from tests.conftest import login


def test_demo_alice_bob_revocation_flow(client):
    alice = login(client, "ACME-100001")
    eng = client.post("/api/chat", headers=alice, json={"query": "Summarize the engineering architecture."})
    assert eng.status_code == 200
    assert eng.json()["citations"]
    salaries = client.post("/api/chat", headers=alice, json={"query": "What are the finance salaries?"})
    assert "I don't have enough authorized information" in salaries.json()["answer"]

    bob = login(client, "ACME-100002")
    finance = client.post("/api/chat", headers=bob, json={"query": "What is the CEO annual salary?"})
    assert "480000" in finance.json()["answer"]

    admin = login(client, "ACME-000001")
    users = client.get("/api/admin/users", headers=admin).json()
    bob_user = next(u for u in users if u["unique_identifier"] == "ACME-100002")
    org = client.get("/api/admin/org", headers=admin).json()
    # Remove finance role from Bob
    client.patch(
        f"/api/admin/users/{bob_user['id']}",
        headers=admin,
        json={"role_ids": [], "group_ids": []},
    )
    bob2 = login(client, "ACME-100002")
    again = client.post("/api/chat", headers=bob2, json={"query": "What is the CEO annual salary?"})
    assert "480000" not in again.json()["answer"]
