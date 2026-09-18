import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cognitive_os.core.config import Settings
from cognitive_os.main import create_app


@pytest.fixture(autouse=True)
def disable_real_workers(monkeypatch):
    monkeypatch.setenv("COGNITIVE_EMBEDDED_WORKERS", "false")


@pytest.fixture
def api():
    url = os.environ.get("COGNITIVE_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set COGNITIVE_TEST_DATABASE_URL to a dedicated migrated PostgreSQL test database")
    application = create_app(Settings(_env_file=None, database_url=url,
                                      environment="test", registration_enabled=True))
    with TestClient(application) as client:
        yield client


@pytest.fixture
def account(api):
    def create(role="owner", organization_id=None):
        from sqlalchemy.orm import Session
        from cognitive_os.infrastructure.database.models import Membership

        email = f"{uuid4().hex}@example.com"
        password = "A-long-test-password-123"
        response = api.post("/api/v1/auth/register", json={
            "email": email, "password": password, "display_name": "Test User",
            "organization_name": "Test Organization"})
        assert response.status_code == 201, response.text
        user = response.json()
        own_org = user["memberships"][0]["organization_id"]
        if role != "owner" or organization_id:
            from uuid import UUID
            with Session(api.app.state.engine) as db:
                if organization_id:
                    db.add(Membership(user_id=UUID(user["id"]), organization_id=UUID(organization_id), role=role))
                else:
                    db.get(Membership, (UUID(own_org), UUID(user["id"]))).role = role
                db.commit()
        response = api.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200, response.text
        token = response.json()["access_token"]
        return {"email": email, "password": password, "id": user["id"], "token": token,
                "organization_id": organization_id or own_org,
                "headers": {"Authorization": f"Bearer {token}", "X-Organization-ID": organization_id or own_org}}
    return create
