from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ReviewActionType(str, Enum):
    accept_fix = "accept_fix"
    ignore_fix = "ignore_fix"
    accept_issue = "accept_issue"
    ignore_issue = "ignore_issue"


class ReviewActionCreate(BaseModel):
    action_type: ReviewActionType
    item_key: str = Field(min_length=1, max_length=255)
    payload: dict[str, Any] = Field(default_factory=dict)


class ReviewActionRead(BaseModel):
    id: int
    submission_id: int
    action_type: ReviewActionType
    item_key: str
    payload: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
