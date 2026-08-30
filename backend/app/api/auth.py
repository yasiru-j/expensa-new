import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from itsdangerous import BadData
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import get_settings
from app.core.cookies import REFRESH_COOKIE_NAME, clear_refresh_cookie, set_refresh_cookie
from app.core.deps import get_current_user, get_db
from app.core.oauth import oauth
from app.core.refresh_tokens import (
    claim_or_replay_rotation,
    finalize_refresh_rotation,
    revoke_refresh_jti,
    store_refresh_jti,
)
from app.db.models.user import User
from app.schemas.auth import (
    AccessTokenResponse,
    EmailVerificationConfirm,
    LoginRequest,
    MessageResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    SignupRequest,
)
from app.schemas.user import UserRead

settings = get_settings()
router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _issue_tokens(user_id: uuid.UUID, response: Response) -> tuple[AccessTokenResponse, str]:
    """Returns the response body AND the raw refresh token string — callers
    that are finalizing a rotation (see /refresh below) need the latter to
    record the result for a concurrent duplicate request to replay."""
    access_token = security.create_access_token(user_id)
    refresh_token, jti = security.create_refresh_token(user_id)
    await store_refresh_jti(jti, user_id)
    set_refresh_cookie(response, refresh_token)
    return AccessTokenResponse(access_token=access_token), refresh_token


@router.post("/signup", response_model=AccessTokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    body: SignupRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> AccessTokenResponse:
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(email=body.email, password_hash=security.hash_password(body.password))
    db.add(user)
    await db.flush()

    verification_token = security.create_email_verification_token(user.id)
    # No email provider is wired up yet (not in the locked v1 stack); log the
    # link so the verification flow is testable end-to-end in dev.
    print(f"[dev] email verification link for {user.email}: token={verification_token}")

    result, _refresh_token = await _issue_tokens(user.id, response)
    return result


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> AccessTokenResponse:
    user = await db.scalar(select(User).where(User.email == body.email))
    if (
        user is None
        or user.password_hash is None
        or not security.verify_password(body.password, user.password_hash)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")

    result, _refresh_token = await _issue_tokens(user.id, response)
    return result


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> AccessTokenResponse:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")

    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if token is None:
        raise unauthorized

    try:
        payload = security.decode_token(token)
    except jwt.PyJWTError as exc:
        raise unauthorized from exc

    if payload.get("type") != security.TokenType.REFRESH.value:
        raise unauthorized

    # Rotation with a short reuse grace window — see
    # app/core/refresh_tokens.py for the full policy and trade-off.
    jti = payload["jti"]
    claim = await claim_or_replay_rotation(jti)
    if claim is None:
        raise unauthorized

    if "access_token" in claim:
        # A concurrent duplicate of a request that already rotated this
        # token within the grace window — hand back that same result
        # instead of minting a second rotation (or rejecting this one).
        set_refresh_cookie(response, claim["refresh_token"])
        return AccessTokenResponse(access_token=claim["access_token"])

    if claim["user_id"] != payload["sub"]:
        raise unauthorized

    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None:
        raise unauthorized

    result, new_refresh_token = await _issue_tokens(user.id, response)
    await finalize_refresh_rotation(jti, result.access_token, new_refresh_token)
    return result


@router.post("/logout", response_model=MessageResponse)
async def logout(request: Request, response: Response) -> MessageResponse:
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if token is not None:
        try:
            payload = security.decode_token(token)
            await revoke_refresh_jti(payload["jti"])
        except jwt.PyJWTError:
            pass
    clear_refresh_cookie(response)
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    body: EmailVerificationConfirm, db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    try:
        user_id = security.read_email_verification_token(body.token)
    except BadData as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired token") from exc

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired token")

    user.email_verified = True
    return MessageResponse(message="Email verified")


@router.post("/password-reset/request", response_model=MessageResponse)
async def request_password_reset(
    body: PasswordResetRequest, db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    user = await db.scalar(select(User).where(User.email == body.email))
    if user is not None:
        reset_token = security.create_password_reset_token(user.id)
        print(f"[dev] password reset link for {user.email}: token={reset_token}")
    # Same response whether or not the email is registered, so this endpoint
    # can't be used to enumerate accounts.
    return MessageResponse(message="If that email is registered, a reset link has been sent")


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def confirm_password_reset(
    body: PasswordResetConfirm, db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    try:
        user_id = security.read_password_reset_token(body.token)
    except BadData as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired token") from exc

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired token")

    user.password_hash = security.hash_password(body.new_password)
    return MessageResponse(message="Password updated")


@router.get("/google")
async def google_login(request: Request):
    return await oauth.google.authorize_redirect(request, settings.google_redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo") or await oauth.google.userinfo(token=token)
    email = userinfo["email"]

    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email, password_hash=None, email_verified=bool(userinfo.get("email_verified"))
        )
        db.add(user)
        await db.flush()

    # Cookie is set on the redirect response; the frontend then calls
    # /api/auth/refresh (credentials included) to pull an access token into memory.
    redirect = RedirectResponse(url=settings.frontend_url)
    await _issue_tokens(user.id, redirect)  # cookie side effect only; body is unused here
    return redirect
