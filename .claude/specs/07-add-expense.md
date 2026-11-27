# Spec: Add Expense

## Overview
Step 7 replaces the `/expenses/add` stub with a working form that lets a
logged-in user record a new expense: amount, category, date and an optional
description. Until now the only expenses in the app come from `seed_db()`,
so the profile page's "Add your first expense" link leads nowhere. This step
makes BrokeAF usable for real tracking and is the first write path for the
`expenses` table, ahead of edit (Step 8) and delete (Step 9).

## Depends on
- Step 1: Database setup (`expenses` table, `CATEGORIES` list in
  `database/db.py`, `get_db()` with `PRAGMA foreign_keys = ON`)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 5: Backend connection (profile page reads expenses via
  `get_expense_summary`, `get_category_breakdown`, `get_recent_expenses`)
- Step 6: Date filter (profile page accepts `date_from` / `date_to`)

## Routes
- `GET /expenses/add` — render the empty add-expense form, with the date
  field defaulting to today — logged-in
- `POST /expenses/add` — validate the form, insert the expense for the
  current user, redirect to `/profile` — logged-in

Both methods share the existing `add_expense` endpoint (update the decorator
to `methods=["GET", "POST"]`). Unauthenticated requests redirect to
`url_for('login')`, the same as `/profile`. If `session["user_id"]` points to
a user that no longer exists, clear the session and redirect to login.

### Validation (POST)
On any error, re-render `add_expense.html` with status **400**, a single
`error` message, and the submitted values pre-filled.
- **amount**: required; must parse as a number; must be `> 0`; at most
  `10,000,000`. Round to 2 decimal places before storing.
  Errors: "Enter a valid amount", "Amount must be greater than zero",
  "Amount must be 10,000,000 or less".
- **category**: required; must be one of `CATEGORIES` exactly.
  Error: "Choose a valid category".
- **date**: required; must parse as `YYYY-MM-DD`; must not be in the future.
  Errors: "Enter a valid date", "Date cannot be in the future".
- **description**: optional; strip whitespace; store `NULL` when empty;
  max 200 characters. Error: "Description must be 200 characters or fewer".

The `user_id` always comes from the session, never from the form.

## Database changes
No database changes. The existing `expenses` table already has `user_id`,
`amount`, `category`, `date`, `description` and `created_at`.

Add one helper to `database/db.py`:
- `create_expense(user_id, amount, category, date, description=None)`:
  parameterised `INSERT`, commit, return `cursor.lastrowid`, close the
  connection in a `finally` block (same pattern as `create_user`).

## Templates
- **Create:** `templates/add_expense.html`
  - Extends `base.html`; title "Add expense — BrokeAF"
  - Reuses the existing form classes (`auth-section`, `auth-card`,
    `form-group`, `form-input`, `btn-submit`, `auth-error`)
  - Form: `method="POST" action="{{ url_for('add_expense') }}"`
    - `amount`: `<input type="number" step="0.01" min="0.01">`, required
    - `category`: `<select>` built from `CATEGORIES` passed by the route,
      with a disabled "Choose a category" placeholder; keeps the submitted
      choice selected on error
    - `date`: `<input type="date">`, required, `max` set to today, value
      defaults to today
    - `description`: `<input type="text" maxlength="200">`, optional
  - Error banner shown when `error` is set
  - A "Cancel" link back to `url_for('profile')`
- **Modify:** `templates/profile.html`
  - Add an "Add expense" button (`url_for('add_expense')`) to the profile
    header or the recent expenses card, so it is reachable when the user
    already has expenses (the empty-state link already exists)

## Files to change
- `app.py`
  - Import `create_expense` and `CATEGORIES` from `database.db`
  - Replace the `add_expense` stub with the GET/POST implementation above
  - Put form validation in a small helper (e.g. `validate_expense_form(form)`
    returning `(values, error)`) so it can be reused by Step 8 edit, and so
    the route itself just fetches, validates, saves and redirects
  - Move `add_expense` out of the "Placeholder routes" section
- `database/db.py`: add `create_expense()`
- `templates/profile.html`: add the "Add expense" button
- `static/css/profile.css`: style for the header button if needed
- `CLAUDE.md`: mark `GET/POST /expenses/add` as Implemented and add
  `create_expense` to the list of DB helpers to reuse

## Files to create
- `templates/add_expense.html`
- `static/css/add_expense.css` (only if the shared form styles are not
  enough, e.g. for the `<select>` or a two-button action row)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders, never f-strings in SQL)
- Passwords hashed with werkzeug (no password handling in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives in `database/db.py` only; the route calls `create_expense()`
- Use `url_for()` for every internal link and form action
- `user_id` comes from the session only; ignore any `user_id` in the form
- Validate server-side even though the inputs have HTML5 constraints
- Category list comes from `CATEGORIES` in `database/db.py`; do not duplicate
  it in the template or `app.py`
- Do not touch the edit or delete stubs (Steps 8 and 9)
- Vanilla JS only, and none should be needed for this step

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in shows the form with today's
      date pre-filled and all 7 categories in the dropdown
- [ ] Submitting a valid expense redirects to `/profile`, where it appears
      at the top of Recent expenses and the total spent and expense count
      update
- [ ] The new row in `expenses` has the logged-in user's `user_id`, the
      amount rounded to 2 dp, and `NULL` description when left blank
- [ ] Amount of `0`, a negative value, or non-numeric text gets a 400 and an
      error message, and nothing is inserted
- [ ] A category not in `CATEGORIES` (e.g. edited via devtools) gets a 400
      and an error message
- [ ] A missing, malformed or future date gets a 400 and an error message
- [ ] A description over 200 characters gets a 400 and an error message
- [ ] After a validation error, the form keeps the submitted values
- [ ] A `user_id` field added to the POST body is ignored; the expense is
      saved for the session user
- [ ] Profile page shows an "Add expense" link both in the empty state and
      when the user already has expenses
- [ ] The edit and delete stubs still return their placeholder text
- [ ] Existing tests still pass (`pytest`)
