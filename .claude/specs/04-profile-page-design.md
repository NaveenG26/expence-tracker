# Spec: Profile Page

## Overview
Replace the `/profile` placeholder with a real, designed page for the logged-in user. The page shows an account summary (name, email, member-since date), headline spending stats (total spent, number of expenses, top category), a per-category breakdown, and a table of recent expenses. This is Step 4 of the Spendly roadmap: Step 3 sets `session["user_id"]` and redirects to `/profile` after login, and this step gives that redirect a real destination and the first read-only view of the data later steps (add/edit/delete) will modify.

## Depends on
- Step 1 — Database setup (`users` and `expenses` tables, `get_db()`, `seed_db()`)
- Step 2 — Registration
- Step 3 — Login and logout (`session["user_id"]`, `session["user_name"]`)

## Routes
- `GET /profile` — render the profile page for the current user; if not logged in, redirect to `/login` — logged-in

No other new routes. `/expenses/add`, `/expenses/<id>/edit` and `/expenses/<id>/delete` remain stubs (Steps 7–9).

## Database changes
No schema changes. The existing `users` (`id`, `name`, `email`, `created_at`) and `expenses` (`user_id`, `amount`, `category`, `date`, `description`) tables hold everything needed.

Add read-only helpers to `database/db.py` (DB logic must not live in routes):
- `get_user_by_id(user_id)` — parameterised SELECT of `id, name, email, created_at`; returns `sqlite3.Row` or `None`
- `get_expense_summary(user_id)` — returns total spent, expense count (zero values when the user has no expenses)
- `get_category_totals(user_id)` — returns rows of `category`, `total` ordered by total descending
- `get_recent_expenses(user_id, limit=10)` — returns the user's latest expenses ordered by `date DESC, id DESC`

All helpers filter by `user_id`, use `?` placeholders, and close the connection in `try/finally`.

## Templates
- **Create:** `templates/profile.html` — extends `base.html`; sections: profile header, stat cards, category breakdown, recent expenses table, empty state when the user has no expenses
- **Modify:**
  - `templates/base.html` — make the navbar user name a link to `url_for('profile')`

## Files to change
- `app.py` — replace the `/profile` stub; import the new helpers
- `database/db.py` — add the four helpers above
- `templates/base.html` — link the nav user name to the profile
- `CLAUDE.md` — mark `GET /profile` as implemented in the route table

## Files to create
- `templates/profile.html`
- `static/css/profile.css` — page-specific styles, loaded via `{% block head %}` (no inline `<style>`)
- `tests/test_profile.py` — pytest tests for the profile route and helpers

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never build SQL with f-strings or `%`
- Passwords hashed with werkzeug; the profile page must never read or display `password_hash`
- Use CSS variables from `style.css` — never hardcode hex values
- All templates extend `base.html`
- All routes stay in `app.py` (no blueprints); all DB logic stays in `database/db.py`
- Route function does one thing: check session, call helpers, render template
- Unauthenticated access redirects to `url_for('login')`; if the session user no longer exists, clear the session and redirect to login
- A user may only ever see their own data — always scope queries by `session["user_id"]`
- Every internal link uses `url_for()` — never hardcode URLs
- Vanilla JS only; the page should work without any JS
- Format currency consistently (two decimals) via a Jinja filter or in the template
- Layout must be responsive (stat cards and table usable on mobile widths)
- Do not implement any other stub route (`/expenses/*`)
- Per `CLAUDE.md` Subagent Policy: explore with a builtin explore subagent before implementing, and verify test results with a subagent afterwards

## Definition of done
- [ ] Visiting `/profile` while logged out redirects to `/login`
- [ ] Logging in as `demo@spendly.com` / `demo123` lands on a styled profile page (not the placeholder text)
- [ ] The header shows the user's name, email and member-since date
- [ ] Stat cards show correct total spent, expense count and top category for the seeded demo data (total 283.45, 8 expenses, top category Bills)
- [ ] Category breakdown lists each category with its total, highest first
- [ ] Recent expenses table shows date, description, category and amount, newest first
- [ ] A newly registered user with no expenses sees a friendly empty state and zero stats with no errors
- [ ] One user never sees another user's expenses
- [ ] The navbar user name links to `/profile`
- [ ] No hardcoded hex values or inline `<style>` tags in the new files
- [ ] Page is usable at ~375px width
- [ ] `pytest tests/test_profile.py` passes
- [ ] App starts with `python app.py` without errors
