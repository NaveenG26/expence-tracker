from datetime import date

import pytest

from app import build_presets, months_ago, parse_date_range
from database.db import (
    create_user,
    get_category_breakdown,
    get_category_totals,
    get_db,
    get_expense_summary,
    get_recent_expenses,
    seed_db,
)

ERROR_TEXT = b"Start date must be before end date."
EMPTY_TEXT = b"No expenses in this period"


# ------------------------------------------------------------------ #
# Helpers / fixtures                                                  #
# ------------------------------------------------------------------ #

def add_expense(user_id, amount, category, day, description="x"):
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


@pytest.fixture
def user_id(app):
    return create_user("Filter User", "filter@example.com", "secret123")


@pytest.fixture
def populated(user_id):
    """Fixed-date expenses: two in Jan 2026, one on 2026-02-15, one in Mar."""
    add_expense(user_id, 10.00, "Food", "2026-01-05", "jan-food")
    add_expense(user_id, 30.00, "Bills", "2026-01-31", "jan-bills")
    add_expense(user_id, 20.00, "Food", "2026-02-15", "feb-food")
    add_expense(user_id, 40.00, "Transport", "2026-03-01", "mar-transport")
    return user_id


@pytest.fixture
def auth_client(client, populated):
    client.post(
        "/login", data={"email": "filter@example.com", "password": "secret123"}
    )
    return client


# ------------------------------------------------------------------ #
# parse_date_range                                                    #
# ------------------------------------------------------------------ #

class TestParseDateRange:
    def test_valid_range_returned_as_iso_strings(self):
        result = parse_date_range({"date_from": "2026-01-01", "date_to": "2026-01-31"})
        assert result == ("2026-01-01", "2026-01-31", None)

    def test_same_day_range_is_valid(self):
        result = parse_date_range({"date_from": "2026-01-10", "date_to": "2026-01-10"})
        assert result == ("2026-01-10", "2026-01-10", None)

    @pytest.mark.parametrize("args", [
        {},
        {"date_from": "", "date_to": ""},
        {"date_from": "2026-01-01"},
        {"date_to": "2026-01-01"},
        {"date_from": "2026-01-01", "date_to": ""},
    ])
    def test_missing_or_empty_bound_means_no_filter_no_error(self, args):
        assert parse_date_range(args) == (None, None, None)

    @pytest.mark.parametrize("bad", [
        "not-a-date", "2026-13-01", "2026-02-30", "01/02/2026", "2026-1-1x",
        "'; DROP TABLE expenses;--",
    ])
    def test_malformed_date_treated_as_absent_no_error(self, bad):
        assert parse_date_range({"date_from": bad, "date_to": "2026-11-27"}) == (
            None, None, None,
        )
        assert parse_date_range({"date_from": "2026-11-01", "date_to": bad}) == (
            None, None, None,
        )

    def test_reversed_range_returns_error_and_no_dates(self):
        date_from, date_to, error = parse_date_range(
            {"date_from": "2026-02-01", "date_to": "2026-01-01"}
        )
        assert date_from is None and date_to is None
        assert error == "Start date must be before end date."


# ------------------------------------------------------------------ #
# months_ago                                                          #
# ------------------------------------------------------------------ #

class TestMonthsAgo:
    @pytest.mark.parametrize("today, months, expected", [
        (date(2026, 11, 27), 3, date(2026, 8, 27)),
        (date(2026, 11, 27), 6, date(2026, 5, 27)),
        (date(2026, 5, 31), 3, date(2026, 2, 28)),
        (date(2024, 5, 31), 3, date(2024, 2, 29)),
        (date(2026, 8, 31), 6, date(2026, 2, 28)),
        (date(2026, 2, 15), 3, date(2025, 11, 15)),
        (date(2026, 1, 31), 6, date(2025, 7, 31)),
    ])
    def test_months_ago(self, today, months, expected):
        assert months_ago(today, months) == expected


# ------------------------------------------------------------------ #
# build_presets                                                       #
# ------------------------------------------------------------------ #

class TestBuildPresets:
    TODAY = date(2026, 11, 27)

    def by_label(self, presets):
        return {p["label"]: p for p in presets}

    def test_labels_and_order(self):
        presets = build_presets(self.TODAY)
        assert [p["label"] for p in presets] == [
            "This Month", "Last 3 Months", "Last 6 Months", "All Time",
        ]

    def test_preset_ranges(self):
        presets = self.by_label(build_presets(self.TODAY))
        assert (presets["This Month"]["date_from"], presets["This Month"]["date_to"]) == (
            "2026-11-01", "2026-11-27")
        assert (presets["Last 3 Months"]["date_from"], presets["Last 3 Months"]["date_to"]) == (
            "2026-08-27", "2026-11-27")
        assert (presets["Last 6 Months"]["date_from"], presets["Last 6 Months"]["date_to"]) == (
            "2026-05-27", "2026-11-27")
        assert presets["All Time"]["date_from"] is None
        assert presets["All Time"]["date_to"] is None

    def test_month_end_clamping(self):
        presets = self.by_label(build_presets(date(2026, 5, 31)))
        assert presets["Last 3 Months"]["date_from"] == "2026-02-28"

    def test_all_time_active_when_no_filter(self):
        presets = build_presets(self.TODAY)
        active = [p["label"] for p in presets if p["active"]]
        assert active == ["All Time"]

    def test_matching_preset_is_only_active_one(self):
        presets = build_presets(self.TODAY, "2026-08-27", "2026-11-27")
        active = [p["label"] for p in presets if p["active"]]
        assert active == ["Last 3 Months"]

    def test_custom_range_highlights_no_preset(self):
        presets = build_presets(self.TODAY, "2026-01-01", "2026-01-31")
        assert not any(p["active"] for p in presets)


# ------------------------------------------------------------------ #
# DB helpers                                                          #
# ------------------------------------------------------------------ #

class TestDbHelpersFiltered:
    def test_summary_filtered(self, populated):
        s = get_expense_summary(populated, date_from="2026-01-01", date_to="2026-01-31")
        assert s["total_spent"] == pytest.approx(40.00)
        assert s["expense_count"] == 2
        assert s["top_category"] == "Bills"

    def test_bounds_are_inclusive(self, populated):
        s = get_expense_summary(populated, date_from="2026-01-05", date_to="2026-01-31")
        assert s["expense_count"] == 2
        s = get_expense_summary(populated, date_from="2026-02-15", date_to="2026-02-15")
        assert s["expense_count"] == 1
        assert s["total_spent"] == pytest.approx(20.00)

    def test_summary_empty_range(self, populated):
        s = get_expense_summary(populated, date_from="2025-01-01", date_to="2025-01-31")
        assert s["total_spent"] == 0
        assert s["expense_count"] == 0
        assert s["top_category"] is None

    def test_no_filter_returns_everything(self, populated):
        s = get_expense_summary(populated)
        assert s["expense_count"] == 4
        assert s["total_spent"] == pytest.approx(100.00)

    def test_filter_applies_only_when_both_given(self, populated):
        assert get_expense_summary(populated, date_from="2026-03-01")["expense_count"] == 4
        assert get_expense_summary(populated, date_to="2026-01-01")["expense_count"] == 4
        assert len(get_recent_expenses(populated, date_from="2026-03-01")) == 4
        assert len(get_category_totals(populated, date_to="2026-01-01")) == 3

    def test_category_totals_filtered(self, populated):
        rows = get_category_totals(populated, date_from="2026-01-01", date_to="2026-02-28")
        totals = {r["category"]: r["total"] for r in rows}
        assert totals == {"Food": pytest.approx(30.00), "Bills": pytest.approx(30.00)}

    def test_category_breakdown_filtered_pct_sums_to_100(self, populated):
        rows = get_category_breakdown(populated, date_from="2026-01-01", date_to="2026-02-28")
        assert {r["category"] for r in rows} == {"Food", "Bills"}
        assert sum(r["pct"] for r in rows) == 100

    @pytest.mark.parametrize("start, end", [
        ("2026-01-01", "2026-03-31"),
        ("2026-01-01", "2026-01-31"),
        ("2026-01-05", "2026-02-15"),
    ])
    def test_breakdown_pct_sums_to_100_for_ranges(self, populated, start, end):
        rows = get_category_breakdown(populated, date_from=start, date_to=end)
        assert rows and sum(r["pct"] for r in rows) == 100

    def test_recent_expenses_filtered_and_ordered(self, populated):
        rows = get_recent_expenses(populated, date_from="2026-01-01", date_to="2026-02-28")
        assert [r["description"] for r in rows] == ["feb-food", "jan-bills", "jan-food"]

    def test_recent_expenses_limit_still_applies(self, populated):
        rows = get_recent_expenses(
            populated, limit=2, date_from="2026-01-01", date_to="2026-03-31"
        )
        assert [r["description"] for r in rows] == ["mar-transport", "feb-food"]

    def test_filter_is_scoped_to_user(self, populated):
        other = create_user("Other", "other@example.com", "secret123")
        add_expense(other, 999.00, "Other", "2026-01-10", "other-expense")
        s = get_expense_summary(populated, date_from="2026-01-01", date_to="2026-01-31")
        assert s["total_spent"] == pytest.approx(40.00)
        rows = get_recent_expenses(populated, date_from="2026-01-01", date_to="2026-01-31")
        assert "other-expense" not in [r["description"] for r in rows]


# ------------------------------------------------------------------ #
# Route                                                               #
# ------------------------------------------------------------------ #

class TestProfileRoute:
    def test_filtered_url_requires_login(self, client):
        response = client.get("/profile?date_from=2026-01-01&date_to=2026-01-31")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_no_params_shows_seed_data_unfiltered(self, client):
        seed_db()
        client.post("/login", data={"email": "demo@brokeaf.com", "password": "demo123"})
        response = client.get("/profile")
        assert response.status_code == 200
        assert "₹283.45".encode() in response.data
        assert b"Bills" in response.data

    def test_filter_bar_present_with_all_presets_and_form(self, auth_client):
        body = auth_client.get("/profile").data
        for label in (b"This Month", b"Last 3 Months", b"Last 6 Months", b"All Time"):
            assert label in body
        assert b"filter-preset" in body
        assert b'name="date_from"' in body
        assert b'name="date_to"' in body
        assert b'type="date"' in body
        assert b"Apply" in body

    def test_filter_bar_appears_before_stats(self, auth_client):
        body = auth_client.get("/profile").data
        assert body.index(b"filter-preset") < body.index("₹".encode())

    def test_custom_range_filters_stats_and_lists(self, auth_client):
        response = auth_client.get("/profile?date_from=2026-02-15&date_to=2026-02-15")
        body = response.data
        assert response.status_code == 200
        assert "₹20.00".encode() in body
        assert b"feb-food" in body
        assert b"jan-food" not in body
        assert b"mar-transport" not in body
        assert b"jan-bills" not in body
        assert EMPTY_TEXT not in body

    def test_custom_range_prefills_inputs(self, auth_client):
        body = auth_client.get("/profile?date_from=2026-01-01&date_to=2026-01-31").data
        assert b'value="2026-01-01"' in body
        assert b'value="2026-01-31"' in body

    def test_custom_range_highlights_no_preset(self, auth_client):
        body = auth_client.get("/profile?date_from=2026-01-01&date_to=2026-01-31").data
        assert b"is-active" not in body

    def test_no_filter_highlights_all_time(self, auth_client):
        body = auth_client.get("/profile").data
        assert body.count(b"is-active") == 1

    def test_unfiltered_shows_all_expenses(self, auth_client):
        body = auth_client.get("/profile").data
        for desc in (b"jan-food", b"jan-bills", b"feb-food", b"mar-transport"):
            assert desc in body
        assert "₹100.00".encode() in body

    def test_empty_range_shows_empty_state(self, auth_client):
        response = auth_client.get("/profile?date_from=2020-01-01&date_to=2020-01-31")
        body = response.data
        assert response.status_code == 200
        assert EMPTY_TEXT in body
        assert "₹0.00".encode() in body
        assert "—".encode() in body
        assert b"No expenses yet" not in body

    def test_empty_state_not_shown_for_unfiltered_user_without_expenses(self, client, user_id):
        client.post("/login", data={"email": "filter@example.com", "password": "secret123"})
        body = client.get("/profile").data
        assert EMPTY_TEXT not in body

    def test_reversed_range_shows_error_and_unfiltered_view(self, auth_client):
        response = auth_client.get("/profile?date_from=2026-02-01&date_to=2026-01-01")
        body = response.data
        assert response.status_code == 200
        assert ERROR_TEXT in body
        assert "₹100.00".encode() in body
        assert b"mar-transport" in body

    @pytest.mark.parametrize("query", [
        "date_from=not-a-date&date_to=2026-11-27",
        "date_from=2026-01-01&date_to=garbage",
        "date_from=&date_to=",
        "date_from=2026-11-01",
        "date_to=2026-11-01",
        "date_from=2026-02-30&date_to=2026-03-01",
        "date_from=%27%3B%20DROP%20TABLE%20expenses%3B--&date_to=2026-03-01",
    ])
    def test_invalid_or_partial_params_render_unfiltered_without_error(
        self, auth_client, query
    ):
        response = auth_client.get("/profile?" + query)
        assert response.status_code == 200
        assert "₹100.00".encode() in response.data
        assert ERROR_TEXT not in response.data

    def test_sql_injection_string_does_not_damage_data(self, auth_client, populated):
        auth_client.get("/profile?date_from=%27%3B%20DROP%20TABLE%20expenses%3B--&date_to=x")
        assert get_expense_summary(populated)["expense_count"] == 4

    def test_amounts_show_rupee_symbol_when_filtered(self, auth_client):
        body = auth_client.get("/profile?date_from=2026-01-01&date_to=2026-01-31").data
        assert "₹40.00".encode() in body
        assert "₹0.00".encode() not in body

    def test_filtered_breakdown_only_includes_range_categories(self, auth_client):
        body = auth_client.get("/profile?date_from=2026-03-01&date_to=2026-03-31").data
        assert b"Transport" in body
        assert b"jan-food" not in body


class TestPresetLinksOnRoute:
    def test_preset_links_carry_computed_dates(self, auth_client):
        today = date.today()
        body = auth_client.get("/profile").data
        this_month = f"date_from={today.replace(day=1).isoformat()}".encode()
        assert this_month in body
        assert f"date_to={today.isoformat()}".encode() in body
        assert f"date_from={months_ago(today, 3).isoformat()}".encode() in body
        assert f"date_from={months_ago(today, 6).isoformat()}".encode() in body

    def test_this_month_preset_is_active_and_filters(self, client, user_id):
        today = date.today()
        add_expense(user_id, 12.34, "Food", today.isoformat(), "today-item")
        add_expense(user_id, 55.00, "Bills", "2000-01-01", "ancient-item")
        client.post("/login", data={"email": "filter@example.com", "password": "secret123"})
        url = f"/profile?date_from={today.replace(day=1).isoformat()}&date_to={today.isoformat()}"
        body = client.get(url).data
        assert b"today-item" in body
        assert b"ancient-item" not in body
        assert body.count(b"is-active") == 1
        assert "₹12.34".encode() in body

    def test_last_3_months_excludes_older_expenses(self, client, user_id):
        today = date.today()
        add_expense(user_id, 5.00, "Food", today.isoformat(), "recent-item")
        add_expense(user_id, 7.00, "Food", "2000-01-01", "ancient-item")
        client.post("/login", data={"email": "filter@example.com", "password": "secret123"})
        url = (f"/profile?date_from={months_ago(today, 3).isoformat()}"
               f"&date_to={today.isoformat()}")
        body = client.get(url).data
        assert b"recent-item" in body
        assert b"ancient-item" not in body
        assert body.count(b"is-active") == 1
