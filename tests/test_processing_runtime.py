from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import AuthenticationError, RateLimitError
from pydantic import ValidationError

from cognitive_os.application.recording_knowledge import report_flow
from cognitive_os.application.recordings import validate_sources
from cognitive_os.core.config import Settings
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.main import create_app
from cognitive_os.schemas.recordings import VisualReportContent
from cognitive_os.workers.consolidation import classify_failure


def sample():
    return dict(title="Proceso", summary="Resumen", report="Informe",
                instructions=[dict(instruction="Comprobar datos", expected_result="Datos comprobados", frame_indices=[0]),
                              dict(instruction="Corregir datos", expected_result="Datos corregidos", frame_indices=[1])],
                uncertainties=[])


def test_local_workers_lifecycle():
    with patch("cognitive_os.workers.runtime.LocalWorkers") as workers:
        settings = Settings(_env_file=None, embedded_workers=True)
        with TestClient(create_app(settings)) as client:
            workers.return_value.start.assert_called_once()
            assert client.get("/api/v1/health").status_code == 200
        workers.return_value.close.assert_called_once()


def test_conditional_graph_and_sources():
    data = sample()
    data["instructions"][0]["alternatives"] = [
        {"condition": "Datos invalidos", "target_step": 2}, {"condition": "Datos validos", "target_step": None}]
    content = VisualReportContent.model_validate(data)
    report = SimpleNamespace(content=content.model_dump(), recording_id="id", revision=1,
                             review_status="pending", sampling={"frames": [{"timestamp_ms": 0}, {"timestamp_ms": 5000}]})
    graph = report_flow(report)
    assert graph["schema_version"] == 2 and graph["kind"] == "conditional"
    assert graph["nodes"][1]["data"]["node_kind"] == "decision"
    assert {e["target"] for e in graph["edges"] if e["source"] == "step-1"} == {"step-2", "end"}
    assert graph["nodes"][2]["data"]["evidence_start_ms"] == 5000


@pytest.mark.parametrize("targets", [[1, None], [3, None], [None, None]])
def test_graph_rejects_cycles_unknown_or_unreachable_steps(targets):
    data = sample()
    data["instructions"][0]["alternatives"] = [
        {"condition": "Si", "target_step": targets[0]}, {"condition": "No", "target_step": targets[1]}]
    with pytest.raises(ValidationError):
        VisualReportContent.model_validate(data)


def test_facts_require_evidence_and_empty_graph_is_honest():
    data = sample()
    data["business_rules"] = [{"text": "Regla sin fuente"}]
    with pytest.raises(ApplicationError):
        validate_sources(VisualReportContent.model_validate(data), {"frames": [{}, {}]})
    data["instructions"] = []
    data["business_rules"] = []
    graph = report_flow(SimpleNamespace(content=data, recording_id="id", revision=1, review_status="pending", sampling={}))
    assert graph["nodes"] == [] and graph["empty_reason"] == "insufficient_evidence"


def test_failures_are_actionable_and_never_include_secrets():
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    job = SimpleNamespace(kind="analyze_recording", recording_id="id", stage="analyzing")
    error = AuthenticationError("secret", response=httpx.Response(401, request=request), body=None)
    assert classify_failure(error, job) == ("ai_authentication_failed", False)
    error = RateLimitError("secret", response=httpx.Response(429, request=request), body={"code": "insufficient_quota"})
    assert classify_failure(error, job) == ("ai_quota_exhausted", False)
