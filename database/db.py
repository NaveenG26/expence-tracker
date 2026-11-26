import sqlite3
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

DB_PATH = "expense_tracker.db"

CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )
    conn.commit()
    conn.close()


def create_user(name, email, password):
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, name, email, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def _date_clause(date_from, date_to):
    """Optional inclusive date-range filter as a fixed SQL fragment.

    Returns ("", ()) unless both bounds are given. The fragment is a
    constant; the dates are always bound as parameters.
    """
    if date_from and date_to:
        return " AND date BETWEEN ? AND ?", (date_from, date_to)
    return "", ()


def get_expense_summary(user_id, date_from=None, date_to=None):
    clause, date_params = _date_clause(date_from, date_to)
    params = (user_id, *date_params)
    conn = get_db()
    try:
        totals = conn.execute(
            """
            SELECT ROUND(COALESCE(SUM(amount), 0), 2) AS total_spent,
                   COUNT(*) AS expense_count
            FROM expenses
            WHERE user_id = ?
            """ + clause,
            params,
        ).fetchone()
        top = conn.execute(
            """
            SELECT category
            FROM expenses
            WHERE user_id = ?
            """ + clause + """
            GROUP BY category
            ORDER BY SUM(amount) DESC, category ASC
            LIMIT 1
            """,
            params,
        ).fetchone()
        return {
            "total_spent": totals["total_spent"],
            "expense_count": totals["expense_count"],
            "top_category": top["category"] if top else None,
        }
    finally:
        conn.close()


def get_category_totals(user_id, date_from=None, date_to=None):
    clause, date_params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        return conn.execute(
            """
            SELECT category, ROUND(SUM(amount), 2) AS total
            FROM expenses
            WHERE user_id = ?
            """ + clause + """
            GROUP BY category
            ORDER BY total DESC, category ASC
            """,
            (user_id, *date_params),
        ).fetchall()
    finally:
        conn.close()


def get_category_breakdown(user_id, date_from=None, date_to=None):
    """Category totals with an integer `pct` share that always sums to 100.

    Each share is rounded to the nearest int; the largest category (first
    row) absorbs any rounding remainder.
    """
    rows = get_category_totals(user_id, date_from=date_from, date_to=date_to)
    grand_total = sum(row["total"] for row in rows)
    if not rows or grand_total <= 0:
        return [
            {"category": row["category"], "total": row["total"], "pct": 0}
            for row in rows
        ]

    breakdown = [
        {
            "category": row["category"],
            "total": row["total"],
            "pct": round(row["total"] / grand_total * 100),
        }
        for row in rows
    ]
    breakdown[0]["pct"] += 100 - sum(item["pct"] for item in breakdown)
    return breakdown


def get_recent_expenses(user_id, limit=10, date_from=None, date_to=None):
    clause, date_params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        return conn.execute(
            """
            SELECT id, amount, category, date, description
            FROM expenses
            WHERE user_id = ?
            """ + clause + """
            ORDER BY date DESC, id DESC
            LIMIT ?
            """,
            (user_id, *date_params, limit),
        ).fetchall()
    finally:
        conn.close()


def seed_db():
    conn = get_db()

    existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing > 0:
        conn.close()
        return

    password_hash = generate_password_hash("demo123")
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", password_hash),
    )
    user_id = cursor.lastrowid

    today = date.today()
    sample_expenses = [
        (25.50, "Food", today - timedelta(days=1), "Groceries"),
        (12.00, "Transport", today - timedelta(days=2), "Bus fare"),
        (85.00, "Bills", today - timedelta(days=3), "Electricity bill"),
        (40.00, "Health", today - timedelta(days=4), "Pharmacy"),
        (18.75, "Entertainment", today - timedelta(days=5), "Movie tickets"),
        (60.00, "Shopping", today - timedelta(days=6), "New shoes"),
        (10.00, "Other", today - timedelta(days=7), "Miscellaneous"),
        (32.20, "Food", today - timedelta(days=8), "Restaurant"),
    ]

    conn.executemany(
        """
        INSERT INTO expenses (user_id, amount, category, date, description)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (user_id, amount, category, d.isoformat(), description)
            for amount, category, d, description in sample_expenses
        ],
    )

    conn.commit()
    conn.close()
