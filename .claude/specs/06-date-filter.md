# Spec: Date Filter for Profile Page

## Overview
Step 6 adds a date-range filter to the existing `/profile` route so users can
narrow the summary stats, category breakdown and recent expenses list to a
specific period. The filter is driven entirely by query-string parameters
(`date_from` and `date_to`) on `GET /profile`, so it needs no new routes and
filtered views are bookmarkable. A compact filter bar offers four presets
("This Month", "Last 3 Months", "Last 6 Months", "All Time") and two
`<input type="date">` fields for a custom range. This delivers the "Filter by
time period" feature advertised on the landing page and comes before the
add/edit/delete steps (7–9).

## Depends on
- Step 1: Database setup (`expenses` table with a `date` column stored as
  `YYYY-MM-DD` text)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 4: Profile page UI (template with header, stats, breakdown and recent
  expenses sections)
- Step 5: Backend connection (`get_expense_summary`, `get_category_breakdown`
  and `get_recent_expenses` in `database/db.py`, wired to `/profile`)

## Routes
No new routes. The existing `GET /profile` route (logged-in only) is modified
to read two optional query parameters:
- `date_from`: ISO date string `YYYY-MM-DD`, inclusive lower bound
- `date_to`: ISO date string `YYYY-MM-DD`, inclusive upper bound

The filter applies only when **both** parameters are present and valid.
If either is absent, empty or malformed, the route falls back to the
unfiltered "All Time" view rather than erroring out.

## Database changes
No database changes. `expenses.date` is `TEXT NOT NULL` in ISO `YYYY-MM-DD`
format, which works with `BETWEEN` comparison in SQLite.

## Templates
- **Create:** none
- **Modify:** `templates/profile.html`
  - Add a filter bar section between the profile header and the stats row,
    containing:
    - Four preset links: "This Month", "Last 3 Months", "Last 6 Months",
      "All Time". Each uses `url_for('profile', date_from=..., date_to=...)`
      with dates computed in `app.py`. "All Time" uses bare
      `url_for('profile')`.
    - A custom-range GET form, `action="{{ url_for('profile') }}"`, with two
      `<input type="date">` fields named `date_from` / `date_to`, pre-filled
      with the active values, and an "Apply" submit button.
    - Active state: the matching preset gets an `is-active` class. When the
      active range matches no preset (a custom range), no preset is
      highlighted and the date inputs show the range. "All Time" is
      highlighted when no filter is active.
    - If the route passes a `filter_error`, render it in the filter bar.
  - Empty state when a filter is active and matches no expenses: the stats
    row shows ₹0.00 / 0 / —, and the card reads "No expenses in this period"
    with a link to All Time instead of "No expenses yet / Add your first
    expense".
  - No other structural changes. Existing sections just receive filtered data.

## Files to change
- `app.py`
  - Add a small helper (e.g. `parse_date_range(args)`) that reads `date_from`
    / `date_to` from `request.args`, validates them, and returns
    `(date_from, date_to, filter_error)`. This keeps `profile()`
    single-responsibility.
  - Add a helper that computes the preset ranges relative to `date.today()`.
  - `profile()` passes the validated dates to each DB helper, and passes
    `date_from`, `date_to`, `presets` and `filter_error` to the template.
- `database/db.py`: add optional `date_from=None, date_to=None` keyword
  params to the existing helpers. When both are given, add
  `AND date BETWEEN ? AND ?`:
  - `get_expense_summary(user_id, date_from=None, date_to=None)` applies to
    both the totals and top-category queries
  - `get_category_totals(user_id, date_from=None, date_to=None)`
  - `get_category_breakdown(user_id, date_from=None, date_to=None)` passes
    the dates through to `get_category_totals`. The pct logic is unchanged.
  - `get_recent_expenses(user_id, limit=10, date_from=None, date_to=None)`.
    Ordering and limit are unchanged.
- `templates/profile.html`: filter bar and filtered empty state (see Templates)
- `static/css/profile.css`: filter bar, preset links, active state and error
  text, using CSS variables only
- `CLAUDE.md`: note in the routes table that `GET /profile` accepts
  `date_from` / `date_to` query params

## Files to create
- `tests/test_date_filter.py` (written by the spec-test-writer subagent)

## New dependencies
No new dependencies. Use the standard library `datetime` for parsing and
preset maths. Do not add `python-dateutil`.

## Rules for implementation
- No SQLAlchemy or ORMs. Raw `sqlite3` only, via `get_db()`
- Parameterised queries only. Never string-format dates into SQL; bind
  both bounds with `?`. The optional `AND date BETWEEN ? AND ?` clause is a
  fixed string fragment, never built from user input
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables. Never hardcode hex values
- All templates extend `base.html`
- No inline `<style>` tags or `style=` attributes
- No JavaScript required. Presets are links and the custom range is a plain
  GET form
- Every link and form action uses `url_for()`. Never hardcode URL strings
- Extend the existing helpers in `database/db.py`. Do not create
  `database/queries.py` or parallel `*_filtered` functions
- Date validation in `app.py`: `datetime.strptime(value, "%Y-%m-%d")`. On
  `ValueError`, treat the param as absent (no filter, no error message)
- If `date_from > date_to` after validation, treat both as absent and pass
  `filter_error="Start date must be before end date."` to the template.
  (The codebase passes `error=` to templates rather than using `flash()`,
  and `base.html` has no flash rendering.)
- Malformed or reversed dates must never return a 4xx/5xx. The page always
  renders 200 for a logged-in user
- When the filter is absent, every helper behaves exactly as in Step 5
- Preset ranges are computed in `app.py`, never in the template, and all
  end on `today`:
  - This Month: 1st of the current month → today
  - Last 3 Months: same day 3 calendar months ago → today
  - Last 6 Months: same day 6 calendar months ago → today
  - If the earlier month is shorter, clamp the day to its last day (e.g.
    31 May minus 3 months → 28/29 Feb)
  - All Time: no params
- Category `pct` values must still sum to 100 within any filtered range
  that has expenses
- Currency always displays as ₹
- Unauthenticated requests to `/profile?date_from=…` still redirect to `/login`

## Definition of done
- [ ] Visiting `/profile` with no query params shows the same data as Step 5 (seed user: 8 expenses, ₹283.45, top category "Bills")
- [ ] A filter bar with This Month, Last 3 Months, Last 6 Months and All Time links plus a custom date-range form appears above the stats
- [ ] Clicking "This Month" changes the URL to `/profile?date_from=<1st of month>&date_to=<today>` and all three sections show only expenses in that window
- [ ] Clicking "Last 3 Months" filters to the 3-month window ending today
- [ ] Clicking "Last 6 Months" filters to the 6-month window ending today
- [ ] Clicking "All Time" goes to a clean `/profile` URL and shows all expenses
- [ ] Submitting a custom range covering a single day shows only that day's expenses in stats, breakdown and recent list
- [ ] Category breakdown percentages add up to 100% for any filtered range that has expenses
- [ ] Submitting `date_from` later than `date_to` shows "Start date must be before end date." and falls back to the unfiltered view (200)
- [ ] `/profile?date_from=not-a-date&date_to=2026-11-27` does not error. It renders the unfiltered view (200)
- [ ] `/profile?date_from=&date_to=` and `/profile?date_from=2026-11-01` (one bound only) render the unfiltered view
- [ ] The active preset is visually highlighted, or for a custom range the date inputs show the active values
- [ ] A range with no matching expenses shows ₹0.00 total spent, 0 expenses, "—" top category and "No expenses in this period" with a link back to All Time, with no errors
- [ ] All amounts display the ₹ symbol regardless of the active filter
- [ ] Visiting a filtered `/profile` URL while logged out redirects to `/login`
- [ ] Existing test suite (`pytest`) still passes
