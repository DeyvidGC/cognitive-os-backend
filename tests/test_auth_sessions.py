from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cognitive_os.application.auth import digest_token
from cognitive_os.infrastructure.database.models import AuthToken, Job, LocalCredential, Membership


def create_session(api, user):
    response = api.post("/api/v1/learning-sessions", headers=user["headers"], json={
        "objective": "Explain a quotation", "application_name": "CRM", "consent": True})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def event(key="first", sequence=0):
    return dict(idempotency_key=key, sequence_number=sequence, offset_ms=0,
                event_type="message", text="Open the quotation screen")


def test_password_hash_token_storage_and_logout(api, account):
    user = account()
    response = api.get("/api/v1/auth/me", headers=user["headers"])
    assert response.status_code == 200
    assert response.json()["email"] == user["email"]
    assert "password" not in response.text
    with Session(api.app.state.engine) as db:
        credential = db.get(LocalCredential, UUID(user["id"]))
        assert credential.password_hash.startswith("$argon2id$")
        assert user["password"] not in credential.password_hash
        assert db.get(AuthToken, digest_token(user["token"])) is not None
        assert db.get(AuthToken, user["token"]) is None
    assert api.post("/api/v1/auth/logout", headers=user["headers"]).status_code == 204
    assert api.get("/api/v1/auth/me", headers=user["headers"]).status_code == 401


def test_invalid_expired_tokens_and_wrong_password(api, account):
    user = account()
    assert api.get("/api/v1/auth/me").status_code == 401
    assert api.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401
    response = api.post("/api/v1/auth/login", json={"email": user["email"], "password": "wrong"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    with Session(api.app.state.engine) as db:
        token = db.get(AuthToken, digest_token(user["token"]))
        token.created_at = datetime.now(UTC) - timedelta(hours=2)
        token.expires_at = datetime.now(UTC) - timedelta(hours=1)
        db.commit()
    assert api.get("/api/v1/auth/me", headers=user["headers"]).status_code == 401


def test_account_lockout_and_recovery(api, account):
    user = account()
    for _ in range(5):
        assert api.post("/api/v1/auth/login", json={"email": user["email"], "password": "wrong"}).status_code == 401
    assert api.post("/api/v1/auth/login", json={"email": user["email"], "password": user["password"]}).status_code == 401
    with Session(api.app.state.engine) as db:
        db.get(LocalCredential, UUID(user["id"])).locked_until = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert api.post("/api/v1/auth/login", json={"email": user["email"], "password": user["password"]}).status_code == 200


def test_registration_duplicate_disabled_and_no_password_echo(api, account):
    user = account()
    data = {"email": user["email"].upper(), "password": user["password"],
            "display_name": "Test", "organization_name": "Test"}
    assert api.post("/api/v1/auth/register", json=data).status_code == 409
    data["password"] = "tinySecret"
    response = api.post("/api/v1/auth/register", json=data)
    assert response.status_code == 422
    assert "tinySecret" not in response.text
    api.app.state.settings.registration_enabled = False
    data["password"] = user["password"]
    assert api.post("/api/v1/auth/register", json=data).status_code == 403


def test_session_events_and_finish_idempotency(api, account):
    user = account()
    session_id = create_session(api, user)
    path = f"/api/v1/learning-sessions/{session_id}"
    assert api.post(path + "/finish", headers=user["headers"]).status_code == 409
    first = api.post(path + "/events", headers=user["headers"], json=event())
    assert first.status_code == 200, first.text
    retry = api.post(path + "/events", headers=user["headers"], json=event())
    assert retry.json()["id"] == first.json()["id"]
    assert api.post(path + "/events", headers=user["headers"], json=event(sequence=1)).status_code == 409
    assert api.post(path + "/events", headers=user["headers"], json=event(key="second")).status_code == 409
    finished = api.post(path + "/finish", headers=user["headers"])
    assert finished.status_code == 202, finished.text
    assert finished.json()["status"] == "pending"
    assert api.post(path + "/finish", headers=user["headers"]).json()["id"] == finished.json()["id"]
    assert api.post(path + "/events", headers=user["headers"], json=event(key="late", sequence=1)).status_code == 409
    assert api.get(path, headers=user["headers"]).json()["status"] == "processing"
    assert len(api.get(path + "/events", headers=user["headers"]).json()) == 1


def test_tenant_isolation_and_reader_permissions(api, account):
    owner, outsider = account(), account()
    session_id = create_session(api, owner)
    path = f"/api/v1/learning-sessions/{session_id}"
    assert api.get(path, headers=outsider["headers"]).status_code == 404
    forged = dict(outsider["headers"], **{"X-Organization-ID": owner["organization_id"]})
    assert api.get(path, headers=forged).status_code == 403
    assert api.get("/api/v1/learning-sessions", headers=outsider["headers"]).json() == []
    reader = account(role="reader", organization_id=owner["organization_id"])
    assert api.get(path, headers=reader["headers"]).status_code == 403
    assert api.post(path + "/events", headers=reader["headers"], json=event()).status_code == 403
    with Session(api.app.state.engine) as db:
        db.delete(db.get(Membership, (UUID(owner["organization_id"]), UUID(reader["id"]))))
        db.commit()
    assert api.get("/api/v1/knowledge/search?q=test", headers=reader["headers"]).status_code == 403


def test_concurrent_finish_creates_one_job(api, account):
    user = account()
    session_id = create_session(api, user)
    path = f"/api/v1/learning-sessions/{session_id}"
    assert api.post(path + "/events", headers=user["headers"], json=event()).status_code == 200
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: api.post(path + "/finish", headers=user["headers"]), range(2)))
    assert [r.status_code for r in results] == [202, 202]
    assert results[0].json()["id"] == results[1].json()["id"]
    with Session(api.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(Job).where(Job.session_id == UUID(session_id))) == 1
