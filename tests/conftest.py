import pytest

from app import app as flask_app
from database.db import create_user, init_db

TEST_EMAIL = "tester@example.com"
TEST_PASSWORD = "secret123"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("database.db.DB_PATH", str(tmp_path / "test.db"))
    init_db()
    monkeypatch.setitem(flask_app.config, "TESTING", True)
    # CSRF is exercised explicitly in tests that opt in; off by default so
    # tests can POST forms directly.
    monkeypatch.setitem(flask_app.config, "CSRF_ENABLED", False)
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user_id(app):
    return create_user("Tester", TEST_EMAIL, TEST_PASSWORD)


@pytest.fixture
def auth_client(client, user_id):
    client.post("/login", data={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    return client
