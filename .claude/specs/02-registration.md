# Spec: Registration

## Overview
Turn the static registration page into a working sign-up flow. A visitor submits name, email and password; the app validates the input, hashes the password, stores a new row in `users`, and redirects to the login page. This is Step 2 of the Spendly roadmap: it builds on the database layer from Step 1 and gives Step 3 (login/logout) real accounts to authenticate against.

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`, `init_db()`)

## Routes
- `GET /register` — render the registration form (already exists, keep as is) — public
- `POST /register` — validate the form, create the user, redirect to `/login` on success, re-render the form with an error message on failure — public

`/register` becomes a single view accepting `methods=["GET", "POST"]`.

## Database changes
No database changes. The existing `users` table (`id`, `name`, `email` UNIQUE, `password_hash`, `created_at`) in `database/db.py` already covers everything needed. The UNIQUE constraint on `email` is the source of truth for duplicate detection.

Add one helper to `database/db.py`:
- `create_user(name, email, password)` — hashes the password with `generate_password_hash`, inserts the row with a parameterised query, returns the new user id. Raises `sqlite3.IntegrityError` on a duplicate email.

## Templates
- **Create:** none
- **Modify:** `templates/register.html`
  - Keep the existing `{% if error %}` block
  - Re-populate `name` and `email` inputs with the submitted values after a failed submit (never re-populate the password)
  - Change the form `action` to `{{ url_for('register') }}`

## Files to change
- `app.py` — implement `POST /register`; import `request`, `redirect`, `url_for`, `sqlite3`, and `create_user`
- `database/db.py` — add `create_user()`
- `templates/register.html` — repopulate fields, use `url_for`

## Files to create
- `tests/test_registration.py` — pytest tests for the registration route (pytest and pytest-flask are already in `requirements.txt`)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never build SQL with f-strings or `%`
- Passwords hashed with werkzeug (`generate_password_hash`); never store or log plaintext passwords
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Server-side validation is required even though the HTML has `required`:
  - `name` and `email` are non-empty after `.strip()`
  - `email` contains an `@` and is lowercased and stripped before storing and comparing
  - `password` is at least 8 characters (matches the form placeholder)
- Catch `sqlite3.IntegrityError` for duplicate email and show "An account with that email already exists" — do not run a separate SELECT-then-INSERT check
- Always close the DB connection (use try/finally)
- On any failure (validation or duplicate email) re-render the form with the error and HTTP 400
- On success redirect to `/login` (no auto-login; sessions arrive in Step 3)
- Reuse the existing `.auth-error` style; add no new colours

## Definition of done
- [ ] `GET /register` still renders the form
- [ ] Submitting valid name, email and an 8+ character password creates a row in `users` and redirects to `/login`
- [ ] The stored `password_hash` is not the plaintext password (check with `sqlite3 expense_tracker.db "select email, password_hash from users"`)
- [ ] Registering with `demo@spendly.com` (seeded user) shows "An account with that email already exists" and creates no new row
- [ ] Registering the same new email twice, in different letter case, is rejected the second time
- [ ] A password shorter than 8 characters shows an error and creates no row
- [ ] Blank or whitespace-only name or email shows an error and creates no row (test by bypassing the browser `required` attribute, e.g. with curl or the test client)
- [ ] After a failed submit, the name and email fields keep their values and the password field is empty
- [ ] A user created through the form can be verified with `check_password_hash` against the stored hash
- [ ] `pytest tests/test_registration.py` passes
- [ ] App starts with `python app.py` without errors
