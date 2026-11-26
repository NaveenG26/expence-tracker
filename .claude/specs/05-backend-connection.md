# Spec: Backend Connection

## Overview
Step 5 makes sure every section of the `/profile` page is driven by live
queries against the SQLite database, so each logged-in user sees only their
own data: user info, summary stats, recent transactions and category
breakdown. In Spendly, Step 4 already shipped the profile page wired to real
DB helpers (`get_user_by_id`, `get_expense_summary`, `get_category_totals`,
`get_recent_expenses`). This step closes the remaining gap: category
percentages are now computed server-side and are guaranteed to sum to 100,
and a dedicated test suite locks in the backend-to-page contract.

## Depends on
- Step 1: Database setup (tables and `get_db()` exist)
- Step 2: Registration (users are stored in the database)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 4: Profile page (template renders all four sections from DB helpers)

## Routes
No new routes. The existing `GET /profile` route is modified to pass
`category_breakdown` (from `get_category_breakdown`) instead of raw
`category_totals`.

## Database changes
No database changes. The `users` and `expenses` tables already have all
required columns (`user_id`, `amount`, `category`, `date`, `description`,
`created_at`).

## Templates
- **Modify**: `templates/profile.html`
  - The category breakdown loops over `category_breakdown` and renders the
    server-computed `pct` instead of computing a percentage in Jinja.
  - Amounts are already rendered with ₹ via the `inr` filter; no change.
  - `member_since` is already rendered from `users.created_at` as
    "Month YYYY" via the `datefmt('%B %Y')` filter; no change.

## Files to change
- `database/db.py` — add `get_category_breakdown(user_id)`
- `app.py` — `profile()` passes `category_breakdown`; drop the unused
  `get_category_totals` / `get_db` imports
- `templates/profile.html` — use `c['pct']` from the breakdown
- `CLAUDE.md` — list `get_category_breakdown` among the reusable helpers

## Files to create
- `tests/test_backend_connection.py`

> **Adapted from the course spec:** the course version asked for a new
> `database/queries.py` with `get_user_by_id`, `get_summary_stats`,
> `get_recent_transactions` and `get_category_breakdown`. Spendly's
> CLAUDE.md requires all DB logic in `database/db.py` and forbids duplicate
> queries, so the existing helpers are reused under their current names and
> keys:
>
> | Course spec | Spendly |
> |---|---|
> | `get_user_by_id` → `name`, `email`, `member_since` | `get_user_by_id` → `id`, `name`, `email`, `created_at` (formatted in template) |
> | `get_summary_stats` → `transaction_count` | `get_expense_summary` → `expense_count` |
> | `get_recent_transactions` | `get_recent_expenses` |
> | `get_category_breakdown` → `name`, `amount`, `pct` | `get_category_breakdown` → `category`, `total`, `pct` (new, built on `get_category_totals`) |
> | empty `top_category` = `"—"` | `None` from the helper; the template renders `—` |

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Passwords hashed with werkzeug
- Foreign keys PRAGMA must be enabled on every connection (already done in `get_db()`)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Currency must always display as ₹ — never £ or $
- `member_since` is derived from `users.created_at` and displayed as
  "Month YYYY" (e.g. "January 2026")
- `pct` values in category breakdown must sum to 100; use integer rounding
  and adjust the largest category (first row) to absorb any rounding
  remainder
- If a user has no expenses, helpers return zeros / `None` / empty lists
  rather than raising exceptions
- DB helpers live in `database/db.py`, call `get_db()` internally and close
  the connection before returning

## Tests to write

### Unit tests
File: `tests/test_backend_connection.py`

| Function | Input | Expected output |
|---|---|---|
| `get_user_by_id` | valid `user_id` | row with correct `name`, `email`, `created_at` |
| `get_user_by_id` | non-existent id | `None` |
| `get_expense_summary` | `user_id` with expenses | `total_spent` 283.45, `expense_count` 8, `top_category` "Bills" |
| `get_expense_summary` | `user_id` with no expenses | `{"total_spent": 0, "expense_count": 0, "top_category": None}` |
| `get_recent_expenses` | `user_id` with expenses | list ordered newest-first, each item has `date`, `description`, `category`, `amount` |
| `get_recent_expenses` | `user_id` with no expenses | empty list |
| `get_category_breakdown` | `user_id` with expenses | list ordered by `total` desc; `pct` values are integers summing to 100 |
| `get_category_breakdown` | shares that round to 99 or 101 | largest row absorbs the remainder; sum is 100 |
| `get_category_breakdown` | `user_id` with no expenses | empty list |

### Route tests
`GET /profile` — unauthenticated:
- Redirects to `/login` (302)

`GET /profile` — authenticated as seed user:
- Returns 200
- Response contains the seed user's name ("Demo User")
- Response contains the seed user's email ("demo@spendly.com")
- Response contains ₹ symbol (and no £ or $)
- Total spent matches the sum of all seed expenses (₹283.45)
- Expense count is 8
- Top category is "Bills" (highest single-category total)
- Transaction list has 8 rows in newest-first order
- Category breakdown contains all 7 categories with percentages summing to 100

## Definition of done
- [x] Logging in as the seed user (demo@spendly.com / demo123) shows "Demo User" and "demo@spendly.com" on the profile page
- [x] Total spent displayed on the profile page equals ₹283.45
- [x] Expense count displayed is 8
- [x] Top category displayed is "Bills"
- [x] Recent expenses table shows 8 rows ordered newest date first
- [x] Category breakdown shows 7 categories with percentages that add up to 100%
- [x] All amounts on the page display the ₹ symbol
- [x] Registering a brand-new user and visiting `/profile` shows ₹0.00 total spent, 0 expenses, and the empty state instead of a category breakdown — no errors
