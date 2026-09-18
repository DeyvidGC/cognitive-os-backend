import logging

from fastapi.testclient import TestClient

from cognitive_os.core.config import Settings
from cognitive_os.main import create_app


def test_health_and_existing_routes():
    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert client.get("/").json() == {"message": "Hello World"}
        assert client.get("/hello/Ana").json() == {"message": "Hello Ana"}
        assert "/api/v1/health" in client.get("/openapi.json").json()["paths"]


def test_configuration_from_environment(monkeypatch):
    monkeypatch.setenv("COGNITIVE_APP_NAME", "Test API")
    monkeypatch.setenv("COGNITIVE_ENVIRONMENT", "test")
    application = create_app(Settings(_env_file=None))
    assert application.title == "Test API"
    assert application.state.settings.environment == "test"


def test_auth_rate_limit_and_unconfigured_database():
    with TestClient(create_app(Settings(_env_file=None))) as client:
        for _ in range(20):
            response = client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "password"})
            assert response.status_code == 503
        response = client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "password"})
        assert response.status_code == 429
        assert response.headers["retry-after"] == "60"


def test_database_failure_is_logged_but_not_disclosed(caplog):
    """A 503 body is identical for every database fault, so the cause must reach the log.

    Without it, a missing migration, an unreachable server and a missing GRANT on a
    single table are indistinguishable from outside the process.
    """
    settings = Settings(_env_file=None, environment="test", registration_enabled=True,
                        database_url="postgresql+psycopg://postgres@127.0.0.1:1/cognitive")
    with TestClient(create_app(settings)) as client:
        with caplog.at_level(logging.ERROR, logger="cognitive_os.main"):
            response = client.post("/api/v1/auth/register", json={
                "email": "a@example.com", "password": "A-long-test-password-123",
                "display_name": "T", "organization_name": "O"})
    assert response.status_code == 503
    # The caller learns nothing about the schema or the server.
    assert response.json() == {"detail": "Database unavailable or migrations missing"}
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "/api/v1/auth/register" in logged
    assert "OperationalError" in logged or "connection" in logged.lower()
