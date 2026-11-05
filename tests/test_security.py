"""密码哈希与 JWT 单元测试。"""

from __future__ import annotations

import pytest

from app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

SECRET = "unit-test-secret-key"


def test_password_hash_roundtrip():
    encoded = hash_password("s3cret-密码")
    assert encoded.startswith("scrypt$")
    assert verify_password("s3cret-密码", encoded) is True
    assert verify_password("wrong-password", encoded) is False


def test_password_salt_is_random():
    assert hash_password("same-password") != hash_password("same-password")


def test_jwt_roundtrip():
    token = create_access_token(42, secret_key=SECRET, expires_minutes=5)
    payload = decode_access_token(token, secret_key=SECRET)
    assert payload["sub"] == "42"


def test_jwt_rejects_tampered_token():
    token = create_access_token(1, secret_key=SECRET)
    with pytest.raises(TokenError):
        decode_access_token(token + "x", secret_key=SECRET)
    with pytest.raises(TokenError):
        decode_access_token(token, secret_key="another-secret-key")


def test_jwt_rejects_expired_token():
    token = create_access_token(1, secret_key=SECRET, expires_minutes=-1)
    with pytest.raises(TokenError):
        decode_access_token(token, secret_key=SECRET)


def test_verify_rejects_garbage():
    assert verify_password("x", "not-a-hash") is False
