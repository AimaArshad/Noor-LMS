"""Assignment and submission endpoints (three routers, mounted in ``api.py``).

classroom_router  (/classrooms/{classroom_id}/assignments)
    POST   /                          create (classroom teacher)
    GET    /                          list (member; students see published only)

router            (/assignments)
    GET    /{id}                      read (member; drafts hidden from students)
    PATCH  /{id}                      update (teacher)
    DELETE /{id}                      delete (teacher)
    POST   /{id}/submit               turn in / update work (student)
    GET    /{id}/submissions          all submissions (teacher)
    GET    /{id}/my-submission        own submission or null (student)

submissions_router (/submissions)
    PATCH  /{id}/grade                grade + feedback (teacher)
    PATCH  /{id}/return               return to the student (teacher)
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.assignment_deps import (
    AssignmentMemberAccess,
    AssignmentTeacherAccess,
    SubmissionTeacherAccess,
)
from app.core.classroom_deps import ClassroomMemberAccess, ClassroomTeacherAccess
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models import AssignmentState, SubmissionState
from app.schemas.assignments import (
    AssignmentCreate,
    AssignmentRead,
    AssignmentUpdate,
    GradeSubmission,
    ReturnSubmission,
    SubmissionCreate,
    SubmissionList,
    SubmissionRead,
)
from app.schemas.common import Message, Page
from app.services.assignment_service import AssignmentService
from app.services.file_service import FileService
from app.services.storage import get_storage

classroom_router = APIRouter()
router = APIRouter()
submissions_router = APIRouter()


def get_assignment_service(db: Annotated[AsyncSession, Depends(get_db)]) -> AssignmentService:
    """Build the per-request service (shares the request's DB session)."""
    return AssignmentService(db, FileService(db, get_storage("local")))


Service = Annotated[AssignmentService, Depends(get_assignment_service)]

_NOT_FOUND = {404: {"model": Message, "description": "Not found, or you may not access it"}}
_FORBIDDEN = {403: {"model": Message, "description": "Not allowed, or classroom is archived"}}


# ====================================================================== #
# /classrooms/{classroom_id}/assignments
# ====================================================================== #
@classroom_router.post(
    "",
    response_model=AssignmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an assignment (classroom teachers)",
    responses={**_NOT_FOUND, **_FORBIDDEN},
)
@limiter.limit("30/minute")
async def create_assignment(
    request: Request,
    body: AssignmentCreate,
    access: ClassroomTeacherAccess,
    service: Service,
) -> AssignmentRead:
    """With ``state=published`` a to-do item is created for every student."""
    assignment = await service.create(access.classroom, access.user, body)
    return AssignmentRead.model_validate(assignment)


@classroom_router.get(
    "",
    response_model=Page[AssignmentRead],
    summary="List assignments (students see published only)",
    responses={**_NOT_FOUND},
)
async def list_assignments(
    access: ClassroomMemberAccess,
    service: Service,
    state: Annotated[AssignmentState | None, Query(description="draft | published")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AssignmentRead]:
    return await service.list_for_classroom(
        access.is_teacher, access.classroom.id, state=state, limit=limit, offset=offset
    )


# ====================================================================== #
# /assignments/{assignment_id}
# ====================================================================== #
@router.get(
    "/{assignment_id}",
    response_model=AssignmentRead,
    summary="Get an assignment",
    responses={**_NOT_FOUND},
)
async def get_assignment(access: AssignmentMemberAccess) -> AssignmentRead:
    return AssignmentRead.model_validate(access.assignment)


@router.patch(
    "/{assignment_id}",
    response_model=AssignmentRead,
    summary="Update an assignment (classroom teachers)",
    responses={
        **_NOT_FOUND,
        **_FORBIDDEN,
        409: {"model": Message, "description": "Would invalidate existing grades / submissions"},
    },
)
async def update_assignment(
    body: AssignmentUpdate, access: AssignmentTeacherAccess, service: Service
) -> AssignmentRead:
    """Publishing (draft → published) creates the students' to-do items."""
    assignment = await service.update(access, body)
    return AssignmentRead.model_validate(assignment)


@router.delete(
    "/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an assignment, its submissions and comments (classroom teachers)",
    responses={**_NOT_FOUND, **_FORBIDDEN},
)
async def delete_assignment(access: AssignmentTeacherAccess, service: Service) -> Response:
    await service.delete(access)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{assignment_id}/submit",
    response_model=SubmissionRead,
    summary="Turn in (or update) your work (students)",
    responses={
        **_NOT_FOUND,
        **_FORBIDDEN,
        409: {"model": Message, "description": "Work is graded; wait for it to be returned"},
        422: {"model": Message, "description": "Empty submission or unknown attachment"},
    },
)
@limiter.limit("30/minute")
async def submit_assignment(
    request: Request,
    body: SubmissionCreate,
    access: AssignmentMemberAccess,
    service: Service,
) -> SubmissionRead:
    """Creates the submission on first call, updates it afterwards. State becomes ``turned_in``
    and every teacher of the classroom gets a notification."""
    submission = await service.submit(access, body)
    return service.present(submission, hide_unreturned_grade=True)


@router.get(
    "/{assignment_id}/submissions",
    response_model=SubmissionList,
    summary="List submissions (classroom teachers)",
    responses={**_NOT_FOUND, **_FORBIDDEN},
)
async def list_submissions(
    access: AssignmentTeacherAccess,
    service: Service,
    state: Annotated[
        SubmissionState | None, Query(description="turned_in | graded | returned")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SubmissionList:
    return await service.list_submissions(access, state=state, limit=limit, offset=offset)


@router.get(
    "/{assignment_id}/my-submission",
    response_model=SubmissionRead | None,
    summary="Get your own submission (students)",
    responses={**_NOT_FOUND, **_FORBIDDEN},
)
async def my_submission(
    access: AssignmentMemberAccess, service: Service
) -> SubmissionRead | None:
    """Returns ``null`` (200) when you have not submitted yet. Grades stay hidden until the
    teacher returns the work."""
    submission = await service.my_submission(access)
    if submission is None:
        return None
    return service.present(submission, hide_unreturned_grade=True)


# ====================================================================== #
# /submissions/{submission_id}
# ====================================================================== #
@submissions_router.patch(
    "/{submission_id}/grade",
    response_model=SubmissionRead,
    summary="Grade a submission (classroom teachers)",
    responses={
        **_NOT_FOUND,
        **_FORBIDDEN,
        409: {"model": Message, "description": "Nothing turned in yet"},
        422: {"model": Message, "description": "Grade above the assignment's max_points"},
    },
)
async def grade_submission(
    body: GradeSubmission, access: SubmissionTeacherAccess, service: Service
) -> SubmissionRead:
    """The student sees the grade only after ``/return``."""
    submission = await service.grade(access, body)
    return service.present(submission, hide_unreturned_grade=False)


@submissions_router.patch(
    "/{submission_id}/return",
    response_model=SubmissionRead,
    summary="Return a submission to the student (classroom teachers)",
    responses={
        **_NOT_FOUND,
        **_FORBIDDEN,
        409: {"model": Message, "description": "Already returned / nothing turned in"},
    },
)
async def return_submission(
    access: SubmissionTeacherAccess,
    service: Service,
    body: ReturnSubmission | None = None,
) -> SubmissionRead:
    """Makes grade and feedback visible to the student and notifies them. The body is optional."""
    submission = await service.return_work(access, body)
    return service.present(submission, hide_unreturned_grade=False)