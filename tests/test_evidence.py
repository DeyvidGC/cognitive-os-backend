from io import BytesIO

from PIL import Image


def session(api, owner):
    response = api.post("/api/v1/learning-sessions", headers=owner["headers"], json={
        "objective": "Capture", "application_name": "CRM", "consent": True})
    assert response.status_code == 201
    return response.json()["id"]


def image_bytes():
    output = BytesIO()
    Image.new("RGB", (3, 3), "white").save(output, format="PNG")
    return output.getvalue()


def test_image_upload_download_and_validation(api, account, tmp_path):
    api.app.state.settings.evidence_directory = tmp_path
    owner, other = account(), account()
    session_id = session(api, owner)
    path = f"/api/v1/learning-sessions/{session_id}/evidence"
    data = image_bytes()
    response = api.post(path, headers=owner["headers"], files={"file": ("../../escape.png", data, "image/png")})
    assert response.status_code == 201, response.text
    evidence = response.json()
    assert "storage_key" not in evidence
    assert evidence["size_bytes"] == len(data)
    file_path = f"/api/v1/evidence/{evidence['id']}/file"
    assert api.get(file_path, headers=owner["headers"]).content == data
    assert api.get(file_path, headers=other["headers"]).status_code == 404
    assert len(list(tmp_path.rglob("*.png"))) == 1
    assert api.post(path, headers=owner["headers"], files={"file": ("fake.png", b"not an image", "image/png")}).status_code == 415
    api.app.state.settings.max_evidence_bytes = 1024
    assert api.post(path, headers=owner["headers"], files={"file": ("big.png", b"x" * 1025, "image/png")}).status_code == 413
    assert api.post(f"/api/v1/learning-sessions/{session_id}/finish", headers=owner["headers"]).status_code == 202
    assert api.post(path, headers=owner["headers"], files={"file": ("later.png", data, "image/png")}).status_code == 409


def test_clarifications_block_finish_until_answered(api, account):
    owner = account()
    session_id = session(api, owner)
    path = f"/api/v1/learning-sessions/{session_id}"
    assert api.post(path + "/events", headers=owner["headers"], json={
        "idempotency_key": "one", "sequence_number": 0, "offset_ms": 0,
        "event_type": "message", "text": "Describe the process"}).status_code == 200
    response = api.post(path + "/clarifications", headers=owner["headers"], json={"question": "Who approves?"})
    assert response.status_code == 201
    assert api.post(path + "/finish", headers=owner["headers"]).status_code == 409
    question_id = response.json()["id"]
    assert api.put(path + f"/clarifications/{question_id}/answer", headers=owner["headers"], json={"answer": "The supervisor"}).status_code == 200
    assert api.post(path + "/finish", headers=owner["headers"]).status_code == 202


def test_evidence_link_enables_observed_step_review(api, account, tmp_path):
    api.app.state.settings.evidence_directory = tmp_path
    owner = account()
    sid = session(api, owner)
    evidence = api.post(f"/api/v1/learning-sessions/{sid}/evidence", headers=owner["headers"],
                        files={"file": ("capture.png", image_bytes(), "image/png")}).json()
    procedure = api.post("/api/v1/procedures", headers=owner["headers"], json={"title": "Test", "scope": "Test"}).json()
    version = api.post(f"/api/v1/procedures/{procedure['id']}/versions", headers=owner["headers"], json={"source_session_id": sid}).json()
    path = f"/api/v1/procedure-versions/{version['id']}"
    step = api.post(path + "/steps", headers=owner["headers"], json={
        "position": 1, "instruction": "Click", "expected_result": "Done", "origin": "observed",
        "validation_status": "confirmed"}).json()
    assert api.put(path + "/tutorial", headers=owner["headers"], json={"content": "Reviewed guide"}).status_code == 200
    assert api.post(path + "/submit", headers=owner["headers"]).status_code == 409
    assert api.put(path + f"/steps/{step['id']}/evidence", headers=owner["headers"], json={
        "evidence_id": evidence["id"], "explanation": "Screen shows the result"}).status_code == 200
    assert api.post(path + "/submit", headers=owner["headers"]).status_code == 200
