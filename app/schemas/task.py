from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class TaskSubmit(BaseModel):
    """
    What the client sends when submitting a new task.
    payload is optional — some task types don't need extra data.
    """
    task_type: str
    payload: Optional[str] = None


class TaskResponse(BaseModel):
    """
    What we send back. Includes everything the client might need
    to either display progress or debug a failure.
    """
    id: UUID
    status: str
    task_type: str
    payload: Optional[str]
    result: Optional[str]
    error: Optional[str]
    retry_count: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        # needed so SQLAlchemy ORM objects serialize correctly
        from_attributes = True
