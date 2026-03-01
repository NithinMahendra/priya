from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReviewAction(Base):
    __tablename__ = "review_actions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    item_key: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    submission = relationship("Submission", back_populates="actions")
    user = relationship("User", back_populates="actions")
