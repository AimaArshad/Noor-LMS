"""STEP 2 , LEVEL 3 TESTS:  
Integration tests: models against a real PostgreSQL database.

Requires a reachable database. Override the URL with ``TEST_DATABASE_URL``.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models import (
    Announcement,
    Assignment,
    AssignmentState,
    Base,
    Classroom,
    ClassroomMember,
    Comment,
    CommentTarget,
    MemberRole,
    Submission,
    User,
    UserRole,
)

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://educonnect:educonnect@localhost:5432/educonnect_test",
)


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Fresh schema for every test; dropped afterwards."""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def _user(email: str, role: UserRole = UserRole.STUDENT) -> User:
    return User(email=email, hashed_password="x", full_name=email.split("@")[0], role=role)


@pytest.mark.asyncio
async def test_create_classroom_and_members(session: AsyncSession) -> None:
    teacher, student = _user("t@x.com", UserRole.TEACHER), _user("s@x.com")
    session.add_all([teacher, student])
    await session.flush()

    classroom = Classroom(name="Math 101", owner_id=teacher.id)
    session.add(classroom)
    await session.flush()
    session.add_all([
        ClassroomMember(classroom_id=classroom.id, user_id=teacher.id, role=MemberRole.TEACHER),
        ClassroomMember(classroom_id=classroom.id, user_id=student.id),
    ])
    await session.commit()

    assert len(classroom.join_code) == 7
    count = await session.scalar(select(func.count()).select_from(ClassroomMember))
    assert count == 2


@pytest.mark.asyncio
async def test_duplicate_email_rejected(session: AsyncSession) -> None:
    session.add_all([_user("dup@x.com"), _user("dup@x.com")])
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_one_submission_per_student(session: AsyncSession) -> None:
    teacher, student = _user("t@x.com", UserRole.TEACHER), _user("s@x.com")
    session.add_all([teacher, student])
    await session.flush()
    classroom = Classroom(name="C", owner_id=teacher.id)
    session.add(classroom)
    await session.flush()
    assignment = Assignment(
        classroom_id=classroom.id, title="HW1", state=AssignmentState.PUBLISHED
    )
    session.add(assignment)
    await session.flush()

    session.add(Submission(assignment_id=assignment.id, student_id=student.id))
    await session.flush()
    session.add(Submission(assignment_id=assignment.id, student_id=student.id))
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_owner_with_classroom_cannot_be_deleted(session: AsyncSession) -> None:
    teacher = _user("t@x.com", UserRole.TEACHER)
    session.add(teacher)
    await session.flush()
    session.add(Classroom(name="C", owner_id=teacher.id))
    await session.commit()

    await session.delete(teacher)
    with pytest.raises(IntegrityError):  # ON DELETE RESTRICT
        await session.commit()


@pytest.mark.asyncio
async def test_deleting_classroom_cascades_and_removes_comments(session: AsyncSession) -> None:
    teacher = _user("t@x.com", UserRole.TEACHER)
    session.add(teacher)
    await session.flush()
    classroom = Classroom(name="C", owner_id=teacher.id)
    session.add(classroom)
    await session.flush()

    assignment = Assignment(classroom_id=classroom.id, title="HW")
    announcement = Announcement(classroom_id=classroom.id, author_id=teacher.id, content="Hi")
    session.add_all([assignment, announcement])
    await session.flush()
    session.add_all([
        Comment(author_id=teacher.id, target_type=CommentTarget.ASSIGNMENT,
                target_id=assignment.id, body="a"),
        Comment(author_id=teacher.id, target_type=CommentTarget.ANNOUNCEMENT,
                target_id=announcement.id, body="b"),
    ])
    await session.commit()

    await session.delete(classroom)  # AsyncSession.delete is a coroutine: cascades load fine
    await session.commit()

    for model in (Assignment, Announcement, Comment):
        assert await session.scalar(select(func.count()).select_from(model)) == 0
