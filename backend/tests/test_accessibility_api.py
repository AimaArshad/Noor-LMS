"""Integration tests for GET/PATCH /users/me/accessibility.

Covers:
- defaults when no row exists
- partial update (only sent fields change)
- full update
- validation: speed out of range, bad voice id, empty body
- privacy: user A cannot read/write user B's settings via own token
- 401 when unauthenticated
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.helpers import API, make_user

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ENDPOINT = f"{API}/users/me/accessibility"
DEFAULT_BODY = {
    "tts_enabled": False,
    "stt_enabled": False,
    "high_contrast": False,
    "large_text": False,
    "tts_voice": None,
    "tts_speed": 1.0,
}


async def _get(client: AsyncClient, headers: dict) -> dict:
    r = await client.get(ENDPOINT, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAccessibilitySettingsDefaults:
    """GET returns sensible defaults when no row exists."""

    async def test_defaults_before_first_patch(self, client: AsyncClient) -> None:
        h = await make_user(client, "alice@example.com")
        body = await _get(client, h)
        assert body["tts_enabled"] is False
        assert body["stt_enabled"] is False
        assert body["high_contrast"] is False
        assert body["large_text"] is False
        assert body["tts_voice"] is None
        assert body["tts_speed"] == pytest.approx(1.0)
        # timestamps present and non-empty
        assert "created_at" in body
        assert "updated_at" in body

    async def test_401_unauthenticated(self, client: AsyncClient) -> None:
        r = await client.get(ENDPOINT)
        assert r.status_code == 401


class TestAccessibilitySettingsUpdate:
    """PATCH creates / updates settings correctly."""

    async def test_patch_single_flag(self, client: AsyncClient) -> None:
        h = await make_user(client, "bob@example.com")
        r = await client.patch(ENDPOINT, json={"tts_enabled": True}, headers=h)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["tts_enabled"] is True
        # Other fields still default
        assert data["stt_enabled"] is False
        assert data["tts_speed"] == pytest.approx(1.0)

    async def test_patch_speed_and_voice(self, client: AsyncClient) -> None:
        h = await make_user(client, "carol@example.com")
        r = await client.patch(
            ENDPOINT,
            json={"tts_speed": 1.50, "tts_voice": "en_US-lessac-medium"},
            headers=h,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["tts_speed"] == pytest.approx(1.50)
        assert data["tts_voice"] == "en_US-lessac-medium"

    async def test_patch_clears_voice_with_null(self, client: AsyncClient) -> None:
        h = await make_user(client, "dave@example.com")
        await client.patch(ENDPOINT, json={"tts_voice": "some-voice"}, headers=h)
        r = await client.patch(ENDPOINT, json={"tts_voice": None}, headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["tts_voice"] is None

    async def test_patch_is_idempotent(self, client: AsyncClient) -> None:
        h = await make_user(client, "eve@example.com")
        for _ in range(3):
            r = await client.patch(ENDPOINT, json={"high_contrast": True}, headers=h)
            assert r.status_code == 200, r.text
            assert r.json()["high_contrast"] is True

    async def test_401_unauthenticated_patch(self, client: AsyncClient) -> None:
        r = await client.patch(ENDPOINT, json={"tts_enabled": True})
        assert r.status_code == 401

    async def test_get_reflects_patch(self, client: AsyncClient) -> None:
        """GET after PATCH must return the new values."""
        h = await make_user(client, "frank@example.com")
        await client.patch(ENDPOINT, json={"large_text": True, "tts_speed": 1.75}, headers=h)
        data = await _get(client, h)
        assert data["large_text"] is True
        assert data["tts_speed"] == pytest.approx(1.75)


class TestAccessibilitySettingsValidation:
    """422 on invalid inputs."""

    async def test_speed_too_low(self, client: AsyncClient) -> None:
        h = await make_user(client, "grace@example.com")
        r = await client.patch(ENDPOINT, json={"tts_speed": 0.4}, headers=h)
        assert r.status_code == 422

    async def test_speed_too_high(self, client: AsyncClient) -> None:
        h = await make_user(client, "harry@example.com")
        r = await client.patch(ENDPOINT, json={"tts_speed": 2.1}, headers=h)
        assert r.status_code == 422

    async def test_speed_boundary_values(self, client: AsyncClient) -> None:
        h = await make_user(client, "iris@example.com")
        for speed in (0.50, 2.00):
            r = await client.patch(ENDPOINT, json={"tts_speed": speed}, headers=h)
            assert r.status_code == 200, f"speed={speed} rejected: {r.text}"

    async def test_bad_voice_id(self, client: AsyncClient) -> None:
        h = await make_user(client, "jay@example.com")
        r = await client.patch(ENDPOINT, json={"tts_voice": "bad voice!"}, headers=h)
        assert r.status_code == 422

    async def test_empty_body_rejected(self, client: AsyncClient) -> None:
        h = await make_user(client, "kim@example.com")
        r = await client.patch(ENDPOINT, json={}, headers=h)
        assert r.status_code == 422

    async def test_unknown_field_rejected(self, client: AsyncClient) -> None:
        h = await make_user(client, "leo@example.com")
        r = await client.patch(ENDPOINT, json={"unknown_field": True}, headers=h)
        assert r.status_code == 422


class TestAccessibilitySettingsPrivacy:
    """User A's token cannot see or change user B's settings."""

    async def test_settings_are_scoped_to_user(self, client: AsyncClient) -> None:
        h_a = await make_user(client, "max@example.com")
        h_b = await make_user(client, "nina@example.com")

        # A sets high_contrast = True
        await client.patch(ENDPOINT, json={"high_contrast": True}, headers=h_a)

        # B reads their own settings — must still be default (False)
        data_b = await _get(client, h_b)
        assert data_b["high_contrast"] is False

