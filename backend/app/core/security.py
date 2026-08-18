import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import bcrypt
import jwt
from itsdangerous import URLSafeTimedSerializer

from app.core.config import get_settings

settings = get_settings()


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _create_token(
    user_id: uuid.UUID, token_type: TokenType, expires_delta: timedelta
) -> tuple[str, str]:
    """Returns (token, jti)."""
    jti = str(uuid.uuid4())
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": token_type.value,
        "jti": jti,
        "iat": now,
        "exp": now + expires_delta,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti


def create_access_token(user_id: uuid.UUID) -> str:
    token, _ = _create_token(
        user_id, TokenType.ACCESS, timedelta(minutes=settings.access_token_expire_minutes)
    )
    return token


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, str]:
    return _create_token(
        user_id, TokenType.REFRESH, timedelta(days=settings.refresh_token_expire_days)
    )


def decode_token(token: str) -> dict[str, Any]:
    """Raises jwt.PyJWTError (or a subclass) on any invalid/expired token."""
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def _serializer(salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.jwt_secret_key, salt=salt)


def create_email_verification_token(user_id: uuid.UUID) -> str:
    return _serializer("email-verify").dumps(str(user_id))


def read_email_verification_token(token: str, max_age_seconds: int = 60 * 60 * 24) -> uuid.UUID:
    user_id = _serializer("email-verify").loads(token, max_age=max_age_seconds)
    return uuid.UUID(user_id)


def create_password_reset_token(user_id: uuid.UUID) -> str:
    return _serializer("password-reset").dumps(str(user_id))


def read_password_reset_token(token: str, max_age_seconds: int = 60 * 60) -> uuid.UUID:
    user_id = _serializer("password-reset").loads(token, max_age=max_age_seconds)
    return uuid.UUID(user_id)
