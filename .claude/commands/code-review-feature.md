---
description: Runs parallel quality and security reviews of a BrokeAF feature. Pass the spec name as argument e.g. /code-review-feature 05-backend-connection
argument-hint: "Spec name (file in .claude/specs/ without .md) e.g. 07-add-expense"
allowed-tools: Read, Glob, Grep, Bash(git diff:*), Bash(git log:*), Bash(git status:*), Bash(git branch:*), Bash(git ls-files:*)
---

Run the code review pipeline for the feature named in $ARGUMENTS. Follow the rules in CLAUDE.md.

If no argument is provided, stop immediately and say:
"Please provide a spec name. Usage: /code-review-feature <spec-name> e.g. /code-review-feature 05-backend-connection"

If `.claude/specs/$ARGUMENTS.md` does not exist, stop immediately, list the available specs in `.claude/specs/`, and say:
"Spec file not found at .claude/specs/$ARGUMENTS.md. Please check the spec name and try again."

---

## Step 0: Pre-flight: work out the review scope

1. Run `git branch --show-current` and `git status`.
2. Collect **all** changes:
   - **Committed on the feature branch**: `git diff main...HEAD` (skip this when on `main`)
   - **Staged and unstaged**: `git diff HEAD`
   - **New untracked files**: `git ls-files --others --exclude-standard`. These don't appear in any `git diff`, so new templates, CSS files, and test files would be missed. Record their paths; the reviewers read them in full as new code.
3. Build `<changed_files>`: the union of `git diff main...HEAD --stat`, `git diff HEAD --stat`, and the untracked files.
4. **If everything is empty** (e.g. on `main` after the feature was merged), no diff is available. Review the files listed under the spec's **"Files to change"** and **"Files to create"** sections instead, and say so at the top of the final report. If the spec lists no files either, stop and say:
   "No changes detected. Implement the feature before running code review."
5. Check the `CLAUDE.md` route table. If the spec's step is still marked **Stub** and nothing in `<changed_files>` implements it, stop and say:
   "Step $ARGUMENTS is still a stub in CLAUDE.md — implement the feature before reviewing it."

---

## Step 1: Run both reviewers in parallel

Launch **brokeaf-quality-reviewer** and **brokeaf-security-reviewer** in the **same message**, so they run at the same time on the same scope. Don't start one before the other. Give both this context:

- Spec file: `.claude/specs/$ARGUMENTS.md`
- Current branch and the exact diff commands from Step 0 (or the fallback file list, if there's no diff)
- Changed files: `<changed_files>`
- New untracked files to read in full: the list from Step 0 (or "none")
- Project rules: `CLAUDE.md`
- Instruction: review only the changed and new code. Stay in your own lane (quality vs. security), skip stub routes, and use the output format from your agent definition. Do not edit any files.

Extra context for each reviewer:
- **brokeaf-quality-reviewer**: you may also read `app.py`, `database/`, `templates/`, and `static/` for context. Check for queries that duplicate existing helpers in `database/db.py`, and check whether `CLAUDE.md` was updated for any new helper or newly implemented route.
- **brokeaf-security-reviewer**: you may also read `app.py` and `database/` for context. Follow every changed route into the `database/db.py` helpers it calls. For routes that take an expense ID, check ownership (`AND user_id = ?`) in the SELECT, UPDATE, and DELETE queries.

Wait for **both** reviewers to finish before going on.

**If either reviewer fails or returns no output**, don't present a partial review as complete. Report which reviewer failed and why, show the other reviewer's output labelled "⚠️ Partial review — <reviewer> did not complete", give no overall verdict, and suggest re-running `/code-review-feature $ARGUMENTS`. Skip Step 3.

---

## Step 2: Unified report

Combine both reviews into one report. **De-duplicate overlapping findings**: if both reviewers flagged the same line for different reasons, merge them into one finding and note both perspectives (e.g. "🔒 + 🧹 `app.py:88` — SQL in the route: injection risk *and* belongs in `database/db.py`").

### Code Review Report — $ARGUMENTS

**Spec**: `.claude/specs/$ARGUMENTS.md`
**Branch**: `<branch>` · **Scope**: committed + uncommitted + untracked (or "spec file list — no diff available")
**Files reviewed**: `<changed_files>`

**🔒 Security Findings**
Mirror brokeaf-security-reviewer's report (💡 Things to learn from, 🌱 Nice to have, ✅ Doing well).

**🧹 Quality Findings**
Mirror brokeaf-quality-reviewer's report (💡 Worth improving, 🌱 Polish ideas, ✅ Doing well).

**📋 Combined Action Plan**
An ordered checklist of everything worth fixing, each item a single line with file:line:
1. **Must fix (security)**: security 💡 items involving SQL injection, missing auth or ownership checks, plaintext passwords or secrets, or data from one user exposed to another
2. **Should fix (quality)**: quality 💡 "Worth improving" items
3. **Should fix (security)**: the remaining security 💡 items (validation, GET for state changes, open redirects, leaky errors)
4. **Optional polish**: 🌱 items from both reviewers

Leave out empty groups.

**🧪 Suggested tests**
Test cases the reviewers suggested, ready to hand to spec-test-writer.

**Overall Verdict**
Pick exactly one:
- ✅ **APPROVED**: ready to commit. There are no 💡 findings from either reviewer; only polish, if anything.
- 💡 **APPROVED WITH SUGGESTIONS**: can commit. There are "Should fix" or "Optional polish" items, but nothing in "Must fix". Address them now or in a later step.
- ❌ **CHANGES REQUESTED**: fix before committing. At least one "Must fix" security item exists (see the action plan above).

---

## Step 3: Ask for approval

After presenting the report (and only when both reviewers completed and there's at least one action plan item), ask:

"Do you want me to implement the action plan now? You can say 'all', a range like 'items 1–3', or 'just the must-fix items'."

Then **stop and wait** for an explicit answer. Don't touch any file until the user approves.

If the user approves:
- Implement only the items they chose, following `CLAUDE.md`: queries in `database/db.py` with `?` placeholders, `abort()` for errors, `url_for()` in templates, no new packages.
- Afterwards, list what changed for each item, and suggest running `/test-feature $ARGUMENTS` and then `/code-review-feature $ARGUMENTS` again to confirm.

If the verdict is ✅ APPROVED with no action items, skip the question and just say the feature is ready to commit.

---

## Rules

- Do NOT edit, fix, or commit any files before the user approves in Step 3
- Do NOT start one reviewer before the other: both must launch in the same message
- Do NOT skip the Step 0 pre-flight scope check
- Do NOT proceed if `.claude/specs/$ARGUMENTS.md` does not exist: report it and stop
- Do NOT present a partial review as complete if either reviewer fails or returns nothing
- Do NOT run the app or the tests here. Use `/test-feature $ARGUMENTS` for tests.
- Reviews are educational: frame findings as learning points, but the verdict and the "Must fix" group still state clearly what should be fixed before committing
