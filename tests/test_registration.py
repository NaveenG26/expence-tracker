from werkzeug.security import check_password_hash

from database.db import get_db, seed_db

VALID = {"name": "Asha Rao", "email": "asha@example.com", "password": "secret123"}


def user_count():
    conn = get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        conn.close()


def test_get_register_renders_form(client):
    response = client.get("/register")
    assert response.status_code == 200
    assert b"Create your account" in response.data


def test_valid_signup_creates_user_and_redirects(client):
    response = client.post("/register", data=VALID)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?", (VALID["email"],)
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["password_hash"] != VALID["password"]
    assert check_password_hash(row["password_hash"], VALID["password"])


def test_short_password_rejected(client):
    response = client.post("/register", data={**VALID, "password": "short7!"})
    assert response.status_code == 400
    assert b"at least 8 characters" in response.data
    assert user_count() == 0


def test_blank_name_rejected(client):
    for name in ("", "   "):
        response = client.post("/register", data={**VALID, "name": name})
        assert response.status_code == 400
        assert b"Name is required" in response.data
    assert user_count() == 0


def test_invalid_email_rejected(client):
    for email in ("", "   ", "not-an-email"):
        response = client.post("/register", data={**VALID, "email": email})
        assert response.status_code == 400
        assert b"valid email" in response.data
    assert user_count() == 0


def test_duplicate_email_rejected(client):
    assert client.post("/register", data=VALID).status_code == 302
    response = client.post("/register", data=VALID)
    assert response.status_code == 400
    assert b"already exists" in response.data
    assert user_count() == 1


def test_duplicate_email_different_case_rejected(client):
    client.post("/register", data=VALID)
    response = client.post(
        "/register", data={**VALID, "email": VALID["email"].upper()}
    )
    assert response.status_code == 400
    assert b"already exists" in response.data
    assert user_count() == 1


def test_seeded_demo_email_rejected(client):
    seed_db()
    before = user_count()
    response = client.post(
        "/register", data={**VALID, "email": "demo@spendly.com"}
    )
    assert response.status_code == 400
    assert b"already exists" in response.data
    assert user_count() == before


def test_failed_submit_keeps_name_and_email_but_not_password(client):
    response = client.post("/register", data={**VALID, "password": "short"})
    html = response.data.decode()
    assert 'value="Asha Rao"' in html
    assert 'value="asha@example.com"' in html
    assert "short" not in html.replace("Password must be at least 8 characters", "")
