import pytest

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.main import create_app


def test_create_and_complete_task(client: TestClient) -> None:
    created = client.post(
        "/api/tasks",
        json={"title": "Check disk space", "description": "Run the usual checks"},
    )
    assert created.status_code == 201
    task_id = created.json()["id"]

    updated = client.patch(f"/api/tasks/{task_id}", json={"completed": True})
    assert updated.status_code == 200
    assert updated.json()["completed"] is True

    tasks = client.get("/api/tasks")
    assert tasks.status_code == 200
    assert tasks.json()[0]["title"] == "Check disk space"


def test_rejects_invalid_task(client: TestClient) -> None:
    response = client.post("/api/tasks", json={"title": "   ", "description": "invalid"})
    assert response.status_code == 422


class UnavailableEngine:
    def connect(self):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))


def test_ready_fails_when_database_is_unavailable() -> None:
    app = create_app(db_engine=UnavailableEngine())  # type: ignore[arg-type]
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not ready", "database": "unavailable"}

@pytest.mark.parametrize("field", ["title", "description", "completed"])
def test_update_rejects_null_fields(client: TestClient, field: str) -> None:
    created = client.post(
        "/api/tasks",
        json={"title": "Check backups", "description": "Keep this text"},
    )
    assert created.status_code == 201
    original = created.json()
    task_id = original["id"]

    response = client.patch(
        f"/api/tasks/{task_id}",
        json={field: None},
    )
    assert response.status_code == 422

    tasks = client.get("/api/tasks")
    assert tasks.status_code == 200
    assert tasks.json() == [original]
