"""Static checks on the ORM metadata (no database required)."""

from sqlalchemy import PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.orm import configure_mappers

from app.models import Base

EXPECTED_TABLES = {
    "users",
    "user_accessibility_settings",
    "classrooms",
    "classroom_members",
    "announcements",
    "assignments",
    "submissions",
    "quizzes",
    "quiz_questions",
    "quiz_options",
    "quiz_attempts",
    "quiz_answers",
    "materials",
    "files",
    "comments",
    "notifications",
    "todo_items",
    # Audiobook feature
    "audiobooks",
    "audiobook_sections",
    "audiobook_segments",
    "playback_progress",
}


def test_all_tables_registered() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_mappers_configure() -> None:
    """Fails on broken relationships / back_populates / ambiguous foreign keys."""
    configure_mappers()


def test_every_foreign_key_is_indexed() -> None:
    """Each FK column must lead at least one index, PK or unique constraint."""
    for table in Base.metadata.sorted_tables:
        leading: set[str] = {list(idx.columns)[0].name for idx in table.indexes}
        leading.add(list(table.primary_key.columns)[0].name)
        for constraint in table.constraints:
            if isinstance(constraint, (UniqueConstraint, PrimaryKeyConstraint)):
                leading.add(list(constraint.columns)[0].name)
        # composite PK: every PK column that is also an FK is covered by index=True
        leading.update(c.name for c in table.primary_key.columns if c.index)
        for fk in table.foreign_keys:
            assert fk.parent.name in leading, f"{table.name}.{fk.parent.name} is not indexed"