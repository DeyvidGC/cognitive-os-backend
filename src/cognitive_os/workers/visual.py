from pathlib import Path
import json
from tempfile import TemporaryDirectory
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cognitive_os.application.recordings import archive_report, validate_sources
from cognitive_os.infrastructure.ai.openai_visual import PROMPT_VERSION
from cognitive_os.infrastructure.database.models import (
    AgentTurn, AuditEvent, Clarification, LearningSession, Recording, RecordingReport, SessionEvent,
)
from cognitive_os.infrastructure.storage.azure_recordings import recording_store
from cognitive_os.infrastructure.video import extract_frames
from cognitive_os.schemas.recordings import VisualReportContent
from cognitive_os.workers.consolidation import claim_job, fail_claim, owned_job, set_stage


class VisualState(TypedDict, total=False):
    objective: str
    sampling: dict
    report: VisualReportContent
    context: dict


def visual_graph(provider, directory):
    def analyze(state):
        return {"report": provider.analyze(state["objective"], state["sampling"], directory, state.get("context", {}))}

    def validate(state):
        report = VisualReportContent.model_validate(state["report"])
        validate_sources(report, state["sampling"])
        return {"report": report}

    graph = StateGraph(VisualState)
    graph.add_node("analyze_frames", analyze)
    graph.add_node("validate_report", validate)
    graph.add_edge(START, "analyze_frames")
    graph.add_edge("analyze_frames", "validate_report")
    graph.add_edge("validate_report", END)
    return graph.compile()


def save_report(engine, claim, report, sampling, model_name):
    with Session(engine) as db, db.begin():
        job = owned_job(db, claim)
        session = db.scalar(select(LearningSession).where(
            LearningSession.id == claim.session_id,
            LearningSession.organization_id == claim.organization_id).with_for_update())
        recording = db.scalar(select(Recording).where(
            Recording.id == claim.recording_id,
            Recording.organization_id == claim.organization_id).with_for_update())
        if not session or session.status != "processing" or not recording or recording.status != "processing":
            raise ValueError("Recording no longer processing")
        validate_sources(report, sampling)
        metadata = {**sampling, "frames": [{"index": f["index"], "timestamp_ms": f["timestamp_ms"]}
                                           for f in sampling["frames"]]}
        data = report.model_dump(mode="json")
        existing = db.scalar(select(RecordingReport).where(RecordingReport.recording_id == recording.id,
                               RecordingReport.organization_id == claim.organization_id).with_for_update())
        if existing:
            if existing.review_status == "approved":
                raise ValueError("Approved report cannot be overwritten")
            archive_report(db, existing)
            existing.content = existing.original_content = data
            existing.sampling = metadata
            existing.model_name, existing.prompt_version = model_name, PROMPT_VERSION
            existing.revision += 1
            existing.review_status = "pending"
            existing.feedback = existing.reviewed_at = existing.reviewer_id = None
        else:
            db.add(RecordingReport(recording_id=recording.id, organization_id=claim.organization_id,
                                   content=data, original_content=data, sampling=metadata,
                                   model_name=model_name, prompt_version=PROMPT_VERSION))
        questions = set(db.scalars(select(Clarification.question).where(
            Clarification.organization_id == claim.organization_id, Clarification.session_id == session.id)))
        for question in report.questions:
            if question.strip() and question not in questions:
                db.add(Clarification(organization_id=claim.organization_id, session_id=session.id,
                                      question=question[:4000]))
                questions.add(question)
        recording.status, recording.error_code = "ready", None
        session.status = "completed"
        job.status = "completed"
        job.stage, job.progress_percent = "completed", 100
        job.completed_at = db.scalar(select(func.clock_timestamp()))
        job.locked_by = job.locked_until = job.last_error = None
        db.add(AuditEvent(organization_id=claim.organization_id, actor_id=None,
                          action="recording.report_generated", resource_type="recording",
                          resource_id=recording.id, details={"job_id": str(job.id), "frames": len(sampling["frames"])}))


def run_visual_once(engine, provider, settings, organization_id=None):
    claim = claim_job(engine, settings.recording_lease_seconds, organization_id, "analyze_recording")
    if claim is None:
        return False
    try:
        with Session(engine, expire_on_commit=False) as db, db.begin():
            owned_job(db, claim)
            session = db.scalar(select(LearningSession).where(
                LearningSession.id == claim.session_id,
                LearningSession.organization_id == claim.organization_id))
            recording = db.scalar(select(Recording).where(
                Recording.id == claim.recording_id,
                Recording.organization_id == claim.organization_id).with_for_update())
            if not session or session.status != "processing" or not recording or not recording.blob_snapshot:
                raise ValueError("Recording unavailable")
            if recording.size_bytes > settings.recording_max_bytes:
                raise ValueError("Recording exceeds worker size limit")
            recording.status = "processing"
            objective = session.objective
            notes = db.scalars(select(SessionEvent).where(
                SessionEvent.organization_id == claim.organization_id, SessionEvent.session_id == session.id,
                SessionEvent.event_type.in_(["message", "transcript"])).order_by(SessionEvent.sequence_number).limit(201)).all()
            turns = db.scalars(select(AgentTurn).where(AgentTurn.organization_id == claim.organization_id,
                AgentTurn.session_id == session.id).order_by(AgentTurn.created_at).limit(121)).all()
            answers = db.scalars(select(Clarification).where(Clarification.organization_id == claim.organization_id,
                Clarification.session_id == session.id, Clarification.resolved_at.is_not(None)).limit(101)).all()
            if len(notes) > 200 or len(turns) > 120 or len(answers) > 100:
                raise ValueError("Too much context for visual analysis")
            context = {"notes": [e.payload.get("text", "") for e in notes] + [t.user_text for t in turns if t.user_text],
                       "clarifications": [{"question": a.question, "answer": a.answer} for a in answers]}
        with TemporaryDirectory(prefix="cognitive-video-") as temp:
            directory = Path(temp)
            video = directory / ("capture.webm" if recording.media_type == "video/webm" else "capture.mp4")
            set_stage(engine, claim, "downloading", 10)
            with recording_store(settings) as store:
                store.download(recording, video)
            set_stage(engine, claim, "extracting", 25)
            sampling = extract_frames(video, directory, recording.media_type, settings)
            if sampling.get("audio_present") and recording.audio_consent:
                set_stage(engine, claim, "transcribing", 45)
                context["transcript"] = provider.transcribe(directory / "audio.wav")
                sampling["audio_analyzed"] = True
                sampling["transcript"] = context["transcript"]
                sampling["transcription_model"] = provider.transcription_model
            elif sampling.get("audio_present"):
                sampling["audio_exclusion_reason"] = "audio_consent_not_granted"
            if len(json.dumps(context).encode("utf-8")) > 200000:
                raise ValueError("Analysis context exceeds limit")
            sampling["text_sources"] = [name for name, value in context.items() if value]
            set_stage(engine, claim, "analyzing", 65)
            result = visual_graph(provider, directory).invoke({"objective": objective, "sampling": sampling, "context": context})
            set_stage(engine, claim, "saving", 90)
            save_report(engine, claim, result["report"], sampling, provider.model_name)
    except Exception as exc:
        fail_claim(engine, claim, exc)
    return True
