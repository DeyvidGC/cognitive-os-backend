import asyncio
import base64
import json

from cognitive_os.core.config import Settings
from cognitive_os.infrastructure.ai.openai_realtime import OpenAIRealtimeSession


class Socket:
    def __init__(self):
        self.sent = []
        self.incoming = []

    async def send(self, raw):
        self.sent.append(json.loads(raw))

    async def __aiter__(self):
        while self.incoming:
            yield json.dumps(self.incoming.pop(0))


def make_session():
    session = OpenAIRealtimeSession(Settings(_env_file=None, openai_api_key="test-key"))
    session._socket = Socket()
    return session, session._socket


def decision(action="listen", text="", status="completed"):
    return {"type": "response.done", "response": {"status": status, "output": [{
        "type": "function_call", "name": "decide_next_action", "call_id": "call-1",
        "arguments": json.dumps({"action": action, "text": text}),
    }]}}


async def drain(session):
    return [event async for event in session.events()]


def test_frames_analyze_silently_and_coalesce_while_busy():
    async def run():
        session, socket = make_session()
        await session.push_frame("image-one")
        await session.push_frame("image-two")
        await session.push_frame("image-three")
        responses = [e for e in socket.sent if e["type"] == "response.create"]
        assert len(responses) == 1
        assert responses[0]["response"]["output_modalities"] == ["text"]
        socket.incoming = [decision()]
        await drain(session)
        responses = [e for e in socket.sent if e["type"] == "response.create"]
        assert len(responses) == 2
        assert all(e["response"]["output_modalities"] == ["text"] for e in responses)
    asyncio.run(run())


def test_speech_defers_observation_until_transcription_and_interrupt_truncates():
    async def run():
        session, socket = make_session()
        socket.incoming = [{"type": "input_audio_buffer.speech_started"}]
        await drain(session)
        await session.push_frame("image")
        assert not any(e["type"] == "response.create" for e in socket.sent)
        socket.incoming = [
            {"type": "input_audio_buffer.speech_stopped"},
            {"type": "conversation.item.input_audio_transcription.completed", "transcript": "¿Tienes dudas?"},
        ]
        await drain(session)
        assert socket.sent[-1]["type"] == "response.create"
        socket.incoming = [{"type": "response.created", "response": {"id": "response-1"}},
                           {"type": "response.output_audio.delta", "item_id": "audio-1",
                            "delta": base64.b64encode(bytes(48000)).decode()}]
        await drain(session)
        await session.interrupt("audio-1", 5000)
        assert socket.sent[-2]["type"] == "response.cancel"
        assert socket.sent[-1] == {"type": "conversation.item.truncate", "item_id": "audio-1",
                                   "content_index": 0, "audio_end_ms": 1000}
        await session.interrupt("untrusted-id", 100)
        assert socket.sent[-1]["type"] == "conversation.item.truncate"
    asyncio.run(run())


def test_question_speaks_only_after_acceptance_and_rejection_stays_silent():
    async def run(accepted):
        session, socket = make_session()
        socket.incoming = [decision("question", "¿Qué campo cambiaste?")]
        async for event in session.events():
            if event.get("name") == "ask_clarifying_question":
                # A frame arriving during database persistence must not start another response.
                await session.push_frame("new-image")
                assert not any(e["type"] == "response.create" for e in socket.sent)
                await session.submit_tool_result(event["call_id"], accepted)
        responses = [e for e in socket.sent if e["type"] == "response.create"]
        assert responses[-1]["response"]["output_modalities"] == (["audio"] if accepted else ["text"])
    asyncio.run(run(True))
    asyncio.run(run(False))


def test_cancelled_decision_never_speaks_and_explicit_answer_does():
    async def run(status):
        session, socket = make_session()
        socket.incoming = [decision("answer", "No tengo dudas por ahora.", status)]
        await drain(session)
        responses = [e for e in socket.sent if e["type"] == "response.create"]
        assert len(responses) == (1 if status == "completed" else 0)
        if responses:
            assert responses[0]["response"]["output_modalities"] == ["audio"]
    asyncio.run(run("cancelled"))
    asyncio.run(run("completed"))


def test_connect_disables_automatic_speech_but_keeps_vad_interruptions(monkeypatch):
    async def run():
        session, socket = make_session()
        async def connect(*args, **kwargs):
            return socket
        monkeypatch.setattr("cognitive_os.infrastructure.ai.openai_realtime.websockets.connect", connect)
        await session.connect("Learn the process")
        vad = socket.sent[0]["session"]["audio"]["input"]["turn_detection"]
        assert vad["interrupt_response"] is True
        assert vad["create_response"] is False
    asyncio.run(run())
