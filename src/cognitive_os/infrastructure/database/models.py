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
    recording_id: Mapped[UUID | None]
    kind: Mapped[str]
    status: Mapped[str] = mapped_column(default="pending")
    stage: Mapped[str] = mapped_column(default="queued")
    progress_percent: Mapped[int] = mapped_column(default=0)
    idempotency_key: Mapped[str]
    attempts: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=3)
    available_at: Mapped[datetime] = mapped_column(server_default=func.now())
    locked_until: Mapped[datetime | None]
    locked_by: Mapped[str | None]
    last_error: Mapped[str | None]
    completed_at: Mapped[datetime | None]


class Procedure(Identified, Created, Base):
    __tablename__ = "procedures"
    organization_id: Mapped[UUID]
    title: Mapped[str]
    scope: Mapped[str]


class ProcedureVersion(Identified, Created, Base):
    __tablename__ = "procedure_versions"
    organization_id: Mapped[UUID]
    procedure_id: Mapped[UUID]
    source_session_id: Mapped[UUID | None]
    version_number: Mapped[int]
    status: Mapped[str] = mapped_column(default="draft")
    summary: Mapped[str] = mapped_column(default="")
    model_name: Mapped[str | None]
    prompt_version: Mapped[str | None]
    reviewer_id: Mapped[UUID | None]
    approved_at: Mapped[datetime | None]
    published_at: Mapped[datetime | None]


class Step(Identified, Base):
    __tablename__ = "steps"
    organization_id: Mapped[UUID]
    version_id: Mapped[UUID]
    position: Mapped[int]
    instruction: Mapped[str]
    expected_result: Mapped[str]
    origin: Mapped[str]
    validation_status: Mapped[str] = mapped_column(default="pending")


class StepEvidence(Base):
    __tablename__ = "step_evidence"
    organization_id: Mapped[UUID] = mapped_column(primary_key=True)
    step_id: Mapped[UUID] = mapped_column(primary_key=True)
    evidence_id: Mapped[UUID] = mapped_column(primary_key=True)
    explanation: Mapped[str]


class Tutorial(Identified, Created, Base):
    __tablename__ = "tutorials"
    organization_id: Mapped[UUID]
    version_id: Mapped[UUID]
    format: Mapped[str]
    content: Mapped[str | None]
    storage_key: Mapped[str | None]


class KnowledgeChunk(Identified, Created, Base):
    __tablename__ = "knowledge_chunks"
    organization_id: Mapped[UUID]
    version_id: Mapped[UUID]
    step_id: Mapped[UUID | None]
    position: Mapped[int]
    content: Mapped[str]


class AuditEvent(Identified, Created, Base):
    __tablename__ = "audit_events"
    organization_id: Mapped[UUID]
    actor_id: Mapped[UUID | None]
    action: Mapped[str]
    resource_type: Mapped[str]
    resource_id: Mapped[UUID]
    details: Mapped[dict] = mapped_column(JSONB, default=dict)


class Evidence(Identified, Created, Base):
    __tablename__ = "evidence"
    organization_id: Mapped[UUID]
    session_id: Mapped[UUID]
    storage_key: Mapped[str]
    media_type: Mapped[str]
    sha256: Mapped[str]
    size_bytes: Mapped[int]
    captured_at: Mapped[datetime]


class Clarification(Identified, Created, Base):
    __tablename__ = "clarifications"
    organization_id: Mapped[UUID]
    session_id: Mapped[UUID]
    question: Mapped[str]
    answer: Mapped[str | None]
    answered_by: Mapped[UUID | None]
    resolved_at: Mapped[datetime | None]


class Recording(Identified, Created, Base):
    __tablename__ = "recordings"
    organization_id: Mapped[UUID]
    session_id: Mapped[UUID]
    idempotency_key: Mapped[str]
    blob_key: Mapped[str]
    blob_snapshot: Mapped[str | None]
    media_type: Mapped[str]
    size_bytes: Mapped[int]
    content_sha256: Mapped[str | None]
    audio_consent: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(default="uploading")
    consent_at: Mapped[datetime]
    uploaded_at: Mapped[datetime | None]
    error_code: Mapped[str | None]


class RecordingReport(Created, Base):
    __tablename__ = "recording_reports"
    recording_id: Mapped[UUID] = mapped_column(primary_key=True)
    organization_id: Mapped[UUID]
    content: Mapped[dict] = mapped_column(JSONB)
    original_content: Mapped[dict] = mapped_column(JSONB)
    sampling: Mapped[dict] = mapped_column(JSONB)
    model_name: Mapped[str]
    prompt_version: Mapped[str]
    revision: Mapped[int] = mapped_column(default=1)
    review_status: Mapped[str] = mapped_column(default="pending")
    reviewer_id: Mapped[UUID | None]
    reviewed_at: Mapped[datetime | None]
    feedback: Mapped[str | None]
    version_id: Mapped[UUID | None]


class ReportRevision(Created, Base):
    __tablename__ = "recording_report_revisions"
    recording_id: Mapped[UUID] = mapped_column(primary_key=True)
    revision: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[UUID]
    snapshot: Mapped[dict] = mapped_column(JSONB)


class StepRecordingEvidence(Base):
    __tablename__ = "step_recording_evidence"
    organization_id: Mapped[UUID]
    step_id: Mapped[UUID] = mapped_column(primary_key=True)
    recording_id: Mapped[UUID]
    report_revision: Mapped[int]
    frame_indices: Mapped[list] = mapped_column(JSONB)


class AgentTurn(Identified, Created, Base):
    __tablename__ = "agent_turns"
    organization_id: Mapped[UUID]
    session_id: Mapped[UUID]
    user_id: Mapped[UUID]
    client_message_id: Mapped[UUID]
    request_hash: Mapped[str]
    user_text: Mapped[str]
    response: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str]
    locked_until: Mapped[datetime]
    attempt_id: Mapped[UUID]
    attempts: Mapped[int] = mapped_column(default=0)
