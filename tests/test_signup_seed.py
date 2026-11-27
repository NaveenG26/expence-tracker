import random
from datetime import date, timedelta

import pytest

from database.db import (
    CATEGORIES,
    DUMMY_EXPENSE_PROFILE,
    create_user,
    get_db,
    get_user_by_email,
    seed_dummy_expenses,
)

SIGNUP = {"name": "New Person", "email": "new@example.com", "password": "password123"}


def expenses_for(user_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT amount, category, date, description FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()


class TestSignupSeedsDashboard:
    def test_new_signup_gets_dummy_expenses(self, client):
        response = client.post("/register", data=SIGNUP)
        assert response.status_code == 302
        user = get_user_by_email(SIGNUP["email"])
        assert len(expenses_for(user["id"])) == 50

    def test_new_signup_profile_is_populated(self, client):
        client.post("/register", data=SIGNUP)
        client.post(
            "/login",
            data={"email": SIGNUP["email"], "password": SIGNUP["password"]},
        )
        body = client.get("/profile").get_data(as_text=True)
        assert "No expenses yet" not in body
        assert "Spending by category" in body
        assert "<table" in body

    def test_failed_signup_seeds_nothing(self, client):
        client.post("/register", data={**SIGNUP, "password": "short"})
        conn = get_db()
        try:
            assert conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0] == 0
        finally:
            conn.close()

    def test_duplicate_email_does_not_reseed_existing_user(self, client):
        client.post("/register", data=SIGNUP)
        user = get_user_by_email(SIGNUP["email"])
        response = client.post("/register", data=SIGNUP)
        assert response.status_code == 400
        assert len(expenses_for(user["id"])) == 50

    def test_only_new_user_is_seeded(self, client):
        existing = create_user("Existing", "existing@example.com", "password123")
        client.post("/register", data=SIGNUP)
        assert expenses_for(existing) == []


class TestSeedDummyExpenses:
    TODAY = date(2026, 11, 27)

    @pytest.fixture
    def user(self, app):
        return create_user("Seed", "seed@example.com", "password123")

    def test_returns_count_and_inserts_rows(self, user):
        assert seed_dummy_expenses(user, count=20, today=self.TODAY) == 20
        assert len(expenses_for(user)) == 20

    def test_rows_respect_category_ranges_and_dates(self, user):
        seed_dummy_expenses(
            user, count=200, months=6, today=self.TODAY, rng=random.Random(1)
        )
        earliest = (self.TODAY - timedelta(days=180)).isoformat()
        for row in expenses_for(user):
            assert row["category"] in CATEGORIES
            _, low, high, descriptions = DUMMY_EXPENSE_PROFILE[row["category"]]
            assert low <= row["amount"] <= high
            assert row["description"] in descriptions
            assert earliest <= row["date"] <= self.TODAY.isoformat()

    def test_food_is_most_common(self, user):
        seed_dummy_expenses(user, count=500, today=self.TODAY, rng=random.Random(2))
        counts = {}
        for row in expenses_for(user):
            counts[row["category"]] = counts.get(row["category"], 0) + 1
        assert max(counts, key=counts.get) == "Food"

    def test_profile_covers_every_category(self):
        assert set(DUMMY_EXPENSE_PROFILE) == set(CATEGORIES)

    def test_failure_rolls_back_all_inserts(self, app):
        # user_id 999 doesn't exist -> FK violation -> nothing inserted.
        import sqlite3

        with pytest.raises(sqlite3.IntegrityError):
            seed_dummy_expenses(999, count=10, today=self.TODAY)
        conn = get_db()
        try:
            assert conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0] == 0
        finally:
            conn.close()
