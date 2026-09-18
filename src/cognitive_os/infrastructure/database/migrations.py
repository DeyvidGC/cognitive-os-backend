"""Registry of the SQL migrations the ORM mapping assumes are applied.

models.py maps columns and job kinds that only exist once every version below
has run. A missing one is not detected at startup by SQLAlchemy, so it surfaces
as an OperationalError or ProgrammingError on the first request that touches the
affected table, which the API reports as an opaque 503. Checking the registry
turns that into a named list of the migrations still pending.

Keep this tuple in sync with migrations/ and with scripts/test_postgres.ps1.
"""

from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

# 003_Query is a saved query, not a migration, so it has no version row.
REQUIRED_MIGRATIONS = (
    "001_initial",
    "002_pgvector",
    "004_local_auth",
    "005_recordings",
    "006_interactive_learning",
    "007_recording_vectors",
    "008_job_progress",
    "009_periodic_learning",
)


class SchemaUnavailable(Exception):
    """The migration registry itself could not be read."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


def applied_migrations(engine: Engine) -> set[str]:
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("SELECT version FROM cognitive.schema_migrations"))
            return {row[0] for row in rows}
    except ProgrammingError as error:
        # The connection works but cognitive.schema_migrations is absent.
        raise SchemaUnavailable(
            "Schema cognitive.schema_migrations is missing; apply migrations/001_initial.sql"
        ) from error
    except OperationalError as error:
        raise SchemaUnavailable("Database unreachable; check COGNITIVE_DATABASE_URL") from error


def missing_migrations(engine: Engine) -> list[str]:
    """Required versions with no row in cognitive.schema_migrations, in order."""
    applied = applied_migrations(engine)
    return [version for version in REQUIRED_MIGRATIONS if version not in applied]
