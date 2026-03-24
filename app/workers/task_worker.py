import logging
import time

from app.celery_app import celery
from app.database import SessionLocal
from app.models.task import Task

logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=3)
def process_task(self, task_id: str, task_type: str, payload: str):
    """
    Main worker entry point. All task types route through here.
    bind=True gives us access to self so we can call self.retry().
    """
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            # task got deleted between submission and pickup — nothing to do
            logger.warning(f"task {task_id} not found in db, skipping")
            return

        task.status = "running"
        db.commit()
        logger.info(f"picked up task {task_id} (type={task_type})")

        if task_type == "send_email":
            result = handle_email(payload)
        elif task_type == "generate_report":
            result = handle_report(payload)
        elif task_type == "process_data":
            result = handle_data(payload)
        else:
            # don't crash the worker on unknown types, just note it
            result = f"unrecognized task type: {task_type}"
            logger.warning(f"unknown task_type '{task_type}' for task {task_id}")

        task.status = "completed"
        task.result = result
        db.commit()
        logger.info(f"task {task_id} finished — {result}")

    except Exception as exc:
        logger.error(f"task {task_id} failed (attempt {self.request.retries + 1}): {exc}")

        task.status = "failed"
        task.error = str(exc)
        task.retry_count = str(int(task.retry_count or 0) + 1)
        db.commit()

        # exponential backoff: 2s, 4s, 8s across 3 retries
        # after max_retries the exception bubbles up and task stays failed
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)

    finally:
        db.close()


def handle_email(payload: str) -> str:
    # simulating an SMTP call or something like SendGrid
    time.sleep(2)
    return f"email dispatched to: {payload}"


def handle_report(payload: str) -> str:
    # this one takes longer — mimics PDF generation or a heavy DB query
    time.sleep(5)
    return f"report built for: {payload}"


def handle_data(payload: str) -> str:
    # generic data transform placeholder
    time.sleep(3)
    char_count = len(payload or "")
    return f"processed {char_count} chars of input"
