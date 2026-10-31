"""Quiz and attempt endpoints (two routers, mounted in ``api.py``).

classroom_router  (/classrooms/{classroom_id}/quizzes)
    POST   /                          create with nested questions (classroom teacher)
    GET    /                          list (member; students see published only)

router            (/quizzes)
    GET    /{id}                      read (teacher: answer key; student: no answer key)
    PATCH  /{id}                      update (teacher)
    DELETE /{id}                      delete (teacher)
    POST   /{id}/start                start or resume an attempt (student)
    POST   /{id}/submit               submit the open attempt, auto-graded (student)
    GET    /{id}/my-attempt           own latest attempt + can_start (student)
    GET    /{id}/results              all attempts + statistics (teacher)
    PATCH  /{id}/attempts/{attempt_id}/answers/{question_id}
                                      manual grading of one answer (teacher)
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.classroom_deps import ClassroomMemberAccess, ClassroomTeacherAccess
from app.core.quiz_deps import QuizMemberAccess, QuizTeacherAccess
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.schemas.common import Message, Page
from app.schemas.quizzes import (
    AttemptResult,
    AttemptStart,
    AttemptSubmit,
    GradeAnswer,
    MyAttemptRead,
    QuizCreate,
    QuizRead,
    QuizResults,
    QuizStudentRead,
    QuizSummary,
    QuizUpdate,
)
from app.services.quiz_service import QuizService

classroom_router = APIRouter()
router = APIRouter()


def get_quiz_service(db: Annotated[AsyncSession, Depends(get_db)]) -> QuizService:
    """Build the per-request service (shares the request's DB session)."""
    return QuizService(db)


Service = Annotated[QuizService, Depends(get_quiz_service)]

#: Teacher and student views are told apart by the ``view`` field.
QuizView = Annotated[QuizRead | QuizStudentRead, Field(discriminator="view")]

_NOT_FOUND = {404: {"model": Message, "description": "Not found, or you may not access it"}}
_FORBIDDEN = {403: {"model": Message, "description": "Not allowed, or classroom is archived"}}


# ====================================================================== #
# /classrooms/{classroom_id}/quizzes
# ====================================================================== #
@classroom_router.post(
    "",
    response_model=QuizRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a quiz with questions and options (classroom teachers)",
    responses={**_NOT_FOUND, **_FORBIDDEN},
)
@limiter.limit("30/minute")
async def create_quiz(
    request: Request,
    body: QuizCreate,
    access: ClassroomTeacherAccess,
    service: Service,
) -> QuizRead:
    """With ``published=true`` a to-do item is created for every student."""
    quiz = await service.create(access.classroom, body)
    return QuizRead.model_validate(quiz)


@classroom_router.get(
    "",
    response_model=Page[QuizSummary],
    summary="List quizzes (students see published only)",
    responses={**_NOT_FOUND},
)
async def list_quizzes(
    access: ClassroomMemberAccess,
    service: Service,
    published: Annotated[
        bool | None, Query(description="Teachers only: filter by published state")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[QuizSummary]:
    return await service.list_for_classroom(
        access.classroom.id,
        include_drafts=access.is_teacher,
        published=published,
        limit=limit,
        offset=offset,
    )


# ====================================================================== #
# /quizzes/{quiz_id}
# ====================================================================== #
@router.get(
    "/{quiz_id}",
    response_model=QuizView,
    summary="Get a quiz (students never receive the answer key)",
    responses={**_NOT_FOUND},
)
async def get_quiz(access: QuizMemberAccess, service: Service) -> QuizRead | QuizStudentRead:
    """Teachers get ``view: "teacher"`` with ``is_correct`` on options. Students get
    ``view: "student"``; short-answer questions have no options at all."""
    quiz = await service.load_full(access.quiz.id)
    if access.is_teacher:
        return QuizRead.model_validate(quiz)
    return QuizStudentRead.model_validate(quiz)


@router.patch(
    "/{quiz_id}",
    response_model=QuizRead,
    summary="Update a quiz (classroom teachers)",
    responses={
        **_NOT_FOUND,
        **_FORBIDDEN,
        409: {"model": Message, "description": "Attempts exist: questions/publish state are locked"},
        422: {"model": Message, "description": "A published quiz needs at least one question"},
    },
)
async def update_quiz(
    body: QuizUpdate, access: QuizTeacherAccess, service: Service
) -> QuizRead:
    """Sending ``questions`` replaces all of them (only while nobody has started the quiz)."""
    quiz = await service.update(access, body)
    return QuizRead.model_validate(quiz)


@router.delete(
    "/{quiz_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a quiz with all attempts (classroom teachers)",
    responses={**_NOT_FOUND, **_FORBIDDEN},
)
async def delete_quiz(access: QuizTeacherAccess, service: Service) -> Response:
    await service.delete(access)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{quiz_id}/start",
    response_model=AttemptStart,
    status_code=status.HTTP_201_CREATED,
    summary="Start (or resume) an attempt (students)",
    responses={
        200: {"model": AttemptStart, "description": "An open attempt was resumed"},
        **_NOT_FOUND,
        **_FORBIDDEN,
        409: {"model": Message, "description": "Already completed and retakes are not allowed"},
    },
)
@limiter.limit("30/minute")
async def start_quiz(
    request: Request,
    response: Response,
    access: QuizMemberAccess,
    service: Service,
) -> AttemptStart:
    """Returns the quiz WITHOUT the answer key and ``expires_at`` for timed quizzes.
    **201** for a new attempt, **200** when the open attempt is resumed."""
    started, created = await service.start(access)
    if not created:
        response.status_code = status.HTTP_200_OK
    return started


@router.post(
    "/{quiz_id}/submit",
    response_model=AttemptResult,
    summary="Submit the open attempt (students)",
    responses={
        **_NOT_FOUND,
        **_FORBIDDEN,
        409: {"model": Message, "description": "No open attempt, or the time limit has passed"},
        422: {"model": Message, "description": "An answer does not fit its question"},
    },
)
@limiter.limit("30/minute")
async def submit_quiz(
    request: Request,
    body: AttemptSubmit,
    access: QuizMemberAccess,
    service: Service,
) -> AttemptResult:
    """Auto-grades MCQ, true/false and short answers that have accepted answers. Unanswered
    questions simply score 0. Per-question results are returned, but never the answer key."""
    return await service.submit(access, body)


@router.get(
    "/{quiz_id}/my-attempt",
    response_model=MyAttemptRead,
    summary="Your latest attempt (students)",
    responses={**_NOT_FOUND, **_FORBIDDEN},
)
async def my_attempt(access: QuizMemberAccess, service: Service) -> MyAttemptRead:
    """``attempt`` is null before the first start. ``can_start`` tells the UI whether to show
    Start / Resume / Retake."""
    return await service.my_attempt(access)


@router.get(
    "/{quiz_id}/results",
    response_model=QuizResults,
    summary="All attempts and scores (classroom teachers)",
    responses={**_NOT_FOUND, **_FORBIDDEN},
)
async def quiz_results(
    access: QuizTeacherAccess,
    service: Service,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> QuizResults:
    return await service.results(access, limit=limit, offset=offset)


@router.patch(
    "/{quiz_id}/attempts/{attempt_id}/answers/{question_id}",
    response_model=AttemptResult,
    summary="Grade one answer manually (classroom teachers)",
    responses={
        **_NOT_FOUND,
        **_FORBIDDEN,
        409: {"model": Message, "description": "Attempt not submitted yet"},
        422: {"model": Message, "description": "More points than the question is worth"},
    },
)
async def grade_answer_manually(
    attempt_id: uuid.UUID,
    question_id: uuid.UUID,
    body: GradeAnswer,
    access: QuizTeacherAccess,
    service: Service,
) -> AttemptResult:
    """For short-answer questions without accepted answers (or to override any answer).
    The attempt's total score is recomputed."""
    return await service.regrade_answer(access, attempt_id, question_id, body)