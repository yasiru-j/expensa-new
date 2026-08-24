from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.db.models.user import User
from app.schemas.usage import UsageRead
from app.usage.quota import current_period, get_current_usage

router = APIRouter(prefix="/api/usage", tags=["usage"])
settings = get_settings()


@router.get("", response_model=UsageRead)
async def get_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsageRead:
    count = await get_current_usage(db, current_user.id)
    return UsageRead(
        period_month=current_period(),
        extraction_count=count,
        monthly_limit=settings.monthly_extraction_quota,
        remaining=max(0, settings.monthly_extraction_quota - count),
    )
