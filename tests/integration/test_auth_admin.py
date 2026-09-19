from tests.conftest import login


def test_admin_and_user_login(client):
    admin = client.post("/api/auth/login", json={"identifier": "ACME-000001", "password": "DevPassw0rd!x"})
    assert admin.status_code == 200
    assert admin.json()["user"]["app_role"] == "ADMIN"
    assert "password_hash" not in admin.json()["user"]
    headers = {"X-CSRF-Token": client.cookies.get("csrf_token")}
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["full_name"] == "Admin User"

    client.post("/api/auth/logout", headers=headers)
    alice_headers = login(client, "alice@acme.local")
    me = client.get("/api/auth/me", headers=alice_headers)
    assert me.json()["unique_identifier"] == "ACME-100001"


def test_login_does_not_reveal_which_field(client):
    missing = client.post("/api/auth/login", json={"identifier": "nobody", "password": "DevPassw0rd!x"})
    wrong = client.post("/api/auth/login", json={"identifier": "ACME-100001", "password": "definitely-wrong-pass"})
    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert missing.json()["error"] == wrong.json()["error"]


def test_admin_can_create_and_disable_user(client):
    headers = login(client, "ACME-000001")
    org = client.get("/api/admin/org", headers=headers).json()
    dept_id = org["departments"][0]["id"]
    created = client.post(
        "/api/admin/users",
        headers=headers,
        json={
            "email": "erin@example.com",
            "full_name": "Erin New",
            "password": "TempPassw0rd!x",
            "app_role": "EMPLOYEE",
            "department_id": dept_id,
        },
    )
    assert created.status_code == 200
    user_id = created.json()["id"]
    assert created.json()["unique_identifier"].startswith("ACME-")
    disabled = client.patch(f"/api/admin/users/{user_id}", headers=headers, json={"is_active": False})
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False


def test_admin_registration_with_otp_flow(client, app):
    from app.database import SessionLocal
    from app.models.otp import EmailOtp

    email = "newadmin@gmail.com"
    send_res = client.post("/api/auth/register-admin/send-otp", json={"email": email})
    assert send_res.status_code == 200
    assert send_res.json()["ok"] is True

    # Check OTP record in DB
    db = SessionLocal()
    otp_record = db.query(EmailOtp).filter(EmailOtp.email == email, EmailOtp.is_used.is_(False)).first()
    assert otp_record is not None
    db.close()

    # Test short password rejection
    short_pw = client.post(
        "/api/auth/register-admin/verify",
        json={"full_name": "New Admin", "company_name": "New Corp", "email": email, "password": "Short1!", "otp": "123456"},
    )
    assert short_pw.status_code == 400

    # Test wrong OTP rejection
    wrong_otp = client.post(
        "/api/auth/register-admin/verify",
        json={"full_name": "New Admin", "company_name": "New Corp", "email": email, "password": "StrongPassword1!", "otp": "000000"},
    )
    assert wrong_otp.status_code == 400

    # Test correct OTP verification by querying the hash
    from app.security.crypto import hash_token
    # Set known OTP code for deterministic verification
    db = SessionLocal()
    rec = db.query(EmailOtp).filter(EmailOtp.email == email, EmailOtp.is_used.is_(False)).first()
    rec.otp_hash = hash_token("654321")
    db.commit()
    db.close()

    verify_res = client.post(
        "/api/auth/register-admin/verify",
        json={"full_name": "New Admin", "company_name": "New Corp", "email": email, "password": "StrongPassword1!", "otp": "654321"},
    )
    assert verify_res.status_code == 200
    user_data = verify_res.json()["user"]
    assert user_data["email"] == email
    assert user_data["app_role"] == "ADMIN"
    assert user_data["unique_identifier"].startswith("ACME-ADMIN-")

    # Verify session cookie was set and /api/auth/me works
    headers = {"X-CSRF-Token": client.cookies.get("csrf_token")}
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert me.json()["app_role"] == "ADMIN"

