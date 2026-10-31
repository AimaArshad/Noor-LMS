"""Unit tests for hashing and JWT helpers (no database or Redis needed)."""

import base64
import json
import uuid
from datetime import timedelta

import pytest

from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_and_verify() -> None:
    hashed = hash_password("Passw0rdX")
    assert hashed != "Passw0rdX" and hashed.startswith("$2")
    assert verify_password("Passw0rdX", hashed)
    assert not verify_password("wrong-pass1", hashed)
    assert not verify_password("x" * 100, hashed)  # > 72 bytes -> False, no exception
    assert not verify_password("Passw0rdX", "not-a-hash")


def test_access_token_roundtrip() -> None:
    uid = uuid.uuid4()
    payload = decode_token(create_access_token(uid), expected_type="access")
    assert payload.sub == str(uid) and payload.type == "access" and payload.jti


def test_token_type_is_enforced() -> None:
    with pytest.raises(TokenError):
        decode_token(create_refresh_token(uuid.uuid4()), expected_type="access")
    with pytest.raises(TokenError):
        decode_token(create_access_token(uuid.uuid4()), expected_type="refresh")


def test_expired_token_rejected() -> None:
    token = create_access_token(uuid.uuid4(), expires_delta=timedelta(seconds=-5))
    with pytest.raises(TokenError, match="expired"):
        decode_token(token)

 
# def test_tampered_token_rejected() -> None:
#     token = create_access_token(uuid.uuid4())
#     flipped = "A" if token[-1] != "A" else "B"
#     with pytest.raises(TokenError):
#         decode_token(token[:-1] + flipped)
#     with pytest.raises(TokenError):
#         decode_token("not.a.jwt")

# RESOLVES ==================== short test summary info ====================
# FAILED tests/test_security.py::test_tampered_token_rejected - Failed: DID NOT RAISE <class 'app.core.security.TokenError'>
# 1 failed, 142 passed, 357 warnings in 312.80s (0:05:12)
def test_tampered_token_rejected() -> None:
    token = create_access_token(uuid.uuid4())
    header, payload, signature = token.split(".")

    i = len(signature) // 2
    tampered_sig = signature[:i] + ("A" if signature[i] != "A" else "B") + signature[i + 1:]
    with pytest.raises(TokenError):
        decode_token(f"{header}.{payload}.{tampered_sig}")

    i = len(payload) // 2
    tampered_payload = payload[:i] + ("A" if payload[i] != "A" else "B") + payload[i + 1:]
    with pytest.raises(TokenError):
        decode_token(f"{header}.{tampered_payload}.{signature}")

    with pytest.raises(TokenError):
        decode_token("not.a.jwt")

def test_alg_none_token_rejected() -> None:
    def b64(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    forged = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': str(uuid.uuid4()), 'type': 'access', 'exp': 9999999999, 'iat': 1, 'jti': 'x'})}."
    with pytest.raises(TokenError):
        decode_token(forged)