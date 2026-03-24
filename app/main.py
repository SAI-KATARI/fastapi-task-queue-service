from fastapi import FastAPI

from app.database import Base, engine
from app.routers import tasks

# create tables on startup if they don't exist yet
# in prod you'd probably want to handle this with alembic migrations instead
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Task Queue Service",
    description="Async background task processing via FastAPI + Celery + Redis",
    version="1.0.0",
)

app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])


@app.get("/health", tags=["health"])
def health_check():
    # keeping this dead simple — load balancers and CI both hit this
    return {"status": "ok"}
