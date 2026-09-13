from concurrent.futures import ThreadPoolExecutor


def draft(api, user, procedure_id=None):
    headers = user["headers"]
    if procedure_id is None:
        response = api.post("/api/v1/procedures", headers=headers,
                            json={"title": "Cotizaciones", "scope": "Cotizacion de seguros"})
        assert response.status_code == 201, response.text
        procedure_id = response.json()["id"]
    response = api.post(f"/api/v1/procedures/{procedure_id}/versions", headers=headers,
                        json={"summary": "Cotizacion inicial"})
    assert response.status_code == 201, response.text
    return procedure_id, response.json()["id"]


def ready(api, user, procedure_id=None):
    procedure_id, version_id = draft(api, user, procedure_id)
    path = f"/api/v1/procedure-versions/{version_id}"
    response = api.post(path + "/steps", headers=user["headers"], json={
        "position": 1, "instruction": "Registrar cotizacion", "expected_result": "Cotizacion guardada",
        "origin": "user_explained", "validation_status": "confirmed"})
    assert response.status_code == 201, response.text
    assert api.put(path + "/tutorial", headers=user["headers"], json={"content": "# Crear cotizacion\nRegistrar datos."}).status_code == 200
    return procedure_id, version_id


def test_review_publication_search_and_retirement(api, account):
    owner = account()
    reader = account(role="reader", organization_id=owner["organization_id"])
    outsider = account()
    procedure_id, version_id = ready(api, owner)
    path = f"/api/v1/procedure-versions/{version_id}"
    assert api.get(path, headers=reader["headers"]).status_code == 404
    assert api.get("/api/v1/procedures", headers=reader["headers"]).json() == []
    assert api.post(path + "/publish", headers=owner["headers"]).status_code == 409
    assert api.post(path + "/submit", headers=owner["headers"]).json()["status"] == "in_review"
    assert api.post(path + "/approve", headers=owner["headers"]).json()["status"] == "approved"
    assert api.put(path + "/tutorial", headers=owner["headers"], json={"content": "Changed"}).status_code == 409
    assert api.post(path + "/publish", headers=owner["headers"]).json()["status"] == "published"
    assert api.post(path + "/publish", headers=owner["headers"]).status_code == 200
    assert api.get(path + "/tutorial", headers=reader["headers"]).status_code == 200
    results = api.get("/api/v1/knowledge/search?q=cotizacion", headers=reader["headers"]).json()
    assert len(results) == 1 and results[0]["version_id"] == version_id
    assert api.get("/api/v1/knowledge/search?q=cotizacion", headers=outsider["headers"]).json() == []
    assert api.get(path, headers=outsider["headers"]).status_code == 404
    assert api.post(path + "/retire", headers=reader["headers"]).status_code == 403
    assert api.post(path + "/retire", headers=owner["headers"]).json()["status"] == "retired"
    assert api.get("/api/v1/knowledge/search?q=cotizacion", headers=reader["headers"]).json() == []
    assert api.get(path + "/tutorial", headers=reader["headers"]).status_code == 404


def test_author_cannot_approve_and_reviewer_cannot_edit(api, account):
    owner = account()
    author = account(role="author", organization_id=owner["organization_id"])
    reviewer = account(role="reviewer", organization_id=owner["organization_id"])
    _, version_id = ready(api, author)
    path = f"/api/v1/procedure-versions/{version_id}"
    assert api.post(path + "/submit", headers=author["headers"]).status_code == 200
    assert api.post(path + "/approve", headers=author["headers"]).status_code == 403
    assert api.post(path + "/return", headers=reviewer["headers"]).json()["status"] == "draft"
    assert api.put(path + "/tutorial", headers=reviewer["headers"], json={"content": "Changed"}).status_code == 403


def test_review_requires_complete_steps_and_evidence(api, account):
    owner = account()
    _, version_id = draft(api, owner)
    path = f"/api/v1/procedure-versions/{version_id}"
    assert api.post(path + "/submit", headers=owner["headers"]).status_code == 409
    assert api.put(path + "/tutorial", headers=owner["headers"], json={"content": "Guide"}).status_code == 200
    step = {"position": 1, "instruction": "Observe", "expected_result": "Done", "origin": "observed"}
    response = api.post(path + "/steps", headers=owner["headers"], json=step)
    assert response.status_code == 201
    assert api.post(path + "/submit", headers=owner["headers"]).status_code == 409
    step["validation_status"] = "confirmed"
    assert api.put(path + "/steps/" + response.json()["id"], headers=owner["headers"], json=step).status_code == 200
    assert api.post(path + "/submit", headers=owner["headers"]).status_code == 409


def test_republication_retires_previous_version_and_concurrent_publish(api, account):
    owner = account()
    procedure_id, first = ready(api, owner)
    _, second = ready(api, owner, procedure_id)
    for version_id in (first, second):
        path = f"/api/v1/procedure-versions/{version_id}"
        assert api.post(path + "/submit", headers=owner["headers"]).status_code == 200
        assert api.post(path + "/approve", headers=owner["headers"]).status_code == 200
    assert api.post(f"/api/v1/procedure-versions/{first}/publish", headers=owner["headers"]).status_code == 200
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: api.post(
            f"/api/v1/procedure-versions/{second}/publish", headers=owner["headers"]), range(2)))
    assert [r.status_code for r in results] == [200, 200]
    assert api.get(f"/api/v1/procedure-versions/{first}", headers=owner["headers"]).json()["status"] == "retired"
    found = api.get("/api/v1/knowledge/search?q=cotizacion", headers=owner["headers"]).json()
    assert len(found) == 1 and found[0]["version_id"] == second
