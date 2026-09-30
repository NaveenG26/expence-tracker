from database.db import seed_db

DEMO = {"email": "demo@spendly.com", "password": "demo123"}
ERROR = b"Invalid email or password"


def test_get_login_renders_form(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Welcome back" in response.data
    assert b"Sign in" in response.data


def test_demo_login_sets_session_and_redirects(client):
    seed_db()
    response = client.post("/login", data=DEMO)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")
    with client.session_transaction() as s:
        assert s["user_id"]
        assert s["user_name"] == "Demo User"
        assert "password_hash" not in s


def test_registered_user_can_log_in(client):
    client.post(
        "/register",
        data={"name": "Asha", "email": "asha@example.com", "password": "secret123"},
    )
    response = client.post(
        "/login", data={"email": "asha@example.com", "password": "secret123"}
    )
    assert response.status_code == 302


def test_email_case_and_whitespace_insensitive(client):
    seed_db()
    response = client.post(
        "/login", data={"email": "  DEMO@Spendly.com ", "password": "demo123"}
    )
    assert response.status_code == 302


def test_wrong_password_rejected(client):
    seed_db()
    response = client.post(
        "/login", data={"email": DEMO["email"], "password": "wrongpass"}
    )
    assert response.status_code == 400
    assert ERROR in response.data
    with client.session_transaction() as s:
        assert "user_id" not in s


def test_unknown_email_same_error(client):
    seed_db()
    response = client.post(
        "/login", data={"email": "nobody@example.com", "password": "demo123"}
    )
    assert response.status_code == 400
    assert ERROR in response.data
    with client.session_transaction() as s:
        assert "user_id" not in s


def test_blank_fields_rejected(client):
    seed_db()
    for data in (
        {"email": "", "password": "demo123"},
        {"email": DEMO["email"], "password": ""},
        {"email": "", "password": ""},
    ):
        response = client.post("/login", data=data)
        assert response.status_code == 400
        assert ERROR in response.data
        with client.session_transaction() as s:
            assert "user_id" not in s


def test_failed_login_repopulates_email_not_password(client):
    seed_db()
    response = client.post(
        "/login", data={"email": DEMO["email"], "password": "wrongpass"}
    )
    assert b'value="demo@spendly.com"' in response.data
    assert b"wrongpass" not in response.data


def test_login_redirects_when_already_logged_in(client):
    with client.session_transaction() as s:
        s["user_id"] = 1
    response = client.get("/login")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")


def test_logout_clears_session(client):
    seed_db()
    client.post("/login", data=DEMO)
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    with client.session_transaction() as s:
        assert "user_id" not in s
    assert client.get("/login").status_code == 200


def test_logout_while_logged_out_redirects(client):
    response = client.get("/logout")
    assert response.status_code == 302


def test_nav_reflects_login_state(client):
    seed_db()
    page = client.get("/login").data
    assert b"Get started" in page
    assert b"Sign out" not in page

    client.post("/login", data=DEMO)
    page = client.get("/", follow_redirects=True).data
    assert b"Sign out" in page
    assert b"Demo User" in page
    assert b"Get started" not in page


def test_profile_still_stub(client):
    assert b"coming in Step 4" in client.get("/profile").data


def test_secret_key_configured(app):
    assert app.secret_key
