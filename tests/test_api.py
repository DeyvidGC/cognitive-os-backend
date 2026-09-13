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
