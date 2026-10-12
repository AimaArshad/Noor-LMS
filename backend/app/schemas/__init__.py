"""Pydantic v2 schemas. Import from here: ``from app.schemas import UserRead``."""

from app.schemas.announcements import AnnouncementCreate, AnnouncementRead, AnnouncementUpdate
from app.schemas.assignments import (
    AssignmentCreate,
    AssignmentRead,
    AssignmentUpdate,
    GradeSubmission,
    ReturnSubmission,
    SubmissionCreate,
    SubmissionRead,
)
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    TokenPayload,
)
from app.schemas.classrooms import (
    ClassroomCreate,
    ClassroomJoin,
    ClassroomMemberRead,
    ClassroomPeople,
    ClassroomRead,
    ClassroomTeacherRead,
    ClassroomUpdate,
)
from app.schemas.comments import CommentCreate, CommentRead, CommentUpdate
from app.schemas.common import AttachmentRef, Message, Page, dump_attachments
from app.schemas.files import FileCreate, FileRead, FileUpdate
from app.schemas.materials import MaterialCreate, MaterialRead, MaterialUpdate
from app.schemas.notifications import (
    NotificationCreate,
    NotificationPage,
    NotificationRead,
    NotificationUpdate,
)
from app.schemas.quizzes import (
    AnswerResult,
    AnswerSubmit,
    AttemptResult,
    AttemptStart,
    AttemptSubmit,
    QuizCreate,
    QuizOptionCreate,
    QuizOptionPublic,
    QuizOptionRead,
    QuizQuestionCreate,
    QuizQuestionPublic,
    QuizQuestionRead,
    QuizRead,
    QuizResults,
    QuizStudentRead,
    QuizSummary,
    QuizUpdate,
)
from app.schemas.todo import TodoCreate, TodoRead, TodoUpdate
from app.schemas.users import UserCreate, UserPublic, UserRead, UserUpdate

__all__ = [
    # common
    "AttachmentRef", "Message", "Page", "dump_attachments",
    # users / auth
    "UserCreate", "UserPublic", "UserRead", "UserUpdate",
    "LoginRequest", "LogoutRequest", "RefreshRequest", "RegisterRequest",
    "TokenPair", "TokenPayload",
    # classrooms
    "ClassroomCreate", "ClassroomJoin", "ClassroomMemberRead", "ClassroomPeople",
    "ClassroomRead", "ClassroomTeacherRead", "ClassroomUpdate",
    # announcements
    "AnnouncementCreate", "AnnouncementRead", "AnnouncementUpdate",
    # assignments
    "AssignmentCreate", "AssignmentRead", "AssignmentUpdate", "GradeSubmission",
    "ReturnSubmission", "SubmissionCreate", "SubmissionRead",
    # quizzes
    "AnswerResult", "AnswerSubmit", "AttemptResult", "AttemptStart", "AttemptSubmit",
    "QuizCreate", "QuizOptionCreate", "QuizOptionPublic", "QuizOptionRead",
    "QuizQuestionCreate", "QuizQuestionPublic", "QuizQuestionRead", "QuizRead",
    "QuizResults", "QuizStudentRead", "QuizSummary", "QuizUpdate",
    # materials / files / comments
    "MaterialCreate", "MaterialRead", "MaterialUpdate",
    "FileCreate", "FileRead", "FileUpdate",
    "CommentCreate", "CommentRead", "CommentUpdate",
    # notifications / todo
    "NotificationCreate", "NotificationPage", "NotificationRead", "NotificationUpdate",
    "TodoCreate", "TodoRead", "TodoUpdate",
]