"""ORM mappings for the resources implemented by the API.

SQL migrations own DDL and constraints; never call create_all at application startup.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, MetaData, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(schema="cognitive")
    type_annotation_map = {str: Text, datetime: DateTime(timezone=True)}


class Created:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Identified:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)


class Organization(Identified, Created, Base):
    __tablename__ = "organizations"
    name: Mapped[str]


class User(Identified, Created, Base):
    __tablename__ = "users"
    identity_subject: Mapped[str]
    display_name: Mapped[str]


class Membership(Created, Base):
    __tablename__ = "memberships"
    organization_id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    role: Mapped[str]


class LocalCredential(Created, Base):
    __tablename__ = "local_credentials"
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str]
    password_hash: Mapped[str]
    failed_attempts: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None]


class AuthToken(Created, Base):
    __tablename__ = "auth_tokens"
    token_hash: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[UUID]
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]


class LearningSession(Identified, Created, Base):
    __tablename__ = "learning_sessions"
    organization_id: Mapped[UUID]
    author_id: Mapped[UUID]
    objective: Mapped[str]
    application_name: Mapped[str]
    status: Mapped[str] = mapped_column(default="capturing")
    consent_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]


class SessionEvent(Identified, Created, Base):
    __tablename__ = "session_events"
    organization_id: Mapped[UUID]
    session_id: Mapped[UUID]
    sequence_number: Mapped[int]
    idempotency_key: Mapped[str]
    event_type: Mapped[str]
    offset_ms: Mapped[int]
    payload: Mapped[dict] = mapped_column(JSONB)
    evidence_id: Mapped[UUID | None]


class Job(Identified, Created, Base):
    __tablename__ = "jobs"
    organization_id: Mapped[UUID]
    session_id: Mapped[UUID | None]
    version_id: Mapped[UUID | None]
    kind: Mapped[str]
    status: Mapped[str] = mapped_column(default="pending")
    idempotency_key: Mapped[str]
    attempts: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=3)
    available_at: Mapped[datetime] = mapped_column(server_default=func.now())
    locked_until: Mapped[datetime | None]
    locked_by: Mapped[str | None]
    last_error: Mapped[str | None]
    completed_at: Mapped[datetime | None]
