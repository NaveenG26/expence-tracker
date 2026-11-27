import re

import pytest

from database.db import (
    create_user,
    get_category_breakdown,
    get_db,
    get_expense_summary,
    get_recent_expenses,
    get_user_by_email,
    get_user_by_id,
    seed_db,
)

DEMO = {"email": "demo@spendly.com", "password": "demo123"}
SEED_TOTAL = 283.45
SEED_CATEGORIES = [
    "Bills", "Shopping", "Food", "Health", "Entertainment", "Transport", "Other",
]


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def login(client, email, password):
    return client.post("/login", data={"email": email, "password": password})


def add_expense(user_id, amount, category, day, description):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, day, description),
        )
        conn.commit()
    finally:
        conn.close()


def demo_id():
    return get_user_by_email(DEMO["email"])["id"]


def breakdown_section(body):
    return body[body.index("Spending by category"):body.index("Recent expenses")]


# ------------------------------------------------------------------ #
# Unit: get_user_by_id                                                #
# ------------------------------------------------------------------ #

def test_get_user_by_id_valid(app):
    seed_db()
    user = get_user_by_id(demo_id())
    assert user["name"] == "Demo User"
    assert user["email"] == "demo@spendly.com"
    assert user["created_at"]


def test_get_user_by_id_missing(app):
    assert get_user_by_id(12345) is None


# ------------------------------------------------------------------ #
# Unit: get_expense_summary                                           #
# ------------------------------------------------------------------ #

def test_summary_with_expenses(app):
    seed_db()
    summary = get_expense_summary(demo_id())
    assert summary["total_spent"] == pytest.approx(SEED_TOTAL)
    assert summary["expense_count"] == 8
    assert summary["top_category"] == "Bills"


def test_summary_without_expenses(app):
    user_id = create_user("Empty", "empty@example.com", "password123")
    assert get_expense_summary(user_id) == {
        "total_spent": 0,
        "expense_count": 0,
        "top_category": None,
    }


# ------------------------------------------------------------------ #
# Unit: get_recent_expenses                                           #
# ------------------------------------------------------------------ #

def test_recent_expenses_newest_first_with_fields(app):
    seed_db()
    rows = get_recent_expenses(demo_id())
    assert len(rows) == 8
    dates = [r["date"] for r in rows]
    assert dates == sorted(dates, reverse=True)
    for r in rows:
        assert {"date", "description", "category", "amount"} <= set(r.keys())


def test_recent_expenses_empty(app):
    user_id = create_user("Empty", "empty@example.com", "password123")
    assert get_recent_expenses(user_id) == []


# ------------------------------------------------------------------ #
# Unit: get_category_breakdown                                        #
# ------------------------------------------------------------------ #

def test_breakdown_seeded_order_and_pct(app):
    seed_db()
    rows = get_category_breakdown(demo_id())
    assert [r["category"] for r in rows] == SEED_CATEGORIES
    totals = [r["total"] for r in rows]
    assert totals == sorted(totals, reverse=True)
    assert all(isinstance(r["pct"], int) for r in rows)
    assert sum(r["pct"] for r in rows) == 100


def test_breakdown_largest_absorbs_rounding_remainder(app):
    # Three equal shares of 33.33% round to 33 each (sum 99);
    # the first (largest) row must absorb the missing 1%.
    user_id = create_user("Thirds", "thirds@example.com", "password123")
    add_expense(user_id, 10.0, "Bills", "2026-03-01", "A")
    add_expense(user_id, 10.0, "Food", "2026-03-02", "B")
    add_expense(user_id, 10.0, "Other", "2026-03-03", "C")
    rows = get_category_breakdown(user_id)
    assert [r["pct"] for r in rows] == [34, 33, 33]


def test_breakdown_rounding_overshoot_is_corrected(app):
    # Shares 33.5 / 33.5 / 33.0 round to 34 + 34 + 33 = 101;
    # the first (largest) row gives back the extra 1%.
    user_id = create_user("Split", "split@example.com", "password123")
    add_expense(user_id, 67.0, "Bills", "2026-03-01", "A")
    add_expense(user_id, 67.0, "Food", "2026-03-02", "B")
    add_expense(user_id, 66.0, "Other", "2026-03-03", "C")
    rows = get_category_breakdown(user_id)
    assert [r["pct"] for r in rows] == [33, 34, 33]
    assert sum(r["pct"] for r in rows) == 100


def test_breakdown_empty(app):
    user_id = create_user("Empty", "empty@example.com", "password123")
    assert get_category_breakdown(user_id) == []


# ------------------------------------------------------------------ #
# Route: GET /profile                                                 #
# ------------------------------------------------------------------ #

def test_profile_unauthenticated_redirects(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_profile_seed_user_live_data(client):
    seed_db()
    login(client, **DEMO)
    response = client.get("/profile")
    body = response.data.decode()

    assert response.status_code == 200
    assert "Demo User" in body
    assert "demo@spendly.com" in body
    assert "₹" in body
    assert "£" not in body and "$" not in body
    assert f"₹{SEED_TOTAL:.2f}" in body
    assert re.search(r'profile-stat-value">\s*8\s*<', body)
    assert re.search(r'profile-stat-value">\s*Bills\s*<', body)


def test_profile_transactions_newest_first(client):
    seed_db()
    login(client, **DEMO)
    body = client.get("/profile").data.decode()
    table = body[body.index("<tbody>"):body.index("</tbody>")]

    assert table.count("<tr>") == 8
    descriptions = [
        "Groceries", "Bus fare", "Electricity bill", "Pharmacy",
        "Movie tickets", "New shoes", "Miscellaneous", "Restaurant",
    ]
    positions = [table.index(d) for d in descriptions]
    assert positions == sorted(positions)


def test_profile_breakdown_has_all_categories_summing_to_100(client):
    seed_db()
    login(client, **DEMO)
    section = breakdown_section(client.get("/profile").data.decode())

    for category in SEED_CATEGORIES:
        assert category in section
    pcts = [int(p) for p in re.findall(r'category-pct">(\d+)%<', section)]
    assert len(pcts) == 7
    assert sum(pcts) == 100


def test_profile_new_user_shows_zero_state(client):
    # create_user() directly: /register now seeds dummy expenses.
    create_user("Fresh User", "fresh@example.com", "password123")
    login(client, "fresh@example.com", "password123")
    response = client.get("/profile")
    body = response.data.decode()

    assert response.status_code == 200
    assert "₹0.00" in body
    assert re.search(r'profile-stat-value">\s*0\s*<', body)
    assert "Spending by category" not in body
    assert "No expenses yet" in body
