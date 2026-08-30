import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None
    email_verified: bool
    created_at: datetime


class AccountUpdate(BaseModel):
    # Explicitly nullable and optional: PATCH-ing {"full_name": null} clears
    # it, distinct from omitting the field entirely (which leaves it alone)
    # — see app/api/account.py's use of model_fields_set for the distinction.
    full_name: str | None = Field(default=None, max_length=200)

    @field_validator("full_name")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None
