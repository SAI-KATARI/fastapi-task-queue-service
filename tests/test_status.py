import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app

client = TestClient(app)


@patch("app.routers.tasks.process_task")
def test_submitted_task_starts_as_pending(mock_task):
    mock_task.delay.return_value = None

    resp = client.post("/tasks/", json={
        "task_type": "process_data",
        "payload": "some csv content here"
    })
    assert resp.status_code == 202
    task_id = resp.json()["id"]

    # immediately after submit — should still be pending
    status_resp = client.get(f"/tasks/{task_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "pending"


@patch("app.routers.tasks.process_task")
def test_task_id_is_valid_uuid(mock_task):
    mock_task.delay.return_value = None

    resp = client.post("/tasks/", json={"task_type": "send_email", "payload": "x@y.com"})
    task_id = resp.json()["id"]

    # quick sanity check that IDs look like UUIDs
    import uuid
    parsed = uuid.UUID(task_id)
    assert str(parsed) == task_id


def test_random_uuid_returns_404():
    import uuid
    fake_id = str(uuid.uuid4())
    resp = client.get(f"/tasks/{fake_id}")
    assert resp.status_code == 404


@patch("app.routers.tasks.process_task")
def test_task_response_has_expected_fields(mock_task):
    mock_task.delay.return_value = None

    resp = client.post("/tasks/", json={"task_type": "generate_report", "payload": "q3"})
    data = resp.json()

    expected_keys = {"id", "status", "task_type", "payload", "result", "error", "created_at", "updated_at"}
    assert expected_keys.issubset(data.keys())
