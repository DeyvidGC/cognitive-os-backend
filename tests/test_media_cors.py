from fastapi.testclient import TestClient
from cognitive_os.core.config import Settings
from cognitive_os.main import create_app


def test_explicit_frontend_origin_can_send_auth_headers():
    with TestClient(create_app(Settings(_env_file=None, cors_origins=["http://localhost:5173"]))) as client:
        response = client.options("/api/v1/recordings/capabilities", headers={
            "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,x-organization-id"})
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert client.options("/api/v1/recordings/capabilities", headers={
            "Origin": "https://untrusted.example", "Access-Control-Request-Method": "GET"}).status_code == 400
