"""init: create all EduConnect tables

Revision ID: a3f1c9d2e7b4
Revises:
Create Date: 2026-10-08 00:00:00

Mirrors the models from STEP 2 exactly (names follow the naming convention in
app/db/base.py). Native PostgreSQL ENUM types are created explicitly and dropped
on downgrade.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a3f1c9d2e7b4"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --------------------------------------------------------------------------- #
# Native ENUM types (create_type=False: we create/drop them explicitly below)
# --------------------------------------------------------------------------- #
def _enum(name: str, *values: str) -> postgresql.ENUM:
    return postgresql.ENUM(*values, name=name, create_type=False)


user_role = _enum("user_role", "teacher", "student", "admin")
member_role = _enum("member_role", "teacher", "student")
assignment_state = _enum("assignment_state", "draft", "published")
submission_state = _enum("submission_state", "assigned", "turned_in", "graded", "returned")
question_type = _enum("question_type", "mcq", "short_answer", "true_false")
comment_target_type = _enum("comment_target_type", "assignment", "announcement")
todo_ref_type = _enum("todo_ref_type", "assignment", "quiz")

ENUMS = (
    user_role,
    member_role,
    assignment_state,
    submission_state,
    question_type,
    comment_target_type,
    todo_ref_type,
)


# --------------------------------------------------------------------------- #
# Small column helpers (keep the table definitions readable)
# --------------------------------------------------------------------------- #
def _uuid(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=nullable)


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def _updated_at() -> sa.Column:
    return sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def _attachments() -> sa.Column:
    return sa.Column(
        "attachments",
        postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'[]'::jsonb"),
        nullable=False,
    )


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in ENUMS:
        enum_type.create(bind, checkfirst=True)

    # ------------------------------------------------------------------ users
    op.create_table(
        "users",
        _uuid("id"),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, server_default="student", nullable=False),
        sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # ------------------------------------------------------------- classrooms
    op.create_table(
        "classrooms",
        _uuid("id"),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("section", sa.String(length=100), nullable=True),
        sa.Column("subject", sa.String(length=100), nullable=True),
        sa.Column("room", sa.String(length=100), nullable=True),
        _uuid("owner_id"),
        sa.Column("join_code", sa.String(length=16), nullable=False),
        sa.Column("is_archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_classrooms_owner_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_classrooms")),
    )
    op.create_index(op.f("ix_classrooms_owner_id"), "classrooms", ["owner_id"], unique=False)
    op.create_index(op.f("ix_classrooms_join_code"), "classrooms", ["join_code"], unique=True)

    # ------------------------------------------------------ classroom_members
    op.create_table(
        "classroom_members",
        _uuid("classroom_id"),
        _uuid("user_id"),
        sa.Column("role", member_role, server_default="student", nullable=False),
        sa.Column(
            "joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["classroom_id"],
            ["classrooms.id"],
            name=op.f("fk_classroom_members_classroom_id_classrooms"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_classroom_members_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("classroom_id", "user_id", name=op.f("pk_classroom_members")),
    )
    op.create_index(
        op.f("ix_classroom_members_user_id"), "classroom_members", ["user_id"], unique=False
    )

    # ---------------------------------------------------------- announcements
    op.create_table(
        "announcements",
        _uuid("id"),
        _uuid("classroom_id"),
        _uuid("author_id", nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(
            ["classroom_id"],
            ["classrooms.id"],
            name=op.f("fk_announcements_classroom_id_classrooms"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name=op.f("fk_announcements_author_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_announcements")),
    )
    op.create_index(op.f("ix_announcements_author_id"), "announcements", ["author_id"], unique=False)
    op.create_index(
        "ix_announcements_classroom_id_created_at",
        "announcements",
        ["classroom_id", "created_at"],
        unique=False,
    )

    # ------------------------------------------------------------ assignments
    op.create_table(
        "assignments",
        _uuid("id"),
        _uuid("classroom_id"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_points", sa.Integer(), server_default="100", nullable=False),
        _attachments(),
        sa.Column("state", assignment_state, server_default="draft", nullable=False),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "max_points >= 0", name=op.f("ck_assignments_max_points_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["classroom_id"],
            ["classrooms.id"],
            name=op.f("fk_assignments_classroom_id_classrooms"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assignments")),
    )
    op.create_index(op.f("ix_assignments_due_at"), "assignments", ["due_at"], unique=False)
    op.create_index(
        "ix_assignments_classroom_id_state", "assignments", ["classroom_id", "state"], unique=False
    )

    # ------------------------------------------------------------ submissions
    op.create_table(
        "submissions",
        _uuid("id"),
        _uuid("assignment_id"),
        _uuid("student_id"),
        sa.Column("content", sa.Text(), nullable=True),
        _attachments(),
        sa.Column("state", submission_state, server_default="assigned", nullable=False),
        sa.Column("grade", sa.Numeric(precision=7, scale=2), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True),
        _uuid("graded_by", nullable=True),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "grade IS NULL OR grade >= 0", name=op.f("ck_submissions_grade_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["assignments.id"],
            name=op.f("fk_submissions_assignment_id_assignments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["users.id"],
            name=op.f("fk_submissions_student_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["graded_by"],
            ["users.id"],
            name=op.f("fk_submissions_graded_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_submissions")),
        sa.UniqueConstraint(
            "assignment_id", "student_id", name="uq_submissions_assignment_student"
        ),
    )
    op.create_index(op.f("ix_submissions_student_id"), "submissions", ["student_id"], unique=False)
    op.create_index(op.f("ix_submissions_graded_by"), "submissions", ["graded_by"], unique=False)

    # ---------------------------------------------------------------- quizzes
    op.create_table(
        "quizzes",
        _uuid("id"),
        _uuid("classroom_id"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("time_limit_minutes", sa.Integer(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "time_limit_minutes IS NULL OR time_limit_minutes > 0",
            name=op.f("ck_quizzes_time_limit_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["classroom_id"],
            ["classrooms.id"],
            name=op.f("fk_quizzes_classroom_id_classrooms"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quizzes")),
    )
    op.create_index(op.f("ix_quizzes_due_at"), "quizzes", ["due_at"], unique=False)
    op.create_index(
        "ix_quizzes_classroom_id_published", "quizzes", ["classroom_id", "published"], unique=False
    )

    # --------------------------------------------------------- quiz_questions
    op.create_table(
        "quiz_questions",
        _uuid("id"),
        _uuid("quiz_id"),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("type", question_type, nullable=False),
        sa.Column("points", sa.Numeric(precision=6, scale=2), server_default="1", nullable=False),
        sa.Column("order_index", sa.Integer(), server_default="0", nullable=False),
        sa.CheckConstraint("points >= 0", name=op.f("ck_quiz_questions_points_non_negative")),
        sa.ForeignKeyConstraint(
            ["quiz_id"],
            ["quizzes.id"],
            name=op.f("fk_quiz_questions_quiz_id_quizzes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quiz_questions")),
    )
    op.create_index(
        "ix_quiz_questions_quiz_id_order_index",
        "quiz_questions",
        ["quiz_id", "order_index"],
        unique=False,
    )

    # ----------------------------------------------------------- quiz_options
    op.create_table(
        "quiz_options",
        _uuid("id"),
        _uuid("question_id"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["quiz_questions.id"],
            name=op.f("fk_quiz_options_question_id_quiz_questions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quiz_options")),
    )
    op.create_index(
        op.f("ix_quiz_options_question_id"), "quiz_options", ["question_id"], unique=False
    )

    # ---------------------------------------------------------- quiz_attempts
    op.create_table(
        "quiz_attempts",
        _uuid("id"),
        _uuid("quiz_id"),
        _uuid("student_id"),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Numeric(precision=7, scale=2), nullable=True),
        sa.ForeignKeyConstraint(
            ["quiz_id"],
            ["quizzes.id"],
            name=op.f("fk_quiz_attempts_quiz_id_quizzes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["users.id"],
            name=op.f("fk_quiz_attempts_student_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quiz_attempts")),
        sa.UniqueConstraint("quiz_id", "student_id", name="uq_quiz_attempts_quiz_student"),
    )
    op.create_index(
        op.f("ix_quiz_attempts_student_id"), "quiz_attempts", ["student_id"], unique=False
    )

    # ------------------------------------------------------------ quiz_answers
    op.create_table(
        "quiz_answers",
        _uuid("id"),
        _uuid("attempt_id"),
        _uuid("question_id"),
        sa.Column("answer_text", sa.Text(), nullable=True),
        _uuid("selected_option_id", nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("points_awarded", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["quiz_attempts.id"],
            name=op.f("fk_quiz_answers_attempt_id_quiz_attempts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["quiz_questions.id"],
            name=op.f("fk_quiz_answers_question_id_quiz_questions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["selected_option_id"],
            ["quiz_options.id"],
            name=op.f("fk_quiz_answers_selected_option_id_quiz_options"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quiz_answers")),
        sa.UniqueConstraint("attempt_id", "question_id", name="uq_quiz_answers_attempt_question"),
    )
    op.create_index(
        op.f("ix_quiz_answers_question_id"), "quiz_answers", ["question_id"], unique=False
    )
    op.create_index(
        op.f("ix_quiz_answers_selected_option_id"),
        "quiz_answers",
        ["selected_option_id"],
        unique=False,
    )

    # -------------------------------------------------------------- materials
    op.create_table(
        "materials",
        _uuid("id"),
        _uuid("classroom_id"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        _attachments(),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(
            ["classroom_id"],
            ["classrooms.id"],
            name=op.f("fk_materials_classroom_id_classrooms"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_materials")),
    )
    op.create_index(
        "ix_materials_classroom_id_created_at",
        "materials",
        ["classroom_id", "created_at"],
        unique=False,
    )

    # ------------------------------------------------------------------ files
    op.create_table(
        "files",
        _uuid("id"),
        _uuid("uploader_id", nullable=True),
        sa.Column("original_name", sa.String(length=512), nullable=False),
        sa.Column("stored_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("storage_backend", sa.String(length=20), server_default="local", nullable=False),
        _created_at(),
        sa.CheckConstraint("size_bytes >= 0", name=op.f("ck_files_size_non_negative")),
        sa.ForeignKeyConstraint(
            ["uploader_id"],
            ["users.id"],
            name=op.f("fk_files_uploader_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_files")),
        sa.UniqueConstraint("stored_name", name=op.f("uq_files_stored_name")),
    )
    op.create_index(op.f("ix_files_uploader_id"), "files", ["uploader_id"], unique=False)

    # --------------------------------------------------------------- comments
    op.create_table(
        "comments",
        _uuid("id"),
        _uuid("author_id", nullable=True),
        sa.Column("target_type", comment_target_type, nullable=False),
        _uuid("target_id"),
        sa.Column("body", sa.Text(), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name=op.f("fk_comments_author_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_comments")),
    )
    op.create_index(op.f("ix_comments_author_id"), "comments", ["author_id"], unique=False)
    op.create_index(
        "ix_comments_target_type_target_id",
        "comments",
        ["target_type", "target_id"],
        unique=False,
    )

    # ---------------------------------------------------------- notifications
    op.create_table(
        "notifications",
        _uuid("id"),
        _uuid("user_id"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("type", sa.String(length=50), server_default="general", nullable=False),
        sa.Column("link", sa.String(length=1024), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notifications_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index(
        "ix_notifications_user_id_is_read_created_at",
        "notifications",
        ["user_id", "is_read", "created_at"],
        unique=False,
    )

    # ------------------------------------------------------------- todo_items
    op.create_table(
        "todo_items",
        _uuid("id"),
        _uuid("user_id"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ref_type", todo_ref_type, nullable=True),
        _uuid("ref_id", nullable=True),
        sa.Column("is_done", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        _created_at(),
        sa.CheckConstraint("(ref_type IS NULL) = (ref_id IS NULL)", name=op.f("ck_todo_items_ref_pair")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_todo_items_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_todo_items")),
        sa.UniqueConstraint("user_id", "ref_type", "ref_id", name="uq_todo_items_user_ref"),
    )
    op.create_index(
        "ix_todo_items_user_id_is_done_due_at",
        "todo_items",
        ["user_id", "is_done", "due_at"],
        unique=False,
    )


def downgrade() -> None:
    # Reverse dependency order. Dropping a table also drops its indexes/constraints.
    for table in (
        "todo_items",
        "notifications",
        "comments",
        "files",
        "materials",
        "quiz_answers",
        "quiz_attempts",
        "quiz_options",
        "quiz_questions",
        "quizzes",
        "submissions",
        "assignments",
        "announcements",
        "classroom_members",
        "classrooms",
        "users",
    ):
        op.drop_table(table)

    bind = op.get_bind()
    for enum_type in reversed(ENUMS):
        enum_type.drop(bind, checkfirst=True)