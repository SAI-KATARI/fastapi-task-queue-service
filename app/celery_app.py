import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# both broker and backend pointing at Redis
# broker = where tasks get queued
# backend = where results get stored after completion
celery = Celery(
    "task_queue",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.workers.task_worker"],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # track_started lets us see "running" state, not just pending/done
    task_track_started=True,

    # acks_late means the task only gets acked after it finishes
    # so if the worker crashes mid-task, it gets re-queued automatically
    task_acks_late=True,

    # prefetch=1 means each worker only grabs one task at a time
    # without this, a worker can hoard tasks and slow things down
    worker_prefetch_multiplier=1,
)
