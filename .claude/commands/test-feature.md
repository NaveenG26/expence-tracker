---
description: Writes and runs tests for a specific BrokeAF feature. Pass the spec name as argument e.g. /test-feature 05-backend-connection
argument-hint: "Spec name (file in .claude/specs/ without .md) e.g. 05-backend-connection"
allowed-tools: Read, Glob, Bash(venv/bin/python -m pytest:*)
---

Run the full testing pipeline for the feature named in $ARGUMENTS. Follow the rules in CLAUDE.md.

If no argument is provided, stop immediately and say:
"Please provide a spec name. Usage: /test-feature <spec-name> e.g. /test-feature 05-backend-connection"

If `.claude/specs/$ARGUMENTS.md` does not exist, stop immediately, list the available specs in `.claude/specs/`, and say:
"Spec file not found at .claude/specs/$ARGUMENTS.md. Please check the spec name and try again."

---

## Step 0: Resolve the test file

Find the test file path in this order, and call it `<test_file>` from here on:
1. The `tests/test_*.py` path listed under the spec's **"Files to create"** section
   (e.g. `05-backend-connection` → `tests/test_backend_connection.py`, `03-login-logout` → `tests/test_login_logout.py`).
2. Otherwise, take the spec name, drop the leading step number, and replace hyphens with underscores:
   `07-add-expense` → `tests/test_add_expense.py`.

Never use the raw spec name (`tests/test_05-backend-connection.py`); it breaks the project's naming convention.

Also check the spec's step against the route table in `CLAUDE.md`. If the spec targets a route still marked **Stub**, stop and say:
"Step $ARGUMENTS is still a stub in CLAUDE.md — implement the feature before testing it."

---

## Step 1: Write Tests

Invoke the **spec-test-writer** subagent with the following context:

- Spec file to base tests on: `.claude/specs/$ARGUMENTS.md`, plus any specs it lists under "Depends on"
- Project rules: `CLAUDE.md` (route table, reusable DB helpers)
- Source files to read **for structure only** (route paths, helper names and signatures, never logic):
  - `app.py`: `grep -n "@app.route" app.py`
  - `database/db.py`: `grep -n "^def " database/db.py`
- Fixtures to reuse: `tests/conftest.py` (`app` and `client`, which use a temp DB via the monkeypatched `database.db.DB_PATH`). Do not redefine them.
- Test file to write: `<test_file>`. If it already exists, add to it; don't overwrite existing tests.
- Instruction: Write tests from what the spec says the feature SHOULD do. Do NOT derive test logic from the implementation. Cover:
  - happy paths
  - edge cases
  - auth guards (anonymous users redirected to `/login`)
  - per-user data isolation
  - validation errors
  - `abort()` status codes (e.g. 404 for a missing expense ID)
  - DB side effects, checked through existing helpers in `database/db.py`

Wait for spec-test-writer to finish and confirm `<test_file>` has been written before going on to Step 2.

---

## Step 2: Run Tests

Once spec-test-writer has finished, invoke the **spec-test-runner** subagent with the following context:

- Test file to run: `<test_file>`
- Spec file for context: `.claude/specs/$ARGUMENTS.md`
- Source files to check against when diagnosing failures:
  - `app.py`
  - `database/db.py`
  - `templates/` (only the templates the spec touches)
- Run command: `venv/bin/python -m pytest <test_file> -v`
  (Use `python -m pytest`, not plain `pytest`: plain `pytest` fails with `No module named 'app'`.)
- Instruction: Run ONLY `<test_file>`. For this pipeline, this overrides the runner's default of also running the full suite. Analyze each failure against the test code, the spec, and the source files. Classify each one as:
  - an **implementation bug**
  - a **missing feature** (the spec requires something not built yet)
  - a **test bug**
  - a **spec ambiguity**

  Flag any BrokeAF rule violations, such as f-string SQL, DB logic in routes, hardcoded URLs, or string error returns instead of `abort()`.

---

## Handoff Rules

- Do NOT start Step 2 until Step 1 is fully complete
- Do NOT fix any application code, templates, or tests, whatever the results show
- Do NOT run any tests beyond `<test_file>`
- Do NOT install packages or touch `requirements.txt`
- If spec-test-writer reports it could not write the test file, stop and report the reason. Do NOT go on to Step 2.

---

## Final Output

After both subagents complete, produce a combined summary:

### Testing Pipeline Report — $ARGUMENTS

**Spec**: `.claude/specs/$ARGUMENTS.md`
**Test file**: `<test_file>`

**Step 1 — Tests Written**
- List each new test with a one-line description of the spec requirement it checks
- Note any spec requirements spec-test-writer marked as too vague to test

**Step 2 — Test Results**
- Mirror spec-test-runner's structured report: the summary table, the failure details with classification and file:line root cause, and the architecture flags

**Verdict**
One of:
- ✅ Ready for code review: all tests pass
- ❌ Needs fixes: list the failing tests, their root causes, and who should fix each one (implementation or tests)
