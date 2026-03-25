# fastapi-task-queue-service

Async background task processing built with FastAPI, Celery, Redis, and PostgreSQL. Submit a job, get an ID back instantly, poll for results while a worker handles the actual processing.

Live API: http://98.93.17.187:8000/docs  
Worker monitor: http://98.93.17.187:5555

---

## endpoints

- `POST /tasks/` -- submit a task, returns ID immediately
- `GET /tasks/{id}` -- check status (pending, running, completed, failed)
- `GET /tasks/` -- list recent tasks, filter by status
- `GET /health` -- health check

## stack

- **API** -- FastAPI + Uvicorn
- **Workers** -- Celery with exponential backoff retry (2s, 4s, 8s)
- **Broker** -- Redis
- **Database** -- PostgreSQL via SQLAlchemy ORM
- **Monitoring** -- Flower dashboard at port 5555
- **Infrastructure** -- Docker Compose, AWS EC2, AWS RDS
- **CI/CD** -- GitHub Actions (test, build, deploy on every push to main)

---

## running locally

Requires Docker and Docker Compose.

```bash
git clone https://github.com/SAI-KATARI/fastapi-task-queue-service.git
cd fastapi-task-queue-service
cp .env.example .env
docker-compose up --build
```

Starts 5 containers: API, worker, Redis, PostgreSQL, Flower.

- Swagger UI: http://localhost:8000/docs
- Flower dashboard: http://localhost:5555

## submitting a task

```bash
curl -X POST http://localhost:8000/tasks/ \
  -H "Content-Type: application/json" \
  -d '{"task_type": "send_email", "payload": "user@example.com"}'

# {"id": "3f1a...", "status": "pending", ...}
```

```bash
curl http://localhost:8000/tasks/3f1a...

# {"status": "completed", "result": "email dispatched to: user@example.com", ...}
```

Task types: `send_email`, `generate_report`, `process_data`

## running tests

Uses SQLite in-memory so no Postgres needed:

```bash
pip install -r requirements.txt
pytest tests/ -v
```

15 tests covering submission, status polling, retry behavior, failure states, and 10 concurrent submissions.

## project structure

```
app/
  main.py           -- app entry point, table creation, router registration
  database.py       -- SQLAlchemy engine, session, get_db dependency
  celery_app.py     -- Celery + Redis config
  models/task.py    -- Task model (UUID pk, 4-state lifecycle)
  schemas/task.py   -- Pydantic request/response schemas
  routers/tasks.py  -- POST /tasks, GET /tasks/{id}, GET /tasks
  workers/
    task_worker.py  -- task handler, retry logic, error storage
tests/
  test_submit.py    -- submission, validation, list endpoint
  test_status.py    -- status polling, UUID format, field checks
  test_advanced.py  -- retry behavior, concurrent load, E2E integration
conftest.py         -- SQLite test DB override
```

## CI/CD

Every push to main runs three jobs in sequence:

1. Spins up Postgres + Redis service containers, runs `pytest tests/ -v`
2. Builds Docker image, pushes to Docker Hub
3. SSHes into EC2, pulls new image, restarts the stack

PRs only run the test job.

## retry behavior

Workers retry failed tasks with exponential backoff up to 3 times. The exception message gets stored in the `error` column on final failure so you can debug without log access.

| attempt | delay |
|---------|-------|
| 1st retry | 2s |
| 2nd retry | 4s |
| 3rd retry | 8s |
| after 3rd | marked failed, error stored |
