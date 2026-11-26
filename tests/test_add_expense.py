import re
from datetime import date, timedelta

import pytest

from database import db as db_module
from database.db import CATEGORIES, create_user, get_db

URL = "/expenses/add"
EMAIL = "tester@example.com"
PASSWORD = "secret123"


@pytest.fixture
def user_id(app):
    return create_user("Tester", EMAIL, PASSWORD)


@pytest.fixture
def auth_client(client, user_id):
    client.post("/login", data={"email": EMAIL, "password": PASSWORD})
    return client


def valid_form(**overrides):
    data = {
        "amount": "25.50",
        "category": "Food",
        "date": date.today().isoformat(),
        "description": "Lunch",
    }
    data.update(overrides)
    return data


def fetch_expenses():
    conn = get_db()
    try:
        return conn.execute(
            "SELECT user_id, amount, category, date, description FROM expenses"
        ).fetchall()
    finally:
        conn.close()


def count_expenses():
    return len(fetch_expenses())


class TestAuthGuard:
    def test_get_logged_out_redirects_to_login(self, client):
        response = client.get(URL)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_post_logged_out_redirects_and_inserts_nothing(self, client):
        response = client.post(URL, data=valid_form())
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
        assert count_expenses() == 0

    def test_stale_session_user_redirects_to_login(self, auth_client, user_id):
        conn = get_db()
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        response = auth_client.get(URL)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
        with auth_client.session_transaction() as sess:
            assert "user_id" not in sess

    def test_stale_session_user_post_inserts_nothing(self, auth_client, user_id):
        conn = get_db()
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        response = auth_client.post(URL, data=valid_form())
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
        assert count_expenses() == 0


class TestGetForm:
    def test_get_returns_200(self, auth_client):
        assert auth_client.get(URL).status_code == 200

    def test_get_prefills_todays_date(self, auth_client):
        response = auth_client.get(URL)
        assert date.today().isoformat().encode() in response.data

    def test_get_lists_all_categories(self, auth_client):
        response = auth_client.get(URL)
        assert len(CATEGORIES) == 7
        for category in CATEGORIES:
            assert category.encode() in response.data, category

    def test_get_has_no_error_banner(self, auth_client):
        response = auth_client.get(URL)
        assert b"auth-error" not in response.data


class TestValidPost:
    def test_valid_post_redirects_to_profile(self, auth_client):
        response = auth_client.post(URL, data=valid_form())
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")

    def test_valid_post_inserts_row_for_session_user(self, auth_client, user_id):
        auth_client.post(URL, data=valid_form())
        rows = fetch_expenses()
        assert len(rows) == 1
        row = rows[0]
        assert row["user_id"] == user_id
        assert row["amount"] == 25.50
        assert row["category"] == "Food"
        assert row["date"] == date.today().isoformat()
        assert row["description"] == "Lunch"

    def test_amount_rounded_to_two_decimals(self, auth_client):
        auth_client.post(URL, data=valid_form(amount="12.345"))
        rows = fetch_expenses()
        assert len(rows) == 1
        assert rows[0]["amount"] == 12.35

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_blank_description_stored_as_null(self, auth_client, blank):
        auth_client.post(URL, data=valid_form(description=blank))
        rows = fetch_expenses()
        assert len(rows) == 1
        assert rows[0]["description"] is None

    def test_missing_description_field_stored_as_null(self, auth_client):
        data = valid_form()
        del data["description"]
        auth_client.post(URL, data=data)
        rows = fetch_expenses()
        assert len(rows) == 1
        assert rows[0]["description"] is None

    def test_description_whitespace_stripped(self, auth_client):
        auth_client.post(URL, data=valid_form(description="   Dinner out  "))
        assert fetch_expenses()[0]["description"] == "Dinner out"

    def test_description_200_chars_accepted(self, auth_client):
        desc = "a" * 200
        response = auth_client.post(URL, data=valid_form(description=desc))
        assert response.status_code == 302
        assert fetch_expenses()[0]["description"] == desc

    def test_amount_at_maximum_accepted(self, auth_client):
        response = auth_client.post(URL, data=valid_form(amount="10000000"))
        assert response.status_code == 302
        assert fetch_expenses()[0]["amount"] == 10000000

    def test_past_date_accepted(self, auth_client):
        past = (date.today() - timedelta(days=30)).isoformat()
        response = auth_client.post(URL, data=valid_form(date=past))
        assert response.status_code == 302
        assert fetch_expenses()[0]["date"] == past

    @pytest.mark.parametrize("category", CATEGORIES)
    def test_every_category_accepted(self, auth_client, category):
        response = auth_client.post(URL, data=valid_form(category=category))
        assert response.status_code == 302
        assert fetch_expenses()[0]["category"] == category

    def test_new_expense_appears_on_profile(self, auth_client):
        auth_client.post(URL, data=valid_form(description="Unique snack xyz"))
        response = auth_client.get("/profile")
        assert response.status_code == 200
        assert b"Unique snack xyz" in response.data
        assert "₹25.50".encode() in response.data or "₹25.5".encode() in response.data

    def test_sql_injection_description_stored_as_text(self, auth_client):
        evil = "x'); DROP TABLE expenses;--"
        auth_client.post(URL, data=valid_form(description=evil))
        rows = fetch_expenses()
        assert len(rows) == 1
        assert rows[0]["description"] == evil


INVALID_CASES = [
    ("amount", "0", "Amount must be greater than zero"),
    ("amount", "-5", "Amount must be greater than zero"),
    ("amount", "abc", "Enter a valid amount"),
    ("amount", "", "Enter a valid amount"),
    ("amount", "nan", "Enter a valid amount"),
    ("amount", "inf", "Enter a valid amount"),
    ("amount", "0.001", "Amount must be greater than zero"),
    ("amount", "10000000.01", "Amount must be 10,000,000 or less"),
    ("category", "Groceries", "Choose a valid category"),
    ("category", "food", "Choose a valid category"),
    ("category", "", "Choose a valid category"),
    ("date", "", "Enter a valid date"),
    ("date", "not-a-date", "Enter a valid date"),
    ("date", "2024-13-45", "Enter a valid date"),
    ("date", "27/11/2024", "Enter a valid date"),
    ("description", "a" * 201, "Description must be 200 characters or fewer"),
]


class TestInvalidPost:
    @pytest.mark.parametrize("field,value,message", INVALID_CASES)
    def test_invalid_value_returns_400_with_message_and_no_insert(
        self, auth_client, field, value, message
    ):
        response = auth_client.post(URL, data=valid_form(**{field: value}))
        assert response.status_code == 400
        assert any(m.encode() in response.data for m in message.split("|")), message
        assert count_expenses() == 0

    def test_zero_amount_gets_greater_than_zero_message(self, auth_client):
        response = auth_client.post(URL, data=valid_form(amount="0"))
        assert response.status_code == 400
        assert b"Amount must be greater than zero" in response.data

    def test_missing_category_field_returns_400(self, auth_client):
        data = valid_form()
        del data["category"]
        response = auth_client.post(URL, data=data)
        assert response.status_code == 400
        assert b"Choose a valid category" in response.data
        assert count_expenses() == 0

    def test_missing_date_field_returns_400(self, auth_client):
        data = valid_form()
        del data["date"]
        response = auth_client.post(URL, data=data)
        assert response.status_code == 400
        assert b"Enter a valid date" in response.data
        assert count_expenses() == 0

    def test_missing_amount_field_returns_400(self, auth_client):
        data = valid_form()
        del data["amount"]
        response = auth_client.post(URL, data=data)
        assert response.status_code == 400
        assert b"Enter a valid amount" in response.data
        assert count_expenses() == 0

    def test_future_date_returns_400(self, auth_client):
        future = (date.today() + timedelta(days=1)).isoformat()
        response = auth_client.post(URL, data=valid_form(date=future))
        assert response.status_code == 400
        assert b"Date cannot be in the future" in response.data
        assert count_expenses() == 0

    def test_error_page_still_lists_categories(self, auth_client):
        response = auth_client.post(URL, data=valid_form(amount="abc"))
        assert response.status_code == 400
        for category in CATEGORIES:
            assert category.encode() in response.data


class TestRefillAfterError:
    def test_submitted_values_are_refilled(self, auth_client):
        response = auth_client.post(
            URL,
            data=valid_form(
                amount="abc", description="Keep me please", category="Bills"
            ),
        )
        assert response.status_code == 400
        assert b"abc" in response.data
        assert b"Keep me please" in response.data

    def test_submitted_category_is_selected(self, auth_client):
        response = auth_client.post(
            URL, data=valid_form(amount="-1", category="Bills")
        )
        assert response.status_code == 400
        html = response.get_data(as_text=True)
        options = re.findall(r"<option\b[^>]*>", html)
        selected = [o for o in options if "selected" in o]
        assert any("Bills" in o for o in selected), selected
        assert not any("Food" in o for o in selected), selected

    def test_submitted_date_is_refilled(self, auth_client):
        past = (date.today() - timedelta(days=3)).isoformat()
        response = auth_client.post(
            URL, data=valid_form(date=past, amount="abc")
        )
        assert response.status_code == 400
        assert past.encode() in response.data


class TestUserIdIgnored:
    def test_form_user_id_is_ignored(self, auth_client, user_id):
        other_id = create_user("Other", "other@example.com", "pw123456")
        assert other_id != user_id
        response = auth_client.post(URL, data=valid_form(user_id=str(other_id)))
        assert response.status_code == 302
        rows = fetch_expenses()
        assert len(rows) == 1
        assert rows[0]["user_id"] == user_id


class TestProfileLink:
    def test_profile_has_add_expense_link_without_expenses(self, auth_client):
        response = auth_client.get("/profile")
        assert response.status_code == 200
        assert b'href="/expenses/add"' in response.data
        assert b"Add expense" in response.data

    def test_profile_has_add_expense_link_with_expenses(self, auth_client):
        auth_client.post(URL, data=valid_form())
        response = auth_client.get("/profile")
        assert b'href="/expenses/add"' in response.data
        assert b"Add expense" in response.data


class TestStubsUntouched:
    def test_edit_stub_still_placeholder(self, client):
        response = client.get("/expenses/1/edit")
        assert response.status_code == 200
        assert b"coming in Step 8" in response.data

    def test_delete_stub_still_placeholder(self, client):
        response = client.get("/expenses/1/delete")
        assert response.status_code == 200
        assert b"coming in Step 9" in response.data


def test_db_path_is_isolated(app):
    assert db_module.DB_PATH != "expense_tracker.db"
