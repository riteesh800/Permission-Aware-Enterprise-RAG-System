from tests.conftest import login


def test_alice_engineering_and_denied_finance(client):
    headers = login(client, "ACME-100001")
    ok = client.post("/api/chat", headers=headers, json={"query": "What are the engineering architecture details?"})
    assert ok.status_code == 200
    body = ok.json()
    assert "FastAPI" in body["answer"] or "architecture" in body["answer"].lower()
    assert body["citations"]
    assert all("Finance" not in c["title"] for c in body["citations"])

    denied = client.post("/api/chat", headers=headers, json={"query": "What is the CEO salary in the finance report?"})
    assert denied.status_code == 200
    assert "480000" not in denied.json()["answer"]
    assert "I don't have enough authorized information" in denied.json()["answer"]
    assert denied.json()["citations"] == []


def test_bob_can_read_finance_until_revoked(client):
    headers = login(client, "ACME-100002")
    first = client.post("/api/chat", headers=headers, json={"query": "What is the CEO salary?"})
    assert first.status_code == 200
    assert "480000" in first.json()["answer"]

    admin = login(client, "ACME-000001")
    docs = client.get("/api/admin/documents", headers=admin).json()
    finance = next(d for d in docs if d["title"] == "Finance Salary Report")
    role_acls = [a for a in finance["acls"] if a["principal_type"] == "ROLE"]
    finance_role_id = role_acls[0]["principal_id"]
    payload_acls = [
        {
            "principal_type": a["principal_type"],
            "principal_id": a["principal_id"],
            "permission": a["permission"],
            "department_scoped": a["department_scoped"],
        }
        for a in finance["acls"]
        if a["principal_id"] != finance_role_id
    ]
    patched = client.patch(
        f"/api/admin/documents/{finance['id']}",
        headers=admin,
        json={"acls": payload_acls},
    )
    assert patched.status_code == 200

    bob = login(client, "ACME-100002")
    second = client.post("/api/chat", headers=bob, json={"query": "What is the CEO salary?"})
    assert "480000" not in second.json()["answer"]
    assert "I don't have enough authorized information" in second.json()["answer"]


def test_conversation_isolation(client):
    alice = login(client, "ACME-100001")
    created = client.post("/api/chat", headers=alice, json={"query": "What is the public company policy?"})
    conv_id = created.json()["conversation_id"]
    bob = login(client, "ACME-100002")
    other = client.get(f"/api/conversations/{conv_id}", headers=bob)
    assert other.status_code == 404
