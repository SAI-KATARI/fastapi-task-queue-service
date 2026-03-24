# task-queue-service

Async background task processing service built with FastAPI, Celery, Redis, and PostgreSQL.

The idea: client hits an endpoint, gets a task ID back immediately, and can poll for results while a worker handles the actual processing in the background. No blocking, no timeouts waiting on slow operations.

---

## what it does

- `POST /tasks/` — submit a job, get a task ID back right away
- `GET /tasks/{id}` — check status (pending → running → completed/failed)
- `GET /tasks/` — list recent tasks, filter by status
- Three task types built in: `send_email`, `generate_report`, `process_data`
- Celery workers with automatic retry and exponential backoff (2s → 4s → 8s, up to 3 retries)
- Full task history in PostgreSQL — status, result, error, retry count

---

## stack

| layer | tech |
|---|---|
| API | FastAPI + Uvicorn |
| task queue | Celery |
| broker / backend | Redis |
| database | PostgreSQL (SQLAlchemy ORM) |
| containers | Docker + Docker Compose |
| CI/CD | GitHub Actions → Docker Hub → EC2 |
| prod DB | AWS RDS PostgreSQL |

---

## running locally

**prereqs:** Docker + Docker Compose installed

```bash
git clone https://github.com/SAI-KATARI/fastapi-task-queue-service.git
cd fastapi-task-queue-service

cp .env.example .env

docker-compose up --build
```

That starts 4 containers: API, Celery worker, Redis, PostgreSQL.

Swagger UI at http://localhost:8000/docs

---

## submitting a task

```bash
curl -X POST http://localhost:8000/tasks/ \
  -H "Content-Type: application/json" \
  -d '{"task_type": "send_email", "payload": "user@example.com"}'

# response
# {"id": "3f1a...", "status": "pending", "task_type": "send_email", ...}
```

```bash
# poll for result
curl http://localhost:8000/tasks/3f1a...

# {"status": "completed", "result": "email dispatched to: user@example.com", ...}
```

---

## running tests

Tests use an in-memory SQLite DB so no running Postgres needed:

```bash
pip install -r requirements.txt
pytest tests/ -v
```

---

## project layout

```
app/
  main.py             — app init, table creation, router registration
  database.py         — SQLAlchemy engine + session + get_db dependency
  celery_app.py       — Celery config (broker/backend both Redis)
  models/task.py      — Task ORM model (UUID pk, status, result, error, retries)
  schemas/task.py     — Pydantic schemas for request validation + response serialization
  routers/tasks.py    — POST /tasks, GET /tasks/{id}, GET /tasks
  workers/
    task_worker.py    — Celery task, routes to type handlers, retry logic
tests/
  test_submit.py      — submission, validation, list endpoint tests
  test_status.py      — status polling, UUID format, field presence tests
conftest.py           — SQLite override for test isolation
```

---

## CI/CD

Every push to `main`:
1. GitHub Actions spins up Postgres + Redis service containers
2. Runs `pytest tests/ -v`
3. Builds Docker image
4. Pushes to Docker Hub
5. SSHes into EC2 and pulls + restarts the stack

PRs only run the test job — no deploy on unmerged branches.

---

## retry behavior

Workers catch any exception and retry with exponential backoff:

| attempt | delay |
|---|---|
| 1st retry | 2s |
| 2nd retry | 4s |
| 3rd retry | 8s |
| after 3rd | task marked `failed`, error stored |

The original exception message gets saved to the `error` column so you can debug without digging through logs.

---

## deploying to AWS

See the [Week 5 setup notes](docs/aws-deploy.md) for EC2 + RDS instructions.

Short version:
- EC2 t2.micro runs Docker Compose (api + worker + redis containers)
- RDS db.t3.micro handles PostgreSQL — no local postgres in prod
- GitHub Actions auto-deploys on every merge to main via SSH
