"""Accessibility business logic: settings upsert and defaults."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accessibility import UserAccessibilitySettings
from app.schemas.accessibility import AccessibilitySettingsRead, AccessibilitySettingsUpdate


class AccessibilityService:
    """Stateless service; create one per request."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_default(self, user_id: uuid.UUID) -> AccessibilitySettingsRead:
        """Return the user's accessibility settings.

        When no row exists (user has never customised their settings) a
        default-valued object is returned *without* writing a row to the DB.
        """
        row = await self.db.get(UserAccessibilitySettings, user_id)
        if row is None:
            return AccessibilitySettingsRead.defaults(user_id)
        return self._to_read(row)

    async def upsert(
        self,
        user_id: uuid.UUID,
        data: AccessibilitySettingsUpdate,
    ) -> AccessibilitySettingsRead:
        """Atomically insert or update settings for ``user_id``.

        Uses PostgreSQL ``ON CONFLICT DO UPDATE`` so the operation is safe
        under concurrent requests and never causes a unique-violation error.
        """
        # Build the payload with only the fields that were actually sent.
        patch = data.model_dump(exclude_unset=True)

        # Coerce Decimal → float-safe Decimal for the speed column.
        if "tts_speed" in patch and patch["tts_speed"] is not None:
            patch["tts_speed"] = Decimal(str(patch["tts_speed"]))

        # Columns to update on conflict (all writable columns except user_id).
        all_columns = [
            "tts_enabled",
            "stt_enabled",
            "high_contrast",
            "large_text",
            "tts_voice",
            "tts_speed",
        ]

        # Build SET clause for ON CONFLICT … DO UPDATE: only include sent fields.
        update_cols = [c for c in all_columns if c in patch]

        if update_cols:
            set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
        else:
            # Nothing to update (shouldn't happen because UpdateModel requires ≥1 field,
            # but keep it safe).
            set_clause = "user_id = EXCLUDED.user_id"  # no-op update

        # Build INSERT column list (always include user_id; add sent columns).
        insert_cols = ["user_id"] + update_cols
        # Placeholders: :user_id plus one per update_col.
        placeholders = [":" + c for c in insert_cols]

        params: dict = {"user_id": user_id}
        for col in update_cols:
            params[col] = patch[col]

        stmt = text(
            f"""
            INSERT INTO user_accessibility_settings ({", ".join(insert_cols)})
            VALUES ({", ".join(placeholders)})
            ON CONFLICT (user_id) DO UPDATE
            SET {set_clause},
                updated_at = now()
            """
        )
        await self.db.execute(stmt, params)
        await self.db.commit()

        # Reload the fresh row.
        # expire_on_commit=False is set on our session_maker so the stale state
        # from before the raw SQL update would be served — refresh explicitly.
        row = await self.db.get(
            UserAccessibilitySettings,
            user_id,
            # options=[],
        )
        # After a raw INSERT/UPDATE the ORM cache may be stale; force a refresh.
        if row is not None:
            await self.db.refresh(row)
        else:
            # Fallback: re-query (should not happen).
            row = await self.db.get(UserAccessibilitySettings, user_id)

        if row is None:  # still None after upsert → something went wrong
            return AccessibilitySettingsRead.defaults(user_id)

        return self._to_read(row)

    @staticmethod
    def _to_read(row: UserAccessibilitySettings) -> AccessibilitySettingsRead:
        return AccessibilitySettingsRead(
            user_id=row.user_id,
            tts_enabled=row.tts_enabled,
            stt_enabled=row.stt_enabled,
            high_contrast=row.high_contrast,
            large_text=row.large_text,
            tts_voice=row.tts_voice,
            tts_speed=float(row.tts_speed),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

