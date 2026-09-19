from app.models.otp import EmailOtp
from app.models.user import User
from app.security.crypto import hash_token
import io


def _register_admin(client, email, name, company_name="Test Company", password="StrongPassword1!"):
    from app import database as dbmod
    client.post("/api/auth/register-admin/send-otp", json={"email": email})
    db = dbmod.SessionLocal()
    rec = db.query(EmailOtp).filter(EmailOtp.email == email, EmailOtp.is_used.is_(False)).first()
    rec.otp_hash = hash_token("999999")
    db.commit()
    db.close()

    res = client.post(
        "/api/auth/register-admin/verify",
        json={"full_name": name, "company_name": company_name, "email": email, "password": password, "otp": "999999"},
    )
    assert res.status_code == 200, res.text
    csrf = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": csrf}


def test_multi_tenant_admin_and_worker_isolation(client):
    # Register Admin A
    headers_a = _register_admin(client, "admin_a@acme.com", "Admin Alpha", company_name="Alpha Corp")

    # Create a department for Admin A
    dept_a = client.post(
        "/api/admin/org/departments",
        headers=headers_a,
        json={"name": "Engineering", "description": "Engineering dept"},
    )
    assert dept_a.status_code == 200, dept_a.text
    dept_a_id = dept_a.json()["id"]

    # Create Worker A under Admin A
    create_a = client.post(
        "/api/admin/users",
        headers=headers_a,
        json={
            "email": "worker_a@acme.com",
            "full_name": "Worker Alpha",
            "password": "WorkerPassw0rd!1",
            "app_role": "EMPLOYEE",
            "department_id": dept_a_id,
        },
    )
    assert create_a.status_code == 200, create_a.text

    # Register Admin B in separate session
    from starlette.testclient import TestClient
    from app.main import app
    client_b = TestClient(app)
    headers_b = _register_admin(client_b, "admin_b@globex.com", "Admin Beta", company_name="Beta Corp")

    # Create a department for Admin B
    dept_b = client_b.post(
        "/api/admin/org/departments",
        headers=headers_b,
        json={"name": "Engineering", "description": "Engineering dept"},
    )
    assert dept_b.status_code == 200, dept_b.text
    dept_b_id = dept_b.json()["id"]

    # Create Worker B under Admin B
    create_b = client_b.post(
        "/api/admin/users",
        headers=headers_b,
        json={
            "email": "worker_b@globex.com",
            "full_name": "Worker Beta",
            "password": "WorkerPassw0rd!2",
            "app_role": "EMPLOYEE",
            "department_id": dept_b_id,
        },
    )
    assert create_b.status_code == 200, create_b.text

    # Verify Admin A's user list ONLY contains Admin A and Worker A
    users_a = client.get("/api/admin/users", headers=headers_a).json()
    emails_a = {u["email"] for u in users_a}
    assert "admin_a@acme.com" in emails_a
    assert "worker_a@acme.com" in emails_a
    assert "admin_b@globex.com" not in emails_a
    assert "worker_b@globex.com" not in emails_a

    # Verify Admin B's user list ONLY contains Admin B and Worker B
    users_b = client_b.get("/api/admin/users", headers=headers_b).json()
    emails_b = {u["email"] for u in users_b}
    assert "admin_b@globex.com" in emails_b
    assert "worker_b@globex.com" in emails_b
    assert "admin_a@acme.com" not in emails_b
    assert "worker_a@acme.com" not in emails_b

    # Verify dashboard user counts are isolated
    dash_a = client.get("/api/admin/dashboard", headers=headers_a).json()
    assert dash_a["total_users"] == 2  # Admin A + Worker A

    dash_b = client_b.get("/api/admin/dashboard", headers=headers_b).json()
    assert dash_b["total_users"] == 2  # Admin B + Worker B


def test_multi_tenant_document_and_rag_isolation(client):
    from starlette.testclient import TestClient
    from app.main import app
    import json

    # 1. Register Admin X (Company X) & Admin Y (Company Y)
    client_x = TestClient(app)
    headers_x = _register_admin(client_x, "admin_x@comp-x.com", "Admin X", company_name="Company X")

    client_y = TestClient(app)
    headers_y = _register_admin(client_y, "admin_y@comp-y.com", "Admin Y", company_name="Company Y")

    # 2. Create Departments in each company
    dept_x = client_x.post(
        "/api/admin/org/departments",
        headers=headers_x,
        json={"name": "Operations", "description": "Ops"},
    )
    assert dept_x.status_code == 200, dept_x.text
    dept_x_id = dept_x.json()["id"]

    dept_y = client_y.post(
        "/api/admin/org/departments",
        headers=headers_y,
        json={"name": "Operations", "description": "Ops"},
    )
    assert dept_y.status_code == 200, dept_y.text
    dept_y_id = dept_y.json()["id"]

    # 3. Create Workers in each company
    res_wx = client_x.post(
        "/api/admin/users",
        headers=headers_x,
        json={
            "email": "worker_x@comp-x.com",
            "full_name": "Worker X",
            "password": "WorkerPassw0rd!X",
            "app_role": "EMPLOYEE",
            "must_change_password": False,
            "department_id": dept_x_id,
        },
    )
    assert res_wx.status_code == 200, res_wx.text

    res_wy = client_y.post(
        "/api/admin/users",
        headers=headers_y,
        json={
            "email": "worker_y@comp-y.com",
            "full_name": "Worker Y",
            "password": "WorkerPassw0rd!Y",
            "app_role": "EMPLOYEE",
            "must_change_password": False,
            "department_id": dept_y_id,
        },
    )
    assert res_wy.status_code == 200, res_wy.text

    # 3. Admin X uploads Document X
    doc_x_data = b"Company X Confidential: Project Falcon budget is 450000 dollars."
    upload_x = client_x.post(
        "/api/admin/documents",
        headers=headers_x,
        files={"file": ("falcon.txt", io.BytesIO(doc_x_data), "text/plain")},
        data={
            "title": "Project Falcon Strategy",
            "classification": "INTERNAL",
            "acls_json": json.dumps([{"principal_type": "PUBLIC", "permission": "READ"}]),
        },
    )
    assert upload_x.status_code == 200, upload_x.text
    doc_x_id = upload_x.json()["id"]

    # 4. Admin Y uploads Document Y
    doc_y_data = b"Company Y Confidential: Project Pegasus budget is 820000 dollars."
    upload_y = client_y.post(
        "/api/admin/documents",
        headers=headers_y,
        files={"file": ("pegasus.txt", io.BytesIO(doc_y_data), "text/plain")},
        data={
            "title": "Project Pegasus Strategy",
            "classification": "INTERNAL",
            "acls_json": json.dumps([{"principal_type": "PUBLIC", "permission": "READ"}]),
        },
    )
    assert upload_y.status_code == 200, upload_y.text
    doc_y_id = upload_y.json()["id"]

    # 5. Document Management Isolation
    # Admin X only sees Falcon
    docs_x = client_x.get("/api/admin/documents", headers=headers_x).json()
    titles_x = [d["title"] for d in docs_x]
    assert "Project Falcon Strategy" in titles_x
    assert "Project Pegasus Strategy" not in titles_x

    # Admin Y only sees Pegasus
    docs_y = client_y.get("/api/admin/documents", headers=headers_y).json()
    titles_y = [d["title"] for d in docs_y]
    assert "Project Pegasus Strategy" in titles_y
    assert "Project Falcon Strategy" not in titles_y

    # Admin X cannot access, modify, or delete Pegasus (404)
    assert client_x.get(f"/api/admin/documents/{doc_y_id}", headers=headers_x).status_code == 404
    assert client_x.patch(f"/api/admin/documents/{doc_y_id}", headers=headers_x, json={"title": "Hacked"}).status_code == 404
    assert client_x.delete(f"/api/admin/documents/{doc_y_id}", headers=headers_x).status_code == 404
    assert client_x.post(f"/api/admin/documents/{doc_y_id}/reindex", headers=headers_x).status_code == 404

    # 6. RAG Isolation: Worker X searches
    worker_x_client = TestClient(app)
    login_x = worker_x_client.post(
        "/api/auth/login",
        json={"identifier": "worker_x@comp-x.com", "password": "WorkerPassw0rd!X", "company_name": "Company X"},
    )
    assert login_x.status_code == 200, login_x.text
    headers_wx = {"X-CSRF-Token": worker_x_client.cookies.get("csrf_token")}

    # Worker X can read Falcon
    chat_x_own = worker_x_client.post(
        "/api/chat",
        headers=headers_wx,
        json={"query": "What is the Falcon budget?"},
    )
    assert chat_x_own.status_code == 200
    assert "450000" in chat_x_own.json()["answer"] or "falcon" in chat_x_own.json()["answer"].lower()
    assert any("Falcon" in c["title"] for c in chat_x_own.json()["citations"])

    # Worker X CANNOT read Pegasus from Company Y (Zero cross-tenant leakage!)
    chat_x_cross = worker_x_client.post(
        "/api/chat",
        headers=headers_wx,
        json={"query": "What is the Pegasus mission?"},
    )
    assert chat_x_cross.status_code == 200
    assert "820000" not in chat_x_cross.json()["answer"]
    assert "I don't have enough authorized information" in chat_x_cross.json()["answer"]
    assert chat_x_cross.json()["citations"] == []

    # 7. RAG Isolation: Worker Y searches
    worker_y_client = TestClient(app)
    login_y = worker_y_client.post(
        "/api/auth/login",
        json={"identifier": "worker_y@comp-y.com", "password": "WorkerPassw0rd!Y", "company_name": "Company Y"},
    )
    assert login_y.status_code == 200, login_y.text
    headers_wy = {"X-CSRF-Token": worker_y_client.cookies.get("csrf_token")}

    # Worker Y can read Pegasus
    chat_y_own = worker_y_client.post(
        "/api/chat",
        headers=headers_wy,
        json={"query": "What is the Pegasus budget?"},
    )
    assert chat_y_own.status_code == 200
    assert "820000" in chat_y_own.json()["answer"] or "pegasus" in chat_y_own.json()["answer"].lower()
    assert any("Pegasus" in c["title"] for c in chat_y_own.json()["citations"])

    # Worker Y CANNOT read Falcon from Company X (Zero cross-tenant leakage!)
    chat_y_cross = worker_y_client.post(
        "/api/chat",
        headers=headers_wy,
        json={"query": "What is the Falcon mission?"},
    )
    assert chat_y_cross.status_code == 200
    assert "450000" not in chat_y_cross.json()["answer"]
    assert "I don't have enough authorized information" in chat_y_cross.json()["answer"]
    assert chat_y_cross.json()["citations"] == []

