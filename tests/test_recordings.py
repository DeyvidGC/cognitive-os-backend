from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import av
import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from cognitive_os.core.config import Settings
from cognitive_os.infrastructure.database.models import Job, Recording, RecordingReport, ReportRevision
from cognitive_os.schemas.recordings import VisualReportContent


@pytest.fixture
def video_file(tmp_path):
    path = tmp_path / "test.mp4"
    with av.open(str(path), mode="w") as output:
        stream = output.add_stream("mpeg4", rate=1)
        stream.width, stream.height, stream.pix_fmt = 64, 64, "yuv420p"
        for i in range(3):
            frame = av.VideoFrame.from_image(Image.new("RGB", (64, 64), (i * 40, 80, 100)))
            for packet in stream.encode(frame):
                output.mux(packet)
        for packet in stream.encode():
            output.mux(packet)
    return path


@pytest.fixture
def storage(monkeypatch, video_file):
    class Store:
        freeze_calls = 0
        fail_freeze = False

        def transfer(self, item, write=False):
            return {"url": "https://example.invalid/test?fake-sas", "method": "PUT" if write else "GET",
                    "expires_at": datetime.now(UTC) + timedelta(minutes=5), "headers": {}}

        def freeze(self, item):
            from cognitive_os.domain.errors import ApplicationError
            if self.fail_freeze:
                raise ApplicationError(409, "Uploaded video size or blob type does not match reservation")
            self.freeze_calls += 1
            return "snapshot-1"

        def download(self, item, target):
            target.write_bytes(video_file.read_bytes())

    store = Store()
    @contextmanager
    def factory(settings):
        yield store
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.recordings.recording_store", factory)
    monkeypatch.setattr("cognitive_os.workers.visual.recording_store", factory)
    return store


def create(api, owner, size=100):
    session = api.post("/api/v1/learning-sessions", headers=owner["headers"], json={
        "objective": "Enseniar formulario", "application_name": "Demo", "consent": True}).json()
    data = {"idempotency_key": str(uuid4()), "media_type": "video/mp4", "size_bytes": size, "consent": True}
    response = api.post(f"/api/v1/learning-sessions/{session['id']}/recordings", headers=owner["headers"], json=data)
    assert response.status_code == 201, response.text
    return session["id"], response.json()["id"], data


def content(questions=None):
    return VisualReportContent(title="Formulario", summary="Completar formulario", report="Se observa el formulario.",
        instructions=[{"instruction": "Revisar formulario", "expected_result": "Datos revisados", "frame_indices": [0]}],
        uncertainties=["Solo se revisaron fotogramas muestreados"], questions=questions or [])


class Provider:
    model_name = "fake-luna"
    transcription_model = "fake-transcriber"
    questions = []
    last_context = None

    def analyze(self, objective, sampling, directory, context):
        self.last_context = context
        return content(self.questions)

    def transcribe(self, path):
        return "Explicacion del formulario"


def run_video(api, owner, provider=None):
    from cognitive_os.workers.visual import run_visual_once
    assert run_visual_once(api.app.state.engine, provider or Provider(), api.app.state.settings,
                            UUID(owner["organization_id"]))


def prepare_report(api, owner, storage, provider=None):
    session_id, recording_id, data = create(api, owner)
    path = f"/api/v1/recordings/{recording_id}"
    assert api.post(path + "/complete", headers=owner["headers"]).status_code == 200
    response = api.post(path + "/process", headers=owner["headers"])
    assert response.status_code == 202, response.text
    run_video(api, owner, provider)
    report = api.get(path + "/report", headers=owner["headers"])
    assert report.status_code == 200, report.text
    return session_id, recording_id, report.json()


def test_reservation_completion_and_access(api, account, storage):
    owner, outsider = account(), account()
    session_id, recording_id, data = create(api, owner)
    path = f"/api/v1/recordings/{recording_id}"
    same = api.post(f"/api/v1/learning-sessions/{session_id}/recordings", headers=owner["headers"], json=data)
    assert same.json()["id"] == recording_id
    data["size_bytes"] += 1
    assert api.post(f"/api/v1/learning-sessions/{session_id}/recordings", headers=owner["headers"], json=data).status_code == 409
    assert api.post(path + "/process", headers=owner["headers"]).status_code == 409
    assert api.post(path + "/upload-url", headers=owner["headers"]).status_code == 200
    assert api.get(path, headers=outsider["headers"]).status_code == 404
    reader = account(role="reader", organization_id=owner["organization_id"])
    assert api.get(path + "/playback", headers=reader["headers"]).status_code == 403
    storage.fail_freeze = True
    assert api.post(path + "/complete", headers=owner["headers"]).status_code == 409
    assert api.get(path, headers=owner["headers"]).json()["status"] == "uploading"
    storage.fail_freeze = False
    for _ in range(2):
        assert api.post(path + "/complete", headers=owner["headers"]).json()["status"] == "uploaded"
    assert storage.freeze_calls == 1
    assert api.post(path + "/upload-url", headers=owner["headers"]).status_code == 409
    assert api.get(path + "/playback", headers=owner["headers"]).status_code == 200


def test_report_edit_review_convert_and_publish(api, account, storage):
    owner = account()
    session_id, recording_id, report = prepare_report(api, owner, storage)
    path = f"/api/v1/recordings/{recording_id}"
    jobs = api.get(f"/api/v1/learning-sessions/{session_id}/jobs", headers=owner["headers"]).json()
    assert jobs[0]["recording_id"] == recording_id and jobs[0]["status"] == "completed"
    assert report["sampling"]["frames"][0]["timestamp_ms"] == 0
    assert api.post(path + "/procedure", headers=owner["headers"]).status_code == 409
    changed = report["content"]
    changed["summary"] = "Resumen validado por usuario"
    response = api.put(path + "/report", headers=owner["headers"], json={"revision": 1, "content": changed})
    assert response.status_code == 200, response.text
    assert api.put(path + "/report", headers=owner["headers"], json={"revision": 1, "content": changed}).status_code == 409
    assert api.post(path + "/report/review", headers=owner["headers"], json={"revision": 2, "decision": "approved"}).status_code == 200
    response = api.post(path + "/procedure", headers=owner["headers"])
    assert response.status_code == 201, response.text
    version_id = response.json()["id"]
    assert api.post(path + "/procedure", headers=owner["headers"]).json()["id"] == version_id
    version = f"/api/v1/procedure-versions/{version_id}"
    for action in ("submit", "approve", "publish"):
        response = api.post(version + "/" + action, headers=owner["headers"])
        assert response.status_code == 200, response.text
    assert api.post(path + "/report/regenerate", headers=owner["headers"], json={"revision": 3}).status_code == 409


def test_post_analysis_questions_and_regeneration(api, account, storage):
    owner = account()
    provider = Provider()
    provider.questions = ["Que campo se debe completar?"]
    session_id, recording_id, report = prepare_report(api, owner, storage, provider)
    path = f"/api/v1/recordings/{recording_id}"
    assert api.post(path + "/report/review", headers=owner["headers"], json={"revision": 1, "decision": "approved"}).status_code == 409
    question = api.get(f"/api/v1/learning-sessions/{session_id}/clarifications", headers=owner["headers"]).json()[0]
    assert api.put(f"/api/v1/learning-sessions/{session_id}/clarifications/{question['id']}/answer",
                   headers=owner["headers"], json={"answer": "El nombre del cliente"}).status_code == 200
    for _ in range(2):
        assert api.post(path + "/report/regenerate", headers=owner["headers"], json={"revision": 1}).status_code == 202
    run_video(api, owner, provider)
    new = api.get(path + "/report", headers=owner["headers"]).json()
    assert new["revision"] == 2 and new["review_status"] == "pending"
    assert provider.last_context["clarifications"][0]["answer"] == "El nombre del cliente"
    with Session(api.app.state.engine) as db:
        assert db.get(ReportRevision, (UUID(recording_id), 1)) is not None


def test_invalid_sources_do_not_persist_report(api, account, storage):
    class BadProvider(Provider):
        def analyze(self, *args):
            result = content()
            result.instructions[0].frame_indices = [999]
            return result
    owner = account()
    _, recording_id, _ = create(api, owner)
    path = f"/api/v1/recordings/{recording_id}"
    api.post(path + "/complete", headers=owner["headers"])
    job = api.post(path + "/process", headers=owner["headers"]).json()
    with Session(api.app.state.engine) as db, db.begin():
        db.get(Job, UUID(job["id"])).max_attempts = 1
    run_video(api, owner, BadProvider())
    assert api.get(path, headers=owner["headers"]).json()["status"] == "failed"
    assert api.get(path + "/report", headers=owner["headers"]).status_code == 404
    assert api.post(path + "/retry", headers=owner["headers"]).status_code == 202
    run_video(api, owner)
    assert api.get(path, headers=owner["headers"]).json()["status"] == "ready"


def test_decoder_rejects_invalid_video_and_reads_real_frames(tmp_path, video_file):
    from cognitive_os.infrastructure.video import extract_frames
    settings = Settings(_env_file=None)
    sampling = extract_frames(video_file, tmp_path, "video/mp4", settings)
    assert sampling["decoded_frame_count"] == 3
    assert sampling["audio_present"] is False
    invalid = tmp_path / "bad.mp4"
    invalid.write_bytes(b"not video")
    with pytest.raises(Exception):
        extract_frames(invalid, tmp_path, "video/mp4", settings)


def test_decoder_extracts_bounded_audio(tmp_path):
    import numpy as np
    import wave
    from cognitive_os.infrastructure.video import extract_frames
    path = tmp_path / "audio-video.mp4"
    with av.open(str(path), mode="w") as output:
        video = output.add_stream("mpeg4", rate=1)
        video.width, video.height, video.pix_fmt = 64, 64, "yuv420p"
        audio = output.add_stream("aac", rate=16000)
        audio.layout = "mono"
        for packet in video.encode(av.VideoFrame.from_image(Image.new("RGB", (64, 64), "red"))):
            output.mux(packet)
        for packet in video.encode():
            output.mux(packet)
        samples = av.AudioFrame.from_ndarray(np.zeros((1, 16000), dtype=np.float32), format="fltp", layout="mono")
        samples.sample_rate = 16000
        for packet in audio.encode(samples):
            output.mux(packet)
        for packet in audio.encode():
            output.mux(packet)
    metadata = extract_frames(path, tmp_path, "video/mp4", Settings(_env_file=None))
    assert metadata["audio_present"] is True
    with wave.open(str(tmp_path / "audio.wav")) as wav:
        assert wav.getframerate() == 16000 and wav.getnchannels() == 1
        assert wav.getnframes() > 0


def test_audio_and_notes_reach_visual_provider_with_consent(api, account, storage, monkeypatch):
    def frames(video, directory, media_type, settings):
        (directory / "audio.wav").write_bytes(b"fake-wave-for-provider")
        return {"frames": [{"index": 0, "timestamp_ms": 0, "file": "frame-0.jpg"}],
                "audio_present": True, "audio_analyzed": False, "frame_interval_seconds": 10}
    monkeypatch.setattr("cognitive_os.workers.visual.extract_frames", frames)
    owner = account()
    session_id, recording_id, _ = create(api, owner)
    with Session(api.app.state.engine) as db, db.begin():
        db.get(Recording, UUID(recording_id)).audio_consent = True
    api.post(f"/api/v1/learning-sessions/{session_id}/events", headers=owner["headers"], json={
        "idempotency_key": "note", "sequence_number": 1, "offset_ms": 0,
        "event_type": "message", "text": "Nota complementaria"})
    path = f"/api/v1/recordings/{recording_id}"
    api.post(path + "/complete", headers=owner["headers"])
    api.post(path + "/process", headers=owner["headers"])
    provider = Provider()
    run_video(api, owner, provider)
    assert provider.last_context["transcript"] == "Explicacion del formulario"
    assert provider.last_context["notes"] == ["Nota complementaria"]
    report = api.get(path + "/report", headers=owner["headers"]).json()
    assert report["sampling"]["audio_analyzed"] is True
