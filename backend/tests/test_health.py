from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready_when_database_is_available():
    db = Mock()
    db.execute.return_value = None

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        r = client.get("/ready")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    assert r.json()["status"] == "ready"
    db.execute.assert_called_once()


def test_ready_returns_503_when_database_is_unavailable():
    db = Mock()
    db.execute.side_effect = SQLAlchemyError("private connection detail")

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        r = client.get("/ready")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 503
    assert r.json()["detail"] == "Database is not ready."
    assert "private connection detail" not in r.text


def test_meta():
    r = client.get("/api/v1/meta")
    assert r.status_code == 200
    assert r.json()["currency"] == "AZN"
    assert r.json()["vat_rate_default"] == 18
