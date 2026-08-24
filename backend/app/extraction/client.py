from functools import lru_cache

from openai import AsyncOpenAI

from app.core.config import get_settings


@lru_cache
def get_openai_client() -> AsyncOpenAI:
    """FastAPI dependency. Tests override this via app.dependency_overrides
    so the real OpenAI API is never called outside production."""
    settings = get_settings()
    return AsyncOpenAI(api_key=settings.openai_api_key)
