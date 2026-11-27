# BrokeAF

A lightweight personal expense tracker built with **Flask** and **SQLite**. Log an expense in a few seconds, then see where your money went by category and date range, in rupees.

It runs on server-rendered Jinja templates and vanilla JavaScript, with no ORM, no front-end framework and only four pip dependencies.

## Features

- **Accounts**: sign up, log in and log out, with Werkzeug password hashing and session auth
- **Profile dashboard**: account info, spending stats, category breakdown and recent expenses
- **Date filtering**: filter every section by a custom range or a preset such as the last 3 months
- **Add expenses**: a validated form for amount, category, date and an optional description
- **Demo data on sign-up**: new accounts get about 50 realistic expenses spread over six months, so the dashboard isn't empty on first login
- **Security basics**: CSRF tokens on every POST form, parameterised SQL, SameSite session cookies and enforced foreign keys

Editing and deleting expenses are on the roadmap (Steps 8 and 9).

## Quick start

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open <http://localhost:5001>. On first run the app creates `expense_tracker.db` and a demo account:

| Email | Password |
|---|---|
| `demo@spendly.com` | `demo123` |

Set `SECRET_KEY` in your environment for anything beyond local development.

## Running tests

```bash
python -m pytest            # full suite
python -m pytest tests/test_add_expense.py
python -m pytest -k "csrf"
```

Tests use a temporary database and switch off CSRF checks through the fixtures in `tests/conftest.py`.

## Project structure

```
app.py              # All routes (no blueprints)
database/db.py      # SQLite helpers and queries
templates/          # One Jinja template per page, all extending base.html
static/css/         # Global styles plus page-specific stylesheets
static/js/main.js   # Vanilla JS
tests/              # pytest suite, one file per feature
.claude/            # Claude Code specs, slash commands, subagents and skills
```

## How it's built

BrokeAF is built with [Claude Code](https://claude.com/claude-code) through a spec-driven workflow that lives in `.claude/`:

1. **`/create-spec`** creates a feature branch and writes a spec covering routes, validation rules, files to change and acceptance criteria.
2. The feature is implemented against the spec, following the rules in `CLAUDE.md`.
3. **`/test-feature`**: the `spec-test-writer` subagent writes pytest tests from the spec rather than the code, then `spec-test-runner` runs them and classifies each failure.
4. **`/code-review-feature`**: the quality and security reviewer subagents review the branch diff in parallel.
5. Fixes are committed, the PR is merged, and anything learned goes back into `CLAUDE.md`.

## Tech constraints

Flask only, SQLite only, vanilla JS only, and no new packages beyond `requirements.txt`. See `CLAUDE.md` for the full conventions.
