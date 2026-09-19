from cognitive_os.infrastructure.ai.openai_change import ChangeProposalDecision
from test_procedures import ready


class Proposing:
    model_name = "fake-luna"

    def __init__(self, *args):
        pass

    def propose(self, steps, request_text):
        after = steps[-1]["position"] if steps else 0
        return ChangeProposalDecision(can_propose=True, after_position=after,
                                      instruction="Confirmar pago inicial",
                                      expected_result="Pago confirmado", rationale="Evita emitir sin pago")

    def close(self):
        pass


class Declining(Proposing):
    def propose(self, steps, request_text):
        return ChangeProposalDecision(can_propose=False)


class Editing(Proposing):
    def propose(self, steps, request_text):
        return ChangeProposalDecision(can_propose=True, kind="edit", step_position=1,
                                      instruction="Registrar cotizacion en el nuevo sistema",
                                      expected_result="Cotizacion guardada en el nuevo sistema",
                                      rationale="Cambio de sistema")


class DeletingStep1(Proposing):
    def propose(self, steps, request_text):
        return ChangeProposalDecision(can_propose=True, kind="delete", step_position=1,
                                      rationale="Paso ya no aplica")


def published(api, owner):
    procedure_id, version_id = ready(api, owner)
    path = f"/api/v1/procedure-versions/{version_id}"
    assert api.post(path + "/submit", headers=owner["headers"]).status_code == 200
    assert api.post(path + "/approve", headers=owner["headers"]).status_code == 200
    assert api.post(path + "/publish", headers=owner["headers"]).status_code == 200
    return procedure_id, version_id


def published_with_second_step(api, owner):
    procedure_id, version_id = ready(api, owner)
    path = f"/api/v1/procedure-versions/{version_id}"
    assert api.post(path + "/steps", headers=owner["headers"], json={
        "position": 2, "instruction": "Enviar cotizacion", "expected_result": "Cotizacion enviada",
        "origin": "user_explained", "validation_status": "confirmed"}).status_code == 201
    assert api.post(path + "/submit", headers=owner["headers"]).status_code == 200
    assert api.post(path + "/approve", headers=owner["headers"]).status_code == 200
    assert api.post(path + "/publish", headers=owner["headers"]).status_code == 200
    return procedure_id, version_id


def test_propose_apply_creates_new_draft_version_with_inserted_step(api, account, monkeypatch):
    owner = account()
    procedure_id, version_id = published(api, owner)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.change_proposals.OpenAIChangeProvider", Proposing)

    response = api.post(f"/api/v1/procedure-versions/{version_id}/change-proposals", headers=owner["headers"],
                        json={"request_text": "Agrega confirmar el pago inicial antes de continuar"})
    assert response.status_code == 201, response.text
    proposal = response.json()
    assert proposal["status"] == "pending" and proposal["after_position"] == 1

    reader = account(role="reader", organization_id=owner["organization_id"])
    assert api.get(f"/api/v1/procedure-versions/{version_id}/change-proposals",
                   headers=reader["headers"]).json()[0]["id"] == proposal["id"]
    assert api.post(f"/api/v1/change-proposals/{proposal['id']}/apply", headers=reader["headers"]).status_code == 403

    applied = api.post(f"/api/v1/change-proposals/{proposal['id']}/apply", headers=owner["headers"])
    assert applied.status_code == 200, applied.text
    new_version = applied.json()
    assert new_version["status"] == "draft" and new_version["version_number"] == 2

    steps = api.get(f"/api/v1/procedure-versions/{new_version['id']}/steps", headers=owner["headers"]).json()
    assert [s["instruction"] for s in steps] == ["Registrar cotizacion", "Confirmar pago inicial"]
    assert steps[1]["origin"] == "user_explained" and steps[1]["validation_status"] == "confirmed"

    original_steps = api.get(f"/api/v1/procedure-versions/{version_id}/steps", headers=owner["headers"]).json()
    assert len(original_steps) == 1, "the published version must stay untouched"

    assert api.post(f"/api/v1/change-proposals/{proposal['id']}/apply", headers=owner["headers"]).status_code == 409

    path2 = f"/api/v1/procedure-versions/{new_version['id']}"
    assert api.post(path2 + "/submit", headers=owner["headers"]).status_code == 200
    assert api.post(path2 + "/approve", headers=owner["headers"]).status_code == 200
    assert api.post(path2 + "/publish", headers=owner["headers"]).json()["status"] == "published"


def test_propose_rejects_unclear_request_and_discard_works(api, account, monkeypatch):
    owner = account()
    _, version_id = published(api, owner)
    path = f"/api/v1/procedure-versions/{version_id}/change-proposals"

    monkeypatch.setattr("cognitive_os.api.v1.endpoints.change_proposals.OpenAIChangeProvider", Declining)
    response = api.post(path, headers=owner["headers"], json={"request_text": "no se entiende"})
    assert response.status_code == 422, response.text

    monkeypatch.setattr("cognitive_os.api.v1.endpoints.change_proposals.OpenAIChangeProvider", Proposing)
    proposal = api.post(path, headers=owner["headers"], json={"request_text": "Agrega un paso"}).json()

    discarded = api.post(f"/api/v1/change-proposals/{proposal['id']}/discard", headers=owner["headers"])
    assert discarded.status_code == 200 and discarded.json()["status"] == "discarded"
    assert api.get(path, headers=owner["headers"]).json() == []


def test_propose_edit_replaces_step_text_without_touching_step_count(api, account, monkeypatch):
    owner = account()
    _, version_id = published(api, owner)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.change_proposals.OpenAIChangeProvider", Editing)

    proposal = api.post(f"/api/v1/procedure-versions/{version_id}/change-proposals", headers=owner["headers"],
                        json={"request_text": "cambia el paso 1"}).json()
    assert proposal["kind"] == "edit" and proposal["step_position"] == 1

    applied = api.post(f"/api/v1/change-proposals/{proposal['id']}/apply", headers=owner["headers"])
    assert applied.status_code == 200, applied.text
    steps = api.get(f"/api/v1/procedure-versions/{applied.json()['id']}/steps", headers=owner["headers"]).json()
    assert len(steps) == 1
    assert steps[0]["instruction"] == "Registrar cotizacion en el nuevo sistema"
    assert steps[0]["origin"] == "user_explained"


def test_propose_delete_removes_step_and_renumbers(api, account, monkeypatch):
    owner = account()
    _, version_id = published_with_second_step(api, owner)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.change_proposals.OpenAIChangeProvider", DeletingStep1)

    proposal = api.post(f"/api/v1/procedure-versions/{version_id}/change-proposals", headers=owner["headers"],
                        json={"request_text": "elimina el paso 1"}).json()
    assert proposal["kind"] == "delete" and proposal["step_position"] == 1

    applied = api.post(f"/api/v1/change-proposals/{proposal['id']}/apply", headers=owner["headers"])
    assert applied.status_code == 200, applied.text
    steps = api.get(f"/api/v1/procedure-versions/{applied.json()['id']}/steps", headers=owner["headers"]).json()
    assert [s["instruction"] for s in steps] == ["Enviar cotizacion"]
    assert steps[0]["position"] == 1


def test_delete_the_only_step_is_rejected(api, account, monkeypatch):
    owner = account()
    _, version_id = published(api, owner)
    monkeypatch.setattr("cognitive_os.api.v1.endpoints.change_proposals.OpenAIChangeProvider", DeletingStep1)

    proposal = api.post(f"/api/v1/procedure-versions/{version_id}/change-proposals", headers=owner["headers"],
                        json={"request_text": "elimina el paso 1"}).json()
    response = api.post(f"/api/v1/change-proposals/{proposal['id']}/apply", headers=owner["headers"])
    assert response.status_code == 409, response.text
