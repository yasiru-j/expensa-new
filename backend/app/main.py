from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.expenses import router as expenses_router
from app.api.usage import router as usage_router
from app.core.config import get_settings
from app.storage.s3 import ensure_bucket_exists

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await ensure_bucket_exists()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Expensa API", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Required by Authlib's Starlette integration to hold OAuth flow state
    # (nonce/code_verifier) between the redirect and the callback.
    app.add_middleware(SessionMiddleware, secret_key=settings.jwt_secret_key)

    app.include_router(auth_router)
    app.include_router(expenses_router)
    app.include_router(dashboard_router)
    app.include_router(usage_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
