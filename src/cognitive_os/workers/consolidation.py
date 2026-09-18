"""PostgreSQL job leases and atomic draft persistence, without network calls in transactions."""

import json
import logging
import subprocess
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session
from openai import APIStatusError, APIConnectionError, APITimeoutError
from cognitive_os.domain.errors import ApplicationError

from cognitive_os.application.orchestration import PROMPT_VERSION, build_draft_graph
from cognitive_os.infrastructure.database.models import (
    AuditEvent, Job, LearningSession, Procedure, ProcedureVersion, Recording, SessionEvent, Step, Tutorial,
)


@dataclass(frozen=True)
class Claim:
    job_id: UUID
    organization_id: UUID
    session_id: UUID
    token: str
    recording_id: UUID | None = None


def set_stage(engine, claim, stage, progress):
    with Session(engine) as db, db.begin():
        job = owned_job(db, claim)
        job.stage, job.progress_percent = stage, progress


def classify_failure(exc, job):
    from cognitive_os.infrastructure.video import VideoDurationExceeded
    if isinstance(exc, VideoDurationExceeded):
        return "recording_duration_exceeded", False
    if isinstance(exc, APIStatusError):
        if exc.status_code == 401:
            return "ai_authentication_failed", False
        if exc.status_code in {403, 404}:
            return "ai_model_access_denied", False
        if exc.status_code == 429:
            if getattr(exc, "code", None) == "insufficient_quota":
                return "ai_quota_exhausted", False
            return "ai_rate_limited", True
        if exc.status_code == 400:
            return "ai_request_rejected", False
        return "ai_service_unavailable", True
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return "ai_connection_failed", True
    if isinstance(exc, (subprocess.CalledProcessError, subprocess.TimeoutExpired)):
        return "video_decode_failed", False
    if isinstance(exc, ApplicationError) and job.stage == "downloading":
        return "storage_unavailable", True
    if isinstance(exc, ValueError) and job.stage == "downloading":
        return "recording_integrity_failed", False
    if isinstance(exc, ValueError) and job.stage in {"analyzing", "validating"}:
        return "analysis_validation_failed", True
    return ("recording_index_failed" if job.kind == "index_recording" else
            "recording_analysis_failed" if job.recording_id else "consolidation_failed"), True


def mark_failed_session(db, job):
    if job.kind == "index_recording":
        return
    session = db.scalar(select(LearningSession).where(
        LearningSession.id == job.session_id,
        LearningSession.organization_id == job.organization_id).with_for_update())
    if session and session.status == "processing":
        session.status = "failed"
    if job.recording_id:
        recording = db.scalar(select(Recording).where(Recording.id == job.recording_id,
                                  Recording.organization_id == job.organization_id).with_for_update())
        if recording:
            recording.status = "failed"
            recording.error_code = job.last_error or "recording_analysis_failed"


def claim_job(engine, lease_seconds=300, organization_id=None, kind="consolidate"):
    with Session(engine) as db, db.begin():
        now = db.scalar(select(func.clock_timestamp()))
        # Skip locked rows allows independent workers to claim separate jobs.
        query = select(Job).where(
            Job.kind == kind,
            or_(and_(Job.status == "pending", Job.available_at <= now),
                and_(Job.status == "running", Job.locked_until <= now)),
        )
        if organization_id is not None:
            query = query.where(Job.organization_id == organization_id)
        job = db.scalar(query.order_by(Job.available_at, Job.id).with_for_update(skip_locked=True).limit(1))
        if job is None:
            return None
        if job.attempts >= job.max_attempts:
            job.status = "failed"
            job.stage = "failed"
            job.last_error = "attempts_exhausted"
            job.completed_at = now
            job.locked_by = job.locked_until = None
            mark_failed_session(db, job)
            return None
        token = uuid4().hex
        job.status = "running"
        job.stage, job.progress_percent = "starting", 1
        job.attempts += 1
        job.locked_by = token
        job.locked_until = now + timedelta(seconds=lease_seconds)
        return Claim(job.id, job.organization_id, job.session_id, token, job.recording_id)


def owned_job(db, claim):
    job = db.scalar(select(Job).where(
        Job.id == claim.job_id, Job.organization_id == claim.organization_id,
    ).with_for_update())
    now = db.scalar(select(func.clock_timestamp()))
    if (job is None or job.status != "running" or job.locked_by != claim.token
            or job.locked_until <= now):
        raise ValueError("Job lease lost")
    return job


def load_source(engine, claim):
    with Session(engine) as db:
        session = db.scalar(select(LearningSession).where(
            LearningSession.id == claim.session_id,
            LearningSession.organization_id == claim.organization_id))
        if session is None or session.status != "processing":
            raise ValueError("Session is not processing")
        events = db.scalars(select(SessionEvent).where(
            SessionEvent.session_id == claim.session_id,
            SessionEvent.organization_id == claim.organization_id,
            SessionEvent.event_type.in_(["message", "transcript"]),
        ).order_by(SessionEvent.sequence_number).limit(201)).all()
        if not events or len(events) > 200:
            raise ValueError("Text capture must contain between 1 and 200 events")
        source = {"objective": session.objective, "application": session.application_name,
                  "events": [{"id": str(e.id), "text": e.payload.get("text", "")} for e in events]}
        if len(json.dumps(source).encode("utf-8")) > 100_000:
            raise ValueError("Capture exceeds input limit")
        return source


def save_draft(engine, claim, draft, model_name):
    with Session(engine) as db, db.begin():
        job = owned_job(db, claim)
        session = db.scalar(select(LearningSession).where(
            LearningSession.id == claim.session_id,
            LearningSession.organization_id == claim.organization_id).with_for_update())
        if session is None or session.status != "processing" or job.version_id is not None:
            raise ValueError("Session or job cannot receive a draft")
        if session.procedure_id:
            procedure = db.scalar(select(Procedure).where(
                Procedure.id == session.procedure_id,
                Procedure.organization_id == claim.organization_id).with_for_update())
            if procedure is None:
                raise ValueError("Procedure no longer available")
        else:
            procedure = Procedure(organization_id=claim.organization_id, title=draft.title,
                                  scope=session.objective)
            db.add(procedure)
            db.flush()
            session.procedure_id = procedure.id
        number = db.scalar(select(func.max(ProcedureVersion.version_number)).where(
            ProcedureVersion.organization_id == claim.organization_id,
            ProcedureVersion.procedure_id == procedure.id)) or 0
        version = ProcedureVersion(organization_id=claim.organization_id, procedure_id=procedure.id,
                                   source_session_id=session.id, version_number=number + 1,
                                   summary=draft.summary, model_name=model_name,
                                   prompt_version=PROMPT_VERSION, status="draft")
        db.add(version)
        db.flush()
        sources = {}
        tutorial = [f"# {draft.title}", draft.summary]
        for position, item in enumerate(draft.steps, 1):
            step = Step(organization_id=claim.organization_id, version_id=version.id,
                        position=position, instruction=item.instruction,
                        expected_result=item.expected_result, origin="user_explained",
                        validation_status="pending")
            db.add(step)
            db.flush()
            sources[str(step.id)] = [str(event_id) for event_id in item.source_event_ids]
            tutorial.append(f"## {position}. Paso\n{item.instruction}\n\nResultado esperado: {item.expected_result}")
        db.add(Tutorial(organization_id=claim.organization_id, version_id=version.id,
                        format="markdown", content="\n\n".join(tutorial)))
        db.add(AuditEvent(organization_id=claim.organization_id, actor_id=None,
                          action="ai.draft_created", resource_type="procedure_version",
                          resource_id=version.id, details={"job_id": str(job.id),
                                                         "source_event_ids_by_step": sources}))
        job.version_id = version.id
        job.status = "completed"
        job.stage, job.progress_percent = "completed", 100
        job.completed_at = db.scalar(select(func.clock_timestamp()))
        job.locked_until = job.locked_by = job.last_error = None
        session.status = "completed"
        return version.id


def fail_claim(engine, claim, exc=None):
    with Session(engine) as db, db.begin():
        try:
            job = owned_job(db, claim)
        except ValueError:
            return
        now = db.scalar(select(func.clock_timestamp()))
        # Never persist exception strings: SDK/DB errors may include sensitive input.
        job.last_error, retryable = classify_failure(exc, job)
        logging.getLogger(__name__).warning("Job %s failed: %s", job.id, job.last_error)
        job.locked_by = job.locked_until = None
        if not retryable or job.attempts >= job.max_attempts:
            job.status = "failed"
            job.stage = "failed"
            job.completed_at = now
            mark_failed_session(db, job)
        else:
            job.status = "pending"
            job.stage = "retry_wait"
            job.available_at = now + timedelta(seconds=min(300, 10 * 2 ** job.attempts))
            if job.recording_id and job.kind == "analyze_recording":
                recording = db.scalar(select(Recording).where(Recording.id == job.recording_id,
                                     Recording.organization_id == job.organization_id).with_for_update())
                if recording:
                    recording.status = "queued"
                    recording.error_code = "recording_analysis_retrying"


def run_once(engine, provider, lease_seconds=300, organization_id=None):
    claim = claim_job(engine, lease_seconds, organization_id)
    if claim is None:
        return False
    try:
        source = load_source(engine, claim)
        result = build_draft_graph(provider).invoke({"source": source})
        save_draft(engine, claim, result["draft"], provider.model_name)
    except Exception as exc:
        fail_claim(engine, claim, exc)
    return True
