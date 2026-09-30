# Spec: Login and Logout

## Overview
Turn the static sign-in page into a working authentication flow. A registered user submits email and password; the app looks up the user, verifies the password against the stored werkzeug hash, and stores the user id in the Flask session. `/logout` clears the session. This is Step 3 of the Spendly roadmap: it builds on the accounts created in Step 2 and provides the session that Step 4 (profile) and later expense routes rely on to know who is logged in.

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`, `seed_db()` demo user)
- Step 2 — Registration (users can be created with hashed passwords)

## Routes
- `GET /login` — render the sign-in form (already exists); if already logged in, redirect to `/profile` — public
- `POST /login` — validate credentials, set `session["user_id"]` and `session["user_name"]`, redirect to `/profile` on success; re-render the form with an error and HTTP 400 on failure — public
- `GET /logout` — clear the session and redirect to `/` — logged-in (harmless if called while logged out; simply redirects)

`/login` becomes a single view accepting `methods=["GET", "POST"]`. The existing placeholder `/logout` view (raw string return) is replaced with a real implementation.

`/profile` remains a stub owned by Step 4. Do not modify it; the post-login redirect targets it via `url_for('profile')` and will land on the placeholder text until Step 4 ships.

## Database changes
No database changes. The existing `users` table already has `email` (UNIQUE) and `password_hash`.

Add one helper to `database/db.py` (DB logic must not live in routes):
- `get_user_by_email(email)` — parameterised SELECT returning the `sqlite3.Row` (id, name, email, password_hash) or `None`. Always closes the connection.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html` — change form `action` to `{{ url_for('login') }}`; re-populate the `email` input with the submitted value after a failed submit (never the password)
  - `templates/base.html` — navbar is session-aware: when `session.user_id` is set, show the user's name and a "Sign out" link to `url_for('logout')`; otherwise keep "Sign in" and "Get started". Use `url_for()` for every link.

## Files to change
- `app.py` — implement `POST /login` and `/logout`; import `session`, `check_password_hash`, `get_user_by_email`; set `app.secret_key`
- `database/db.py` — add `get_user_by_email()`
- `templates/login.html` — `url_for` action, repopulate email
- `templates/base.html` — conditional nav links
- `static/css/style.css` — only if the nav needs a style for the user name / sign-out link; use existing CSS variables

## Files to create
- `tests/test_login_logout.py` — pytest tests for login and logout (pytest and pytest-flask are already in `requirements.txt`)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never build SQL with f-strings or `%`
- Passwords hashed with werkzeug; verify with `check_password_hash`; never store or log plaintext passwords
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- All routes stay in `app.py` (no blueprints); all DB logic stays in `database/db.py`
- Route functions do one thing: read the form, call the helper, render or redirect
- Every internal link and form action uses `url_for()` — never hardcode URLs
- Do not implement any other stub route (`/profile`, `/expenses/*`)
- `app.secret_key` must come from an environment variable (e.g. `SECRET_KEY`) with a clearly-dev-only fallback; do not commit a real secret
- Strip and lowercase the email before lookup
- Use a single generic error, "Invalid email or password", for both unknown email and wrong password (no user enumeration)
- Server-side validation: reject empty email or empty password with the same error and HTTP 400
- Store only `user_id` and `user_name` in the session — never the hash
- Call `session.clear()` on logout, and on successful login before setting the new values
- Always close the DB connection (try/finally)
- Failed login re-renders the form with HTTP 400 (not a bare string return); use `abort()` for any other HTTP error
- Reuse the existing `.auth-error` style; add no new colours
- Do not implement a `next` redirect parameter (avoids open-redirect risk at this stage)
- Per `CLAUDE.md` Subagent Policy: explore with a builtin explore subagent before implementing, and verify test results with a subagent afterwards
- After implementing, update the route table in `CLAUDE.md` (`/login` POST and `/logout` now implemented)

## Definition of done
- [ ] `GET /login` renders the form when logged out
- [ ] Logging in as `demo@spendly.com` / `demo123` redirects to `/profile` and the navbar shows a "Sign out" link instead of "Sign in" / "Get started"
- [ ] A user registered through `/register` can log in with their credentials
- [ ] Email is case-insensitive at login (`DEMO@Spendly.com` works)
- [ ] Wrong password shows "Invalid email or password" with HTTP 400 and no session is set
- [ ] Unknown email shows the exact same error message as a wrong password
- [ ] Blank email or password (bypassing the browser `required` attribute) shows the error and no session is set
- [ ] After a failed login, the email field keeps its value and the password field is empty
- [ ] Visiting `/login` while logged in redirects to `/profile`
- [ ] `GET /logout` clears the session, redirects to `/`, and the navbar shows "Sign in" / "Get started" again
- [ ] After logout, revisiting `/login` shows the login form (session is really gone)
- [ ] `/profile` is unchanged (still the Step 4 stub)
- [ ] `pytest tests/test_login_logout.py` passes
- [ ] App starts with `python app.py` without errors
