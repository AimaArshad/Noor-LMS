"""quiz retakes: allow_retake, option order, open-attempt unique index

Revision ID: b7e2d4a91c35
Revises: a3f1c9d2e7b4
Create Date: 2026-10-10 00:00:00

* quizzes.allow_retake                  - retakes are opt-in
* quiz_options.order_index              - options keep the author's order
* quiz_attempts: the (quiz_id, student_id) UNIQUE constraint is replaced by
    - a plain index for lookups
    - a PARTIAL unique index: at most one *open* attempt per student per quiz
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e2d4a91c35"
down_revision: Union[str, None] = "a3f1c9d2e7b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "quizzes",
        sa.Column("allow_retake", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "quiz_options",
        sa.Column("order_index", sa.Integer(), server_default="0", nullable=False),
    )
    # Give existing options a stable order (per question, by id).
    op.execute(
        """
        UPDATE quiz_options o
        SET order_index = r.rn
        FROM (
            SELECT id, row_number() OVER (PARTITION BY question_id ORDER BY id) - 1 AS rn
            FROM quiz_options
        ) r
        WHERE o.id = r.id
        """
    )

    op.drop_constraint("uq_quiz_attempts_quiz_student", "quiz_attempts", type_="unique")
    op.create_index(
        "ix_quiz_attempts_quiz_id_student_id",
        "quiz_attempts",
        ["quiz_id", "student_id"],
        unique=False,
    )
    op.create_index(
        "uq_quiz_attempts_open_attempt",
        "quiz_attempts",
        ["quiz_id", "student_id"],
        unique=True,
        postgresql_where=sa.text("submitted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_quiz_attempts_open_attempt", table_name="quiz_attempts")
    op.drop_index("ix_quiz_attempts_quiz_id_student_id", table_name="quiz_attempts")

    # The old constraint allows ONE attempt per student: keep only the newest one.
    op.execute(
        """
        DELETE FROM quiz_attempts a
        USING quiz_attempts b
        WHERE a.quiz_id = b.quiz_id
          AND a.student_id = b.student_id
          AND (a.started_at, a.id) < (b.started_at, b.id)
        """
    )
    op.create_unique_constraint(
        "uq_quiz_attempts_quiz_student", "quiz_attempts", ["quiz_id", "student_id"]
    )
    op.drop_column("quiz_options", "order_index")
    op.drop_column("quizzes", "allow_retake")