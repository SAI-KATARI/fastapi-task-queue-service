import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Task(Base):
    __tablename__ = "tasks"

    # using postgres UUID natively — avoids string-based ID headaches down the line
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # lifecycle: pending → running → completed | failed
    status = Column(String, nullable=False, default="pending")

    # what kind of task this is — drives which handler gets called in the worker
    task_type = Column(String, nullable=False)

    # arbitrary string payload, keeping it flexible for now
    # could be JSON-encoded if needed later
    payload = Column(Text, nullable=True)

    # where the result lands once the worker finishes
    result = Column(Text, nullable=True)

    # storing the actual exception message if something goes wrong
    error = Column(Text, nullable=True)

    # tracking retries as a string to avoid a migration headache later
    # TODO: switch to Integer in v2
    retry_count = Column(String, default="0")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
