import calendar
import math
import os
import sqlite3
from datetime import date, datetime

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import (
    CATEGORIES,
    create_expense,
    create_user,
    get_category_breakdown,
    get_expense_summary,
    get_recent_expenses,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-key")


# ------------------------------------------------------------------ #
# Template filters                                                    #
# ------------------------------------------------------------------ #

@app.template_filter("inr")
def format_inr(value):
    return f"₹{(value or 0):.2f}"


@app.template_filter("datefmt")
def format_date(value, fmt="%d %b %Y"):
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").strftime(fmt)
    except (TypeError, ValueError):
        return value


# ------------------------------------------------------------------ #
# Date filter helpers                                                 #
# ------------------------------------------------------------------ #

FILTER_ERROR_REVERSED = "Start date must be before end date."


def _parse_iso_date(value):
    try:
        return datetime.strptime((value or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_date_range(args):
    """Return (date_from, date_to, filter_error) from query args.

    Dates come back as normalised ISO strings, or None when the filter
    should not apply (either bound missing, malformed, or reversed).
    """
    start = _parse_iso_date(args.get("date_from"))
    end = _parse_iso_date(args.get("date_to"))
    if start is None or end is None:
        return None, None, None
    if start > end:
        return None, None, FILTER_ERROR_REVERSED
    return start.isoformat(), end.isoformat(), None


def months_ago(d, months):
    """Same day `months` calendar months earlier, clamped to month end."""
    year, month = divmod(d.year * 12 + (d.month - 1) - months, 12)
    month += 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def build_presets(today, date_from=None, date_to=None):
    end = today.isoformat()
    ranges = [
        ("This Month", today.replace(day=1).isoformat(), end),
        ("Last 3 Months", months_ago(today, 3).isoformat(), end),
        ("Last 6 Months", months_ago(today, 6).isoformat(), end),
        ("All Time", None, None),
    ]
    return [
        {
            "label": label,
            "date_from": start,
            "date_to": stop,
            "active": (start, stop) == (date_from, date_to),
        }
        for label, start, stop in ranges
    ]


# ------------------------------------------------------------------ #
# Expense form helpers                                                #
# ------------------------------------------------------------------ #

MAX_AMOUNT = 10_000_000
MAX_DESCRIPTION_LENGTH = 200


def validate_expense_form(form, today):
    """Return (values, error) for an add/edit expense form.

    On success `values` matches create_expense()'s keyword arguments and
    `error` is None. On failure `values` is None. Never reads user_id.
    """
    try:
        amount = float((form.get("amount") or "").strip())
    except ValueError:
        return None, "Enter a valid amount"
    if not math.isfinite(amount):
        return None, "Enter a valid amount"
    amount = round(amount, 2)
    if amount <= 0:
        return None, "Amount must be greater than zero"
    if amount > MAX_AMOUNT:
        return None, "Amount must be 10,000,000 or less"

    category = (form.get("category") or "").strip()
    if category not in CATEGORIES:
        return None, "Choose a valid category"

    expense_date = _parse_iso_date(form.get("date"))
    if expense_date is None:
        return None, "Enter a valid date"
    if expense_date > today:
        return None, "Date cannot be in the future"

    description = (form.get("description") or "").strip() or None
    if description and len(description) > MAX_DESCRIPTION_LENGTH:
        return None, "Description must be 200 characters or fewer"

    return {
        "amount": amount,
        "category": category,
        "date": expense_date.isoformat(),
        "description": description,
    }, None


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    error = None
    if not name:
        error = "Name is required"
    elif not email or "@" not in email:
        error = "Enter a valid email address"
    elif len(password) < 8:
        error = "Password must be at least 8 characters"

    if not error:
        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            error = "An account with that email already exists"

    if error:
        return (
            render_template("register.html", error=error, name=name, email=email),
            400,
        )
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = get_user_by_email(email) if email and password else None
    if user is None or not check_password_hash(user["password_hash"], password):
        return (
            render_template(
                "login.html", error="Invalid email or password", email=email
            ),
            400,
        )

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    user = get_user_by_id(user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    date_from, date_to, filter_error = parse_date_range(request.args)
    date_range = {"date_from": date_from, "date_to": date_to}
    return render_template(
        "profile.html",
        user=user,
        summary=get_expense_summary(user_id, **date_range),
        category_breakdown=get_category_breakdown(user_id, **date_range),
        recent_expenses=get_recent_expenses(user_id, **date_range),
        presets=build_presets(date.today(), date_from, date_to),
        date_from=date_from,
        date_to=date_to,
        filter_error=filter_error,
        is_filtered=date_from is not None,
    )


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    if get_user_by_id(user_id) is None:
        session.clear()
        return redirect(url_for("login"))

    today = date.today()
    form = {"date": today.isoformat()}
    error = None

    if request.method == "POST":
        values, error = validate_expense_form(request.form, today)
        if not error:
            create_expense(user_id, **values)
            return redirect(url_for("profile"))
        form = request.form

    return (
        render_template(
            "add_expense.html",
            form=form,
            error=error,
            categories=CATEGORIES,
            today=today.isoformat(),
        ),
        400 if error else 200,
    )


# ------------------------------------------------------------------ #
# Placeholder routes — implemented in later roadmap steps            #
# ------------------------------------------------------------------ #


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    with app.app_context():
        init_db()
        seed_db()
    app.run(debug=True, port=5001)
