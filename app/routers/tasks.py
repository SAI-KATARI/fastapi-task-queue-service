import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task
from app.schemas.task import TaskResponse, TaskSubmit
from app.workers.task_worker import process_task

router = APIRouter()


@router.post("/", response_model=TaskResponse, status_code=202)
def submit_task(task_data: TaskSubmit, db: Session = Depends(get_db)):
    """
    Submit a new background task.
    Returns immediately with a task ID — no blocking on worker completion.
    Client should poll GET /tasks/{id} to track progress.
    """
    task = Task(
        id=uuid.uuid4(),
        task_type=task_data.task_type,
        payload=task_data.payload,
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # hand off to celery — this is non-blocking
    process_task.delay(str(task.id), task.task_type, task.payload)

    return task


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, db: Session = Depends(get_db)):
    """
    Fetch the current state of a task by ID.
    Clients poll this endpoint to check if their task is done.
    """
    task = db.query(Task).filter(Task.id == uuid.UUID(task_id)).first()
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@router.get("/", response_model=list[TaskResponse])
def list_tasks(status: str = None, db: Session = Depends(get_db)):
    """
    List recent tasks, optionally filtered by status.
    Capped at 50 rows — add pagination if this grows.
    """
    query = db.query(Task)
    if status:
        query = query.filter(Task.status == status)
    return query.order_by(Task.created_at.desc()).limit(50).all()
