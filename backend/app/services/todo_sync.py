"""Helpers that keep ``TodoItem`` rows in sync with assignments and quizzes.

Used by the quiz service. ``assignment_service.py`` (STEP 9) still carries its own
private copy of the same logic; the To-Do step can switch it over.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ClassroomMember, MemberRole, TodoItem, TodoRefType, User

_INSERT_CHUNK = 1000


async def active_student_ids(db: AsyncSession, classroom_id: uuid.UUID) -> list[uuid.UUID]:
    """Ids of the classroom's active student members."""
    stmt = (
        select(ClassroomMember.user_id)
        .join(User, User.id == ClassroomMember.user_id)
        .where(
            ClassroomMember.classroom_id == classroom_id,
            ClassroomMember.role == MemberRole.STUDENT,
            User.is_active.is_(True),
        )
    )
    return list((await db.scalars(stmt)).all())


async def create_for_students(
    db: AsyncSession,
    *,
    classroom_id: uuid.UUID,
    ref_type: TodoRefType,
    ref_id: uuid.UUID,
    title: str,
    due_at: datetime | None,
) -> None:
    """One to-do per active student. Idempotent (``ON CONFLICT DO NOTHING``)."""
    student_ids = await active_student_ids(db, classroom_id)
    for i in range(0, len(student_ids), _INSERT_CHUNK):
        rows = [
            {
                "id": uuid.uuid4(),
                "user_id": student_id,
                "title": title,
                "due_at": due_at,
                "ref_type": ref_type,
                "ref_id": ref_id,
                "is_done": False,
            }
            for student_id in student_ids[i : i + _INSERT_CHUNK]
        ]
        await db.execute(
            pg_insert(TodoItem)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["user_id", "ref_type", "ref_id"])
        )


async def sync_for_ref(
    db: AsyncSession,
    *,
    ref_type: TodoRefType,
    ref_id: uuid.UUID,
    title: str,
    due_at: datetime | None,
) -> None:
    """Copy a changed title / due date onto the existing to-do items."""
    await db.execute(
        update(TodoItem)
        .where(TodoItem.ref_type == ref_type, TodoItem.ref_id == ref_id)
        .values(title=title, due_at=due_at)
        .execution_options(synchronize_session=False)
    )


async def delete_for_ref(db: AsyncSession, *, ref_type: TodoRefType, ref_id: uuid.UUID) -> None:
    """Remove every to-do item derived from the given assignment/quiz."""
    await db.execute(
        delete(TodoItem)
        .where(TodoItem.ref_type == ref_type, TodoItem.ref_id == ref_id)
        .execution_options(synchronize_session=False)
    )