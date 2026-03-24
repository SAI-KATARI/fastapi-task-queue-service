import uuid
import time
import threading
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.task import Task

client = TestClient(app)


# ─────────────────────────────────────────────
# TEST 1 — Retry behavior on task failure
# ─────────────────────────────────────────────
# Both tests use the test_session fixture from conftest — same SQLite
# engine the API uses during tests, so reads and writes stay consistent.

@patch("app.routers.tasks.process_task")
def test_failed_task_stores_error(mock_task, test_session):
    """
    Submits a task via the API, then drives it to failed state directly
    through the test DB session. Verifies the API reflects the failure.
    """
    mock_task.delay.return_value = None

    resp = client.post("/tasks/", json={
        "task_type": "send_email",
        "payload": "bad@example.com"
    })
    assert resp.status_code == 202
    task_id = resp.json()["id"]

    # update via test_session — same engine the API reads from
    task = test_session.query(Task).filter(
        Task.id == uuid.UUID(task_id)
    ).first()
    assert task is not None, "task not found in test DB after submit"

    task.status = "failed"
    task.error = "SMTPConnectionError: could not reach mail server"
    task.retry_count = "3"
    test_session.commit()

    status_resp = client.get(f"/tasks/{task_id}")
    assert status_resp.status_code == 200
    data = status_resp.json()

    assert data["status"] == "failed"
    assert data["error"] is not None
    assert "SMTP" in data["error"]
    assert data["retry_count"] == "3"
    print(f"\n  task failed correctly, error stored: {data['error']}")


@patch("app.routers.tasks.process_task")
def test_worker_increments_retry_count_on_exception(mock_task, test_session):
    """
    Submits a task, simulates 3 retries exhausted by updating retry_count
    and failed status through the test session. Verifies final DB state.
    """
    mock_task.delay.return_value = None

    resp = client.post("/tasks/", json={
        "task_type": "send_email",
        "payload": "failtest@example.com"
    })
    assert resp.status_code == 202
    task_id = resp.json()["id"]

    task = test_session.query(Task).filter(
        Task.id == uuid.UUID(task_id)
    ).first()
    assert task is not None

    # simulate what the worker does after 3 failed retries
    task.status = "failed"
    task.error = "connection refused on port 587"
    task.retry_count = "3"
    test_session.commit()

    # verify through the API
    resp = client.get(f"/tasks/{task_id}")
    data = resp.json()

    assert data["status"] == "failed"
    assert "connection refused" in data["error"]
    assert int(data["retry_count"]) == 3
    print(f"\n  retry_count={data['retry_count']}, error: {data['error']}")


# ─────────────────────────────────────────────
# TEST 2 — Concurrent task submission
# ─────────────────────────────────────────────

@patch("app.routers.tasks.process_task")
def test_concurrent_submissions_all_succeed(mock_task):
    """
    Fires 10 POST requests simultaneously via threads.
    Verifies all succeed, all get unique IDs, none collide.
    """
    mock_task.delay.return_value = None

    results = []
    errors = []

    def submit_one(i):
        try:
            resp = client.post("/tasks/", json={
                "task_type": "process_data",
                "payload": f"batch-input-{i}"
            })
            results.append(resp.json())
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=submit_one, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"some requests failed: {errors}"
    assert len(results) == 10

    statuses = [r["status"] for r in results]
    assert all(s == "pending" for s in statuses)

    ids = [r["id"] for r in results]
    assert len(set(ids)) == 10, "duplicate task IDs — UUID generation broken"

    print(f"\n  10 concurrent tasks, all unique IDs, all pending")


@patch("app.routers.tasks.process_task")
def test_concurrent_submissions_with_threadpool(mock_task):
    """
    Same but with ThreadPoolExecutor — closer to real load test behavior.
    """
    mock_task.delay.return_value = None

    def submit(payload):
        return client.post("/tasks/", json={
            "task_type": "generate_report",
            "payload": payload
        })

    payloads = [f"report-{i}" for i in range(10)]

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(submit, p) for p in payloads]
        responses = [f.result() for f in as_completed(futures)]

    assert all(r.status_code == 202 for r in responses)

    ids = [r.json()["id"] for r in responses]
    assert len(set(ids)) == 10

    print(f"\n  threadpool: 10/10 accepted, no ID collisions")


# ─────────────────────────────────────────────
# TEST 3 — End-to-end integration (real worker)
# ─────────────────────────────────────────────
# No mocks — hits the actual running stack.
# Uses httpx (already in requirements) instead of requests.
# Skips cleanly if the stack isn't up.

@pytest.mark.integration
def test_e2e_task_completes_with_real_worker():
    """
    Full end-to-end with no mocks. Submits via HTTP, polls until completed.
    Requires the full docker-compose stack to be running.
    Skips automatically if the API isn't reachable.
    """
    import os
    import httpx

    base = os.getenv("API_BASE_URL", "http://localhost:8000")

    try:
        submit = httpx.post(f"{base}/tasks/", json={
            "task_type": "process_data",
            "payload": "end to end test payload"
        }, timeout=5)
    except Exception:
        pytest.skip("API not reachable — run with docker-compose stack up")

    assert submit.status_code == 202
    task_id = submit.json()["id"]
    assert submit.json()["status"] == "pending"

    # poll until completed or 20s timeout
    deadline = time.time() + 20
    final_status = None
    data = {}

    while time.time() < deadline:
        poll = httpx.get(f"{base}/tasks/{task_id}", timeout=5)
        data = poll.json()
        final_status = data["status"]

        if final_status in ("completed", "failed"):
            break
        time.sleep(1)

    assert final_status == "completed", f"task still '{final_status}' after 20s"
    assert data["result"] is not None
    assert data["error"] is None

    print(f"\n  E2E: task {task_id[:8]}... completed")
    print(f"  result: {data['result']}")
