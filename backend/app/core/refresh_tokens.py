"""Refresh-token rotation state, backed by Redis.

Rotation policy — a deliberate trade-off, not the strictest possible one:
a refresh token is single-use, but for REFRESH_TOKEN_REUSE_GRACE_SECONDS
after its first use it stays redeemable, returning the SAME rotation
result rather than either minting a second one or rejecting the request.
That's what turns a genuinely-concurrent duplicate refresh (two browser
tabs loading at once, React StrictMode's double-invoked mount effect, a
retried request after a flaky response) into "session survives" instead
of "user gets logged out" — which is exactly the failure mode strict
immediate invalidation produces, and the bug this module was added to fix.

The cost: a stolen refresh token replayed within that same window would
also succeed. That's judged an acceptable, tightly bounded trade — a
window measured in single-digit seconds, not indefinite reuse — versus
logging real users out on ordinary concurrent requests. A replay *outside*
the window is rejected exactly as under strict single-use rotation, so
theft detection past the grace period is unaffected.

Implementation: each jti's Redis key holds one of three states across its
life —
    {"user_id": "<uuid>"}                                  not yet used
    {"access_token": "...", "refresh_token": "..."}        rotated once;
                                                             within grace
    (key absent)                                            never existed,
                                                             or grace elapsed

`claim_or_replay_rotation` moves a key from the first state to a
placeholder atomically (Redis SET ... XX GET is a single round trip, so
two concurrent callers can never both see the pre-rotation state), so
exactly one caller ever mints new tokens; a concurrent caller either sees
the finished result already, or briefly waits for the winner to finish
writing it via `finalize_refresh_rotation`.
"""

import asyncio
import json
import uuid
from datetime import timedelta
from typing import TypedDict

from app.core.config import get_settings
from app.core.redis import redis_client

settings = get_settings()

_CLAIMED_PLACEHOLDER = "{}"
# How long, and how often, to wait for a concurrent rotation-in-progress to
# finish before giving up — well under one grace window, and far shorter
# than any real HTTP round trip, so it only ever matters for the truly
# simultaneous case (two requests claiming within microseconds of each
# other), not for the more common "arrived a few hundred ms apart" case.
_CLAIM_WAIT_ATTEMPTS = 4
_CLAIM_WAIT_SECONDS = 0.02


class PendingClaim(TypedDict):
    user_id: str


class CompletedRotation(TypedDict):
    access_token: str
    refresh_token: str


def _key(jti: str) -> str:
    return f"refresh_jti:{jti}"


async def store_refresh_jti(jti: str, user_id: uuid.UUID) -> None:
    await redis_client.set(
        _key(jti),
        json.dumps({"user_id": str(user_id)}),
        ex=timedelta(days=settings.refresh_token_expire_days),
    )


async def claim_or_replay_rotation(jti: str) -> PendingClaim | CompletedRotation | None:
    """Returns the state that was in place just before this call:

    - a PendingClaim: this call is the first use — the caller now owns
      rotation and MUST call finalize_refresh_rotation with the result.
    - a CompletedRotation: another request already rotated this token
      (within the grace window) — hand its result straight back.
    - None: unknown jti, or its grace window has elapsed. Reject.
    """
    for _ in range(_CLAIM_WAIT_ATTEMPTS):
        raw = await redis_client.set(
            _key(jti),
            _CLAIMED_PLACEHOLDER,
            xx=True,
            get=True,
            ex=settings.refresh_token_reuse_grace_seconds,
        )
        if raw is None:
            return None
        if raw != _CLAIMED_PLACEHOLDER:
            return json.loads(raw)
        # Someone else claimed it a moment ago and hasn't finalized yet.
        await asyncio.sleep(_CLAIM_WAIT_SECONDS)
    return None  # rotation didn't finish in time; fail closed rather than hang


async def finalize_refresh_rotation(jti: str, access_token: str, refresh_token: str) -> None:
    await redis_client.set(
        _key(jti),
        json.dumps({"access_token": access_token, "refresh_token": refresh_token}),
        ex=settings.refresh_token_reuse_grace_seconds,
    )


async def revoke_refresh_jti(jti: str) -> None:
    await redis_client.delete(_key(jti))
