from typing import Any

from fastapi.testclient import TestClient

BASE_PAYLOAD: dict[str, Any] = {
    "type": "preference",
    "scope": {"tenant_id": "home", "project_id": "henley"},
    "content": "User prefers operational summaries with explicit next actions.",
    "provenance": {"source_type": "agent_run", "run_id": "run_1"},
    "confidence": 0.92,
    "sensitivity": "internal",
}


def test_create_memory_requires_auth(client: TestClient) -> None:
    response = client.post("/memories", json=BASE_PAYLOAD)
    assert response.status_code == 401


def test_create_memory_succeeds_and_is_approved(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post("/memories", json=BASE_PAYLOAD, headers=auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["memory_id"].startswith("mem_")
    assert body["write_status"] == "approved"
    assert body["scope"]["tenant_id"] == BASE_PAYLOAD["scope"]["tenant_id"]
    assert body["scope"]["project_id"] == BASE_PAYLOAD["scope"]["project_id"]
    assert body["content"] == BASE_PAYLOAD["content"]


def test_create_memory_rejects_unknown_type(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    payload = {**BASE_PAYLOAD, "type": "not-a-real-type"}
    response = client.post("/memories", json=payload, headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "policy_rejected"


def test_create_memory_rejects_unknown_sensitivity(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    payload = {**BASE_PAYLOAD, "sensitivity": "not-a-real-tier"}
    response = client.post("/memories", json=payload, headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "policy_rejected"


def test_create_memory_rejects_invalid_confidence(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    payload = {**BASE_PAYLOAD, "confidence": 1.5}
    response = client.post("/memories", json=payload, headers=auth_headers)
    assert response.status_code == 422


def test_sensitive_memory_requires_approval_and_is_hidden_from_search(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    payload = {**BASE_PAYLOAD, "sensitivity": "sensitive"}
    created = client.post("/memories", json=payload, headers=auth_headers).json()
    assert created["write_status"] == "pending_approval"

    search = client.post(
        "/memories/search",
        json={"scope": BASE_PAYLOAD["scope"], "query": "operational summaries"},
        headers=auth_headers,
    )
    assert search.status_code == 200
    assert search.json() == []

    search_including_pending = client.post(
        "/memories/search",
        json={
            "scope": BASE_PAYLOAD["scope"],
            "query": "operational summaries",
            "include_pending": True,
        },
        headers=auth_headers,
    )
    ids = [hit["memory"]["memory_id"] for hit in search_including_pending.json()]
    assert created["memory_id"] in ids


def test_get_memory_round_trip(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    created = client.post("/memories", json=BASE_PAYLOAD, headers=auth_headers).json()
    response = client.get(
        f"/memories/{created['memory_id']}",
        params={"tenant_id": "home", "project_id": "henley"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["memory_id"] == created["memory_id"]


def test_get_memory_outside_scope_is_not_found(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    created = client.post("/memories", json=BASE_PAYLOAD, headers=auth_headers).json()
    response = client.get(
        f"/memories/{created['memory_id']}",
        params={"tenant_id": "someone-else", "project_id": "henley"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_search_finds_approved_memory_in_scope(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    client.post("/memories", json=BASE_PAYLOAD, headers=auth_headers)
    response = client.post(
        "/memories/search",
        json={
            "scope": {"tenant_id": "home", "project_id": "henley"},
            "query": "How does the user like reports formatted?",
            "top_k": 5,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["memory"]["content"] == BASE_PAYLOAD["content"]


def test_search_respects_project_scope_isolation(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    client.post("/memories", json=BASE_PAYLOAD, headers=auth_headers)
    response = client.post(
        "/memories/search",
        json={
            "scope": {"tenant_id": "home", "project_id": "a-different-project"},
            "query": "operational summaries",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json() == []
