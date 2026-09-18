from copy import deepcopy
from types import SimpleNamespace
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from PIL import Image
import pytest

from cognitive_os.application.bpmn import NS, report_bpmn
from cognitive_os.application.report_exports import export_document, EXPORT_SLOTS
from cognitive_os.core.config import Settings
from cognitive_os.domain.errors import ApplicationError
from cognitive_os.infrastructure.report_documents import build_document, document_blocks


@pytest.fixture
def snapshot():
    return {"recording_id": "demo-recording", "revision": 3, "review_status": "pending",
            "reviewed_at": None, "model_name": "test-provider", "clarifications": [
                {"question": "Cuando continuar?", "answer": "Despues de revisar los datos."}],
            "sampling": {"frames": [{"timestamp_ms": 5000}], "frame_interval_seconds": 5},
            "content": {"title": "Registrar una solicitud", "summary": "Revisar y registrar datos.",
                        "report": "El usuario verifica los campos antes de guardar.", "uncertainties": ["Validar permisos."],
                        "instructions": [
                            {"instruction": "Revisar datos <del formulario> & confirmar", "expected_result": "Datos correctos",
                             "frame_indices": [0], "alternatives": [
                                 {"condition": "Datos validos", "target_step": 2},
                                 {"condition": "Datos incompletos", "target_step": None}]},
                            {"instruction": "Guardar solicitud", "expected_result": "Solicitud guardada",
                             "frame_indices": [], "text_sources": ["clarifications"]}]}}


def test_bpmn_human_tasks_and_separate_decision(snapshot):
    root = ET.fromstring(report_bpmn(SimpleNamespace(**snapshot)))
    assert len(root.findall(".//bpmn:userTask", NS)) == 2
    assert len(root.findall(".//bpmn:exclusiveGateway", NS)) == 1
    assert len(root.findall(".//bpmn:startEvent", NS)) == 1
    assert root.find("bpmn:process", NS).attrib["isExecutable"] == "false"
    flows = root.findall(".//bpmn:sequenceFlow", NS)
    assert any(f.attrib["sourceRef"] == "decision-1" and f.attrib["targetRef"] == "end" for f in flows)
    ids = {element.attrib["id"] for element in root.iter() if "id" in element.attrib}
    for flow in flows:
        assert flow.attrib["sourceRef"] in ids and flow.attrib["targetRef"] in ids
    assert len(root.findall(".//bpmndi:BPMNEdge", NS)) == len(flows)
    assert root.find(".//bpmn:userTask", NS).attrib["name"].endswith("<del formulario> & confirmar")


@pytest.mark.parametrize("format", ["docx", "pdf"])
def test_documents_include_real_image_answers_and_draft(snapshot, tmp_path, format):
    frame = tmp_path / "frame.jpg"
    Image.new("RGB", (1280, 720), "#308090").save(frame)
    path = tmp_path / f"report.{format}"
    frames = {0: (frame, 5000)}
    build_document(snapshot, frames, path, format=format, style="report")
    blocks = document_blocks(snapshot, frames, "report")
    assert ("image", frame) in blocks
    assert any("00:05.000" in str(value) for _, value in blocks)
    assert any("Despues de revisar" in str(value) for _, value in blocks)
    assert any("BORRADOR" in str(value) for _, value in blocks)
    if format == "docx":
        with ZipFile(path) as archive:
            assert any(name.startswith("word/media/") for name in archive.namelist())
            xml = archive.read("word/document.xml").decode()
            assert "BORRADOR" in xml and "&lt;del formulario&gt;" in xml
    else:
        assert path.read_bytes().startswith(b"%PDF-")
        assert b"/Subtype /Image" in path.read_bytes()


def test_approved_document_status(snapshot):
    snapshot["review_status"] = "approved"
    snapshot["content"]["instructions"][0]["frame_indices"] = []
    blocks = document_blocks(snapshot, {}, "tutorial")
    assert any("APROBADO" in str(value) for _, value in blocks)
    assert not any("BORRADOR" in str(value) for _, value in blocks)


def test_export_concurrency_limit(snapshot):
    EXPORT_SLOTS.acquire()
    EXPORT_SLOTS.acquire()
    try:
        with pytest.raises(ApplicationError, match="busy"):
            export_document(snapshot, None, Settings(_env_file=None), format="pdf", style="tutorial")
    finally:
        EXPORT_SLOTS.release()
        EXPORT_SLOTS.release()


def test_export_rejects_mismatched_frame_without_fabricating(snapshot, monkeypatch):
    from contextlib import contextmanager

    @contextmanager
    def storage(settings):
        yield SimpleNamespace(ensure_private=lambda: None, download=lambda recording, target: None)

    monkeypatch.setattr("cognitive_os.application.report_exports.recording_store", storage)
    monkeypatch.setattr("cognitive_os.application.report_exports.extract_frames",
                        lambda *args: {"frames": [{"timestamp_ms": 6000}]})
    source = SimpleNamespace(blob_snapshot="frozen", media_type="video/mp4")
    with pytest.raises(ApplicationError, match="no longer match"):
        export_document(deepcopy(snapshot), source, Settings(_env_file=None), format="pdf", style="tutorial")
