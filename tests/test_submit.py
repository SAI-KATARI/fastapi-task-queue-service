import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# patching celery so tests don't need a real Redis/worker running
@patch("app.routers.tasks.process_task")
def test_submit_task(mock_task):
    mock_task.delay.return_value = None

    resp = client.post("/tasks/", json={
        "task_type": "send_email",
        "payload": "someone@example.com"
    })
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "pending"
    assert data["task_type"] == "send_email"
    assert "id" in data

    # make sure the worker actually got called
    mock_task.delay.assert_called_once()


@patch("app.routers.tasks.process_task")
def test_submit_task_no_payload(mock_task):
    mock_task.delay.return_value = None

    resp = client.post("/tasks/", json={"task_type": "generate_report"})
    assert resp.status_code == 202
    assert resp.json()["task_type"] == "generate_report"


def test_get_task_not_found():
    resp = client.get("/tasks/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "task not found"


def test_list_tasks_returns_list():
    resp = client.get("/tasks/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_list_tasks_filter_by_status():
    # filtering by a valid status shouldn't crash even if nothing matches
    resp = client.get("/tasks/?status=completed")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
