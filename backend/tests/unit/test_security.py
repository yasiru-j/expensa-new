import time
import uuid

import jwt
import pytest

from app.core import security


def test_password_hash_roundtrip() -> None:
    password = "correct horse battery staple"
    hashed = security.hash_password(password)

    assert hashed != password
    assert security.verify_password(password, hashed)
    assert not security.verify_password("wrong password", hashed)


def test_access_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    token = security.create_access_token(user_id)

    payload = security.decode_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["type"] == security.TokenType.ACCESS.value


def test_refresh_token_has_unique_jti() -> None:
    user_id = uuid.uuid4()
    token_a, jti_a = security.create_refresh_token(user_id)
    token_b, jti_b = security.create_refresh_token(user_id)

    assert jti_a != jti_b
    assert token_a != token_b
    assert security.decode_token(token_a)["type"] == security.TokenType.REFRESH.value


def test_decode_token_rejects_tampered_signature() -> None:
    token = security.create_access_token(uuid.uuid4())
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

    with pytest.raises(jwt.PyJWTError):
        security.decode_token(tampered)


def test_decode_token_rejects_expired_token(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid.uuid4()
    payload = {
        "sub": str(user_id),
        "type": security.TokenType.ACCESS.value,
        "jti": str(uuid.uuid4()),
        "iat": int(time.time()) - 120,
        "exp": int(time.time()) - 60,
    }
    expired_token = jwt.encode(
        payload, security.settings.jwt_secret_key, algorithm=security.settings.jwt_algorithm
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        security.decode_token(expired_token)


def test_email_verification_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    token = security.create_email_verification_token(user_id)

    assert security.read_email_verification_token(token) == user_id
