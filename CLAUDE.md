# CLAUDE.md

## Project overview

BrokeAF is a lightweight personal expense tracker built with Flask and SQLite.

---

## Architecture
```
brokeaf/
├── app.py              # All routes — single file, no blueprints
├── database/
│   └── db.py           # SQLite helpers: get_db(), init_db(), seed_db(), user/expense queries
├── templates/
│   ├── base.html       # Shared layout — all templates must extend this
│   └── *.html          # One template per page
├── static/
│   ├── css/
│   │   ├── style.css       # Global styles
│   │   ├── profile.css     # Profile-page-only styles
│   │   └── add_expense.css # Add-expense-page-only styles
│   └── js/
│       └── main.js         # Vanilla JS only
└── requirements.txt
```

**Where things belong:**
- New routes → `app.py` only, no blueprints
- DB logic → `database/db.py` only, never inline in routes
- New pages → new `.html` file extending `base.html`
- Page-specific styles → new `.css` file, not inline `<style>` tags

---

## Code style

- Python: PEP 8, snake_case for all variables and functions
- Templates: Jinja2 with `url_for()` for every internal link — never hardcode URLs
- Route functions: one responsibility only — fetch data, render template, done
- DB queries: always use parameterized queries (`?` placeholders) — never f-strings in SQL
- Error handling: use `abort()` for HTTP errors, not bare `return "error string"`

---

## Tech constraints

- **Flask only** — no FastAPI, no Django, no other web frameworks
- **SQLite only** — no PostgreSQL, no SQLAlchemy ORM, no external DB
- **Vanilla JS only** — no React, no jQuery, no npm packages
- **No new pip packages** — work within `requirements.txt` as-is unless explicitly told otherwise
- Python 3.10+ assumed — f-strings and `match` statements are fine

---

## Subagent Policy
- Always use a builtin explore subagent for codebase exploration 
  before implementing any new feature
- Always use a subagent to verify test results 
  after any implementation
- When asked to plan, delegate codebase research 
  to a subagent before presenting the plan
- always use a builtin plan subagent in plan mode

---

## Commands
```bash
# Setup
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run dev server (port 5001)
python app.py

# Run all tests
pytest

# Run a specific test file
pytest tests/test_foo.py

# Run a specific test by name
pytest -k "test_name"

# Run tests with output visible
pytest -s
```

---

## Implemented vs stub routes

| Route | Status |
|---|---|
| `GET /` | Implemented — renders `landing.html` |
| `GET/POST /register` | Implemented — renders `register.html`, creates the user, redirects to `/login` |
| `GET/POST /login` | Implemented — renders `login.html`, authenticates and sets session |
| `GET /logout` | Implemented — clears session, redirects to `/` |
| `GET /profile` | Implemented — renders `profile.html` (login required): account info, stats, category breakdown, recent expenses. Optional `date_from` / `date_to` query params (`YYYY-MM-DD`, both required, inclusive) filter all sections |
| `GET/POST /expenses/add` | Implemented — renders `add_expense.html` (login required), validates via `validate_expense_form()`, inserts via `create_expense`, redirects to `/profile` |
| `GET /expenses/<id>/edit` | Stub — Step 8 |
| `GET /expenses/<id>/delete` | Stub — Step 9 |

**Do not implement a stub route unless the active task explicitly targets that step.**

---

## Warnings and things to avoid

- **Never use raw string returns for stub routes** once a step is implemented — always render a template
- **Never hardcode URLs** in templates — always use `url_for()`
- **Never put DB logic in route functions** — it belongs in `database/db.py`
- **Never install new packages** mid-feature without flagging it — keep `requirements.txt` in sync
- **Never use JS frameworks** — the frontend is intentionally vanilla
- **Reuse existing DB helpers** — `create_user`, `get_user_by_email`, `get_user_by_id`, `get_expense_summary`, `get_category_totals`, `get_category_breakdown`, `get_recent_expenses`, `create_expense` already exist in `database/db.py`; don't write duplicate queries. Expense form validation lives in `validate_expense_form()` in `app.py` — reuse it for edit (Step 8). The expense helpers accept optional `date_from` / `date_to` kwargs — extend them rather than adding `*_filtered` copies
- **Login-required routes** start with `user = get_current_user()` (in `app.py`) and redirect to `login` when it returns `None` — don't re-inline the session/stale-user check
- **CSRF**: every `<form method="POST">` must include `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`; a `before_request` hook rejects POSTs without a valid token (`abort(400)`). Tests run with `CSRF_ENABLED = False` (see `tests/conftest.py`), and the shared `user_id` / `auth_client` fixtures live there too
- **FK enforcement is manual** — SQLite foreign keys are off by default; `get_db()` must run `PRAGMA foreign_keys = ON` on every connection
- The app runs on **port 5001**, not the Flask default 5000 — don't change this