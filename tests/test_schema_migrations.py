"""The migration registry must match migrations/, or setups drift silently.

A database built without 007 or 008 answers every request that touches jobs with
an opaque 503, so these tests pin the registry to the files on disk and check
that readiness names what is missing.
"""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

from cognitive_os.core.config import Settings
from cognitive_os.infrastructure.database.migrations import REQUIRED_MIGRATIONS
from cognitive_os.main import create_app

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"


def test_registry_lists_every_migration_file():
    # 003_Query is a saved query and records no version, so it is not required.
    on_disk = sorted(path.stem for path in MIGRATIONS.glob("*.sql"))
    assert on_disk == sorted(REQUIRED_MIGRATIONS)


def test_each_migration_records_its_own_version():
    for version in REQUIRED_MIGRATIONS:
        sql = (MIGRATIONS / f"{version}.sql").read_text(encoding="utf-8")
        assert f"schema_migrations(version) VALUES ('{version}')" in sql


def test_registry_matches_the_windows_test_script():
    script = (MIGRATIONS.parent / "scripts" / "test_postgres.ps1").read_text(encoding="utf-8")
    for version in REQUIRED_MIGRATIONS:
        assert f"migrations/{version}.sql" in script


def test_readiness_requires_a_configured_database():
    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert "COGNITIVE_DATABASE_URL" in response.json()["detail"]
        # Liveness stays green: the process is up even with no database.
        assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_readiness_reports_a_fully_migrated_database(api):
    response = api.get("/api/v1/health/ready")
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ready", "migrations": list(REQUIRED_MIGRATIONS)}


def test_readiness_names_the_missing_migration(api):
    engine = api.app.state.engine
    missing = "008_job_progress"
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM cognitive.schema_migrations WHERE version=:v"),
                           {"v": missing})
    try:
        response = api.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert response.json()["detail"] == f"Missing migrations: {missing}"
    finally:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO cognitive.schema_migrations(version) VALUES (:v)"),
                               {"v": missing})
