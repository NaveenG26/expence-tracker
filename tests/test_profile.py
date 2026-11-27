from datetime import date, timedelta

import pytest

from database.db import (
    create_user,
    get_category_totals,
    get_db,
    get_expense_summary,
    get_recent_expenses,
    get_user_by_email,
    get_user_by_id,
    seed_db,
)

DEMO = {"email": "demo@brokeaf.com", "password": "demo123"}


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def login(client, email, password):
    return client.post("/login", data={"email": email, "password": password})


def add_expense(user_id, amount, category, day, description):
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, day, description),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def demo_id():
    return get_user_by_email(DEMO["email"])["id"]


# ------------------------------------------------------------------ #
# Route: access control                                               #
# ------------------------------------------------------------------ #

def test_profile_requires_login(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_profile_stale_session_is_cleared(client):
    with client.session_transaction() as s:
        s["user_id"] = 999
        s["user_name"] = "Ghost"
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with client.session_transaction() as s:
        assert "user_id" not in s


# ------------------------------------------------------------------ #
# Route: rendering                                                    #
# ------------------------------------------------------------------ #

def test_demo_profile_renders_real_data(client):
    seed_db()
    login(client, **DEMO)
    response = client.get("/profile")
    body = response.data

    assert response.status_code == 200
    assert b"Demo User" in body
    assert b"demo@brokeaf.com" in body
    assert b"Member since" in body
    assert "₹283.45".encode() in body
    assert b"Bills" in body
    assert b"coming in Step 4" not in body
    assert b"password_hash" not in body
    assert b"scrypt:" not in body and b"pbkdf2:" not in body


def test_recent_expenses_newest_first(client):
    seed_db()
    login(client, **DEMO)
    body = client.get("/profile").data.decode()

    assert body.index("Groceries") < body.index("Bus fare") < body.index("Restaurant")
    yesterday = (date.today() - timedelta(days=1)).strftime("%d %b %Y")
    assert yesterday in body


def test_category_breakdown_highest_first(client):
    seed_db()
    login(client, **DEMO)
    body = client.get("/profile").data.decode()
    breakdown = body[body.index("Spending by category"):body.index("Recent expenses")]

    order = ["Bills", "Shopping", "Food", "Health", "Entertainment", "Transport", "Other"]
    positions = [breakdown.index(c) for c in order]
    assert positions == sorted(positions)
    assert "₹57.70" in breakdown


def test_empty_state_for_new_user(client):
    # create_user() directly: /register now seeds dummy expenses.
    create_user("New Person", "new@example.com", "password123")
    login(client, "new@example.com", "password123")
    response = client.get("/profile")
    body = response.data.decode()

    assert response.status_code == 200
    assert "New Person" in body
    assert "₹0.00" in body
    assert "No expenses yet" in body
    assert "<table" not in body
    assert "—" in body


def test_users_only_see_their_own_expenses(client):
    seed_db()
    other_id = create_user("Other User", "other@example.com", "password123")
    add_expense(other_id, 99.99, "Shopping", "2026-01-15", "Secret purchase")

    login(client, **DEMO)
    demo_body = client.get("/profile").data.decode()
    assert "Secret purchase" not in demo_body
    assert "₹283.45" in demo_body

    client.get("/logout")
    login(client, "other@example.com", "password123")
    other_body = client.get("/profile").data.decode()
    assert "Secret purchase" in other_body
    assert "Groceries" not in other_body
    assert "₹99.99" in other_body
    assert "₹283.45" not in other_body


def test_nav_name_links_to_profile(client):
    seed_db()
    login(client, **DEMO)
    body = client.get("/").data.decode()
    assert 'href="/profile" class="nav-user"' in body


def test_profile_has_no_inline_styles(client):
    seed_db()
    login(client, **DEMO)
    body = client.get("/profile").data
    assert b'style="' not in body
    assert b"<style" not in body
    assert b"css/profile.css" in body


# ------------------------------------------------------------------ #
# DB helpers                                                          #
# ------------------------------------------------------------------ #

def test_get_user_by_id(app):
    seed_db()
    user = get_user_by_id(demo_id())
    assert set(user.keys()) == {"id", "name", "email", "created_at"}
    assert user["name"] == "Demo User"
    assert get_user_by_id(999) is None


def test_get_expense_summary_seeded(app):
    seed_db()
    summary = get_expense_summary(demo_id())
    assert summary["total_spent"] == pytest.approx(283.45)
    assert summary["expense_count"] == 8
    assert summary["top_category"] == "Bills"


def test_get_expense_summary_empty(app):
    user_id = create_user("Empty", "empty@example.com", "password123")
    summary = get_expense_summary(user_id)
    assert summary == {"total_spent": 0, "expense_count": 0, "top_category": None}
    assert get_category_totals(user_id) == []
    assert get_recent_expenses(user_id) == []


def test_get_category_totals_order(app):
    seed_db()
    rows = get_category_totals(demo_id())
    assert [r["category"] for r in rows] == [
        "Bills", "Shopping", "Food", "Health", "Entertainment", "Transport", "Other",
    ]
    food = next(r for r in rows if r["category"] == "Food")
    assert food["total"] == pytest.approx(57.70)


def test_get_recent_expenses_limit_and_order(app):
    seed_db()
    rows = get_recent_expenses(demo_id(), limit=3)
    assert len(rows) == 3
    assert rows[0]["description"] == "Groceries"
    assert len(get_recent_expenses(demo_id())) == 8


def test_get_recent_expenses_same_date_newest_id_first(app):
    user_id = create_user("Tie", "tie@example.com", "password123")
    first = add_expense(user_id, 1.0, "Food", "2026-03-01", "First")
    second = add_expense(user_id, 2.0, "Food", "2026-03-01", "Second")
    rows = get_recent_expenses(user_id)
    assert [r["id"] for r in rows] == [second, first]


def test_top_category_tie_breaks_alphabetically(app):
    user_id = create_user("Tie", "tie2@example.com", "password123")
    add_expense(user_id, 10.0, "Transport", "2026-03-01", "Taxi")
    add_expense(user_id, 10.0, "Food", "2026-03-02", "Lunch")
    assert get_expense_summary(user_id)["top_category"] == "Food"


# ------------------------------------------------------------------ #
# Template filters                                                    #
# ------------------------------------------------------------------ #

def test_inr_filter(app):
    inr = app.jinja_env.filters["inr"]
    assert inr(0) == "₹0.00"
    assert inr(None) == "₹0.00"
    assert inr(12.5) == "₹12.50"


def test_datefmt_filter(app):
    datefmt = app.jinja_env.filters["datefmt"]
    assert datefmt("2026-11-05") == "05 Nov 2026"
    assert datefmt("2026-11-05 10:20:30", "%B %Y") == "November 2026"
    assert datefmt("not a date") == "not a date"
