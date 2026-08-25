"""Refresh-cookie set/clear, shared between auth.py (login/logout) and
account.py (account deletion) — the set and delete params (httponly/secure/
samesite/path) must match exactly for the browser to actually clear the
cookie, so this is one place rather than two copies that could drift."""

from fastapi import Response

from app.core.config import get_settings

settings = get_settings()

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/auth"


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
