from fastapi.testclient import TestClient
import pytest
from cognitive_os.core.config import Settings
from cognitive_os.main import create_app


@pytest.mark.parametrize("origin", ["http://localhost:5173", "https://cognitive-os-frontend.vercel.app"])
def test_explicit_frontend_origin_can_send_auth_headers(origin):
    with TestClient(create_app(Settings(_env_file=None, cors_origins=[origin]))) as client:
        response = client.options("/api/v1/recordings/capabilities", headers={
            "Origin": origin, "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,x-organization-id"})
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
        assert client.options("/api/v1/recordings/capabilities", headers={
            "Origin": "https://untrusted.example", "Access-Control-Request-Method": "GET"}).status_code == 400
        login = client.options("/api/v1/auth/login", headers={
            "Origin": origin, "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type"})
        assert login.status_code == 200
        health = client.get("/api/v1/health", headers={"Origin": origin})
        assert health.status_code == 200
        assert health.headers["access-control-allow-origin"] == origin
