from datetime import date

from pydantic import BaseModel


class UsageRead(BaseModel):
    period_month: date
    extraction_count: int
    monthly_limit: int
    remaining: int
