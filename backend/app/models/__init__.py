"""Import every model so they register on ``Base.metadata``.

Alembic's ``env.py`` (STEP 3) imports this package to discover all tables.
"""

from app.db.base import Base
from app.models.enums import (
    AssignmentState,
    CommentTarget,
    MemberRole,
    QuestionType,
    SubmissionState,
    TodoRefType,
    UserRole,
)
from app.models.audiobook_enums import AudiobookStatus, SegmentStatus
from app.models.user import User
from app.models.accessibility import UserAccessibilitySettings
from app.models.classroom import Classroom, ClassroomMember, generate_join_code
from app.models.announcement import Announcement
from app.models.assignment import Assignment, Submission
from app.models.quiz import Quiz, QuizAnswer, QuizAttempt, QuizOption, QuizQuestion
from app.models.material import Material
from app.models.file import File
from app.models.comment import Comment
from app.models.notification import Notification
from app.models.todo import TodoItem
from app.models.audiobook import Audiobook, AudiobookSection, AudiobookSegment, PlaybackProgress

__all__ = [
    "Base",
    # enums
    "AssignmentState",
    "AudiobookStatus",
    "CommentTarget",
    "MemberRole",
    "QuestionType",
    "SegmentStatus",
    "SubmissionState",
    "TodoRefType",
    "UserRole",
    # models
    "Announcement",
    "Assignment",
    "Audiobook",
    "AudiobookSection",
    "AudiobookSegment",
    "Classroom",
    "ClassroomMember",
    "Comment",
    "File",
    "Material",
    "Notification",
    "PlaybackProgress",
    "Quiz",
    "QuizAnswer",
    "QuizAttempt",
    "QuizOption",
    "QuizQuestion",
    "Submission",
    "TodoItem",
    "User",
    "UserAccessibilitySettings",
    "generate_join_code",
]