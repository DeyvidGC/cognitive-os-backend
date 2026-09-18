from uuid import UUID, uuid4
from types import SimpleNamespace
import wave

import av
from PIL import Image
import pytest
from sqlalchemy.orm import Session

from cognitive_os.core.config import Settings
from cognitive_os.infrastructure.database.models import ProcedureVersion
from cognitive_os.infrastructure.video import extract_frames, VideoDurationExceeded
from cognitive_os.infrastructure.ai.openai_visual import OpenAIVisualProvider
from cognitive_os.schemas.agent import AgentReply
from test_recordings import video_file, storage, prepare_report, run_video


def test_thirty_minute_decode_and_duration_error(tmp_path):
    video = tmp_path / 'long.mp4'
    with av.open(str(video), 'w') as output:
        stream = output.add_stream('mpeg4', rate=1)
        stream.width = stream.height = 16
        stream.pix_fmt = 'yuv420p'
        for _ in range(1800):
            frame = av.VideoFrame.from_image(Image.new('RGB', (16, 16)))
            for packet in stream.encode(frame):
                output.mux(packet)
        for packet in stream.encode():
            output.mux(packet)
    settings = Settings(_env_file=None, recording_frame_interval_seconds=5)
    sampling = extract_frames(video, tmp_path, 'video/mp4', settings)
    assert sampling['duration_ms'] >= 1799000
    assert len(sampling['frames']) <= 122
    assert sampling['frame_interval_seconds'] == 15
    with pytest.raises(VideoDurationExceeded):
        extract_frames(video, tmp_path, 'video/mp4', settings.model_copy(update={'recording_max_seconds': 600}))


def test_long_audio_is_transcribed_in_order_in_bounded_chunks(tmp_path):
    path = tmp_path / 'audio.wav'
    with wave.open(str(path), 'wb') as output:
        output.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        for _ in range(1800):
            output.writeframes(b'\0' * 32000)
    sizes = []
    def transcribe(**kwargs):
        sizes.append(len(kwargs['file'].read()))
        return SimpleNamespace(text=f'Parte {len(sizes)}')
    provider = object.__new__(OpenAIVisualProvider)
    provider.transcription_model = 'fake'
    provider.client = SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=transcribe)))
    assert provider.transcribe(path) == 'Parte 1\nParte 2\nParte 3'
    assert len(sizes) == 3 and max(sizes) < 20_000_000


def test_history_and_new_version_preserve_prior_version(api, account, storage):
    owner = account()
    headers = owner['headers']
    session_id, recording_id, report = prepare_report(api, owner, storage)
    path = f'/api/v1/recordings/{recording_id}'
    assert api.post(path + '/report/review', headers=headers, json={
        'revision': report['revision'], 'decision': 'approved'}).status_code == 200
    first = api.post(path + '/procedure', headers=headers).json()
    procedure_id = first['procedure_id']
    # A later conversion must never mutate an existing published version.
    with Session(api.app.state.engine) as db:
        old = db.get(ProcedureVersion, UUID(first['id']))
        old.status = 'published'
        from datetime import datetime, UTC
        old.reviewer_id = UUID(owner['id'])
        old.approved_at = old.published_at = datetime.now(UTC)
        db.commit()
    response = api.post('/api/v1/learning-sessions', headers=headers, json={
        'objective': 'Actualización mensual', 'application_name': 'Demo', 'consent': True,
        'procedure_id': procedure_id})
    assert response.status_code == 201, response.text
    next_session = response.json()['id']
    uploaded = api.post(f'/api/v1/learning-sessions/{next_session}/recordings', headers=headers, json={
        'idempotency_key': str(uuid4()), 'media_type': 'video/mp4', 'size_bytes': 100,
        'consent': True, 'title': 'Cambio mensual', 'origin': 'upload'}).json()
    next_path = '/api/v1/recordings/' + uploaded['id']
    api.post(next_path + '/complete', headers=headers)
    assert api.post(next_path + '/process', headers=headers).status_code == 202
    run_video(api, owner)
    report = api.get(next_path + '/report', headers=headers).json()
    api.post(next_path + '/report/review', headers=headers, json={'revision': report['revision'], 'decision': 'approved'})
    second = api.post(next_path + '/procedure', headers=headers).json()
    assert second['procedure_id'] == procedure_id
    assert second['version_number'] == 2 and second['status'] == 'draft'
    assert api.post(next_path + '/procedure', headers=headers).json()['id'] == second['id']
    with Session(api.app.state.engine) as db:
        assert db.get(ProcedureVersion, UUID(first['id'])).status == 'published'
    page = api.get('/api/v1/recordings', headers=headers, params={'limit': 1, 'procedure_id': procedure_id}).json()
    assert page['items'][0]['origin'] == 'upload' and page['next_cursor']
    older = api.get('/api/v1/recordings', headers=headers, params={'limit': 1, 'cursor': page['next_cursor']}).json()
    assert older['items'][0]['id'] == recording_id and older['next_cursor'] is None
    assert len(api.get('/api/v1/recordings?query=Cambio', headers=headers).json()['items']) == 1
    outsider = account()
    assert api.get('/api/v1/recordings', headers=outsider['headers']).json()['items'] == []
    assert api.post('/api/v1/learning-sessions', headers=outsider['headers'], json={
        'objective': 'Otra', 'application_name': 'Demo', 'consent': True, 'procedure_id': procedure_id}).status_code == 404


def test_proactive_question_persists_once_and_answer_is_linked(api, account, monkeypatch):
    class Agent:
        def __init__(self, settings): pass
        def close(self): pass
        def respond(self, *args):
            return AgentReply(observation='Formulario', answer='', questions=['¿Cuál es la regla?'])
    monkeypatch.setattr('cognitive_os.api.v1.endpoints.agent.OpenAILiveProvider', Agent)
    api.app.state.settings.agent_min_interval_seconds = 1
    owner = account()
    headers = owner['headers']
    sid = api.post('/api/v1/learning-sessions', headers=headers, json={
        'objective': 'Demo', 'application_name': 'Demo', 'consent': True}).json()['id']
    with api.websocket_connect(f'/api/v1/learning-sessions/{sid}/agent/live') as ws:
        ws.send_json({'type': 'auth', 'token': owner['token'], 'organization_id': owner['organization_id'], 'consent': True})
        assert ws.receive_json()['proactive_questions'] is True
        message = {'type': 'observe', 'message_id': str(uuid4()), 'text': 'Observar', 'offset_ms': 15000}
        for _ in range(2):
            ws.send_json(message)
            assert ws.receive_json()['type'] == 'processing'
            reply = ws.receive_json()['reply']
        question_id = reply['clarifications'][0]['clarification_id']
        questions = api.get(f'/api/v1/learning-sessions/{sid}/clarifications', headers=headers).json()
        assert len(questions) == 1 and questions[0]['id'] == question_id
        # Avoid wall-clock sleeps: age the prior completed turn.
        from cognitive_os.infrastructure.database.models import AgentTurn
        from sqlalchemy import update
        from datetime import datetime, UTC, timedelta
        with Session(api.app.state.engine) as db:
            db.execute(update(AgentTurn).where(AgentTurn.session_id == UUID(sid)).values(created_at=datetime.now(UTC) - timedelta(seconds=5)))
            db.commit()
        answer = {'type': 'message', 'message_id': str(uuid4()), 'text': 'Validar el monto', 'clarification_id': question_id}
        ws.send_json(answer)
        ws.receive_json()
        assert ws.receive_json()['reply']['questions'] == []
        ws.send_json(answer)
        ws.receive_json()
        assert ws.receive_json()['type'] == 'reply'
    questions = api.get(f'/api/v1/learning-sessions/{sid}/clarifications', headers=headers).json()
    assert len(questions) == 1 and questions[0]['answer'] == 'Validar el monto'
