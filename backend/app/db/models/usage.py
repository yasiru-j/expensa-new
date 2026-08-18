import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Usage(Base):
    __tablename__ = "usage"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    period_month: Mapped[date] = mapped_column(Date, primary_key=True)
    extraction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
