---
name: frontend-design
description: Designs and builds UI for BrokeAF, Naveen's personal expense tracker (repo - https://github.com/NaveenG26/expence-tracker), using Flask + Jinja2 + vanilla CSS + vanilla JS. Produces pages and components (cards, forms, tables, stat tiles, empty states) that match BrokeAF's existing warm-paper, ink-and-forest-green look by reusing the CSS variables and classes in static/css/style.css. Use when the user asks to design, build, create, redesign, improve, or style any BrokeAF page, screen, section, or component - e.g. "design the X page", "create UI for X", "make the X look better" - or any request about BrokeAF's templates, layout, CSS, or visual polish.
disable-model-invocation: true
---

# BrokeAF UI Designer

You are designing frontend UI for **BrokeAF**, a personal expense tracker built with Flask and SQLite. Pages are server-rendered Jinja2 templates styled with vanilla CSS, with small amounts of vanilla JS. Every new page must look like it belongs next to the existing landing, login and register pages: one coherent product, not a collage.

`CLAUDE.md` is the source of truth for project rules. If anything here conflicts with it, `CLAUDE.md` wins.

## The stack (fixed - do not change)

- **Routes:** `app.py` only, no blueprints. A route checks the session, calls helpers from `database/db.py`, and renders a template.
- **Templates:** `templates/*.html`, one per page, each starting with `{% extends "base.html" %}`.
- **Styles:** `static/css/style.css` holds the global styles and design tokens. Page-specific styles go in a **new file** (e.g. `static/css/profile.css`) loaded through `{% block head %}`. Never use inline `<style>` tags or `style=""` attributes.
- **Scripts:** vanilla JS only, either in `static/js/main.js` or in a page file loaded through `{% block scripts %}`. Pages must work with JS turned off.
- **No frameworks or packages:** no React, Vue, Tailwind, Bootstrap, jQuery, npm, or new pip packages.

## Before you design: read what exists

Open these before writing anything:

1. `templates/base.html`: layout, navbar, footer, and the `title` / `head` / `content` / `scripts` blocks
2. `static/css/style.css`: tokens (`:root`) and the existing component classes
3. `templates/login.html` or `templates/register.html`: the reference for cards and forms
4. The spec for the current step in `.claude/specs/`: which variables the template receives

## Design tokens (from `style.css` - always use these)

Never hardcode hex or rgb colours in new CSS. Always use `var(--token)`. If you truly need a new colour, add it as a token in `:root` in `style.css` and flag it to the user.

| Purpose | Token |
|---|---|
| Primary text | `--ink` (near-black) |
| Secondary text | `--ink-soft` |
| Muted text, labels | `--ink-muted` |
| Placeholders, faint hints | `--ink-faint` |
| Page background | `--paper` (warm off-white) |
| Alternate section background | `--paper-warm` |
| Card surface | `--paper-card` (white) |
| Primary accent (hover, focus, highlights) | `--accent` (forest green) / `--accent-light` |
| Secondary accent (badges, second data series) | `--accent-2` (amber) / `--accent-2-light` |
| Errors, destructive actions | `--danger` / `--danger-light` |
| Borders and dividers | `--border` / `--border-soft` |
| Headings, big numbers | `--font-display` (DM Serif Display) |
| Body text, UI, tables | `--font-body` (DM Sans) |
| Corner radius | `--radius-sm` 6px (buttons, inputs, badges) · `--radius-md` 12px (cards) · `--radius-lg` 20px (large panels) |
| Content width | `--max-width` 1200px · `--auth-width` 440px |

Fonts are already loaded in `base.html`. Do not add new font imports.

`style.css` has three older hardcoded colours (`#f5c6c2` in `.auth-error` and `#5b7fa6` / `#8b5e83` in the landing mock bars). Don't copy them. If you need those colours, turn them into tokens first.

## Reuse existing classes before making new ones

| Need | Class |
|---|---|
| Main button (ink, turns green on hover) | `.btn-primary` |
| Secondary / outline button | `.btn-ghost` |
| Full-width form submit | `.btn-submit` |
| Form field wrapper and label | `.form-group` (with `<label>` inside) |
| Text input | `.form-input` |
| Error message box | `.auth-error` |
| Card surface | follow `.auth-card`: `--paper-card` background, `1px solid var(--border)`, `--radius-md`, `2rem` padding |

New classes get a page prefix so they don't leak into other pages: `.profile-header`, `.profile-stat`, `.expense-table`, and so on.

## BrokeAF's visual language

It's an editorial, calm fintech look: ink on warm paper, with forest green as the single accent.

- **Hierarchy:** page titles and large figures use `--font-display`. Everything else uses `--font-body`. Labels are small (`0.8–0.85rem`) and set in `--ink-muted`.
- **Spacing:** use `rem`, matching `style.css`: `0.5`, `0.75`, `1`, `1.25`, `1.5`, `2`, `4`, `5rem`. Cards take `2rem` padding (`1.25rem` on mobile). Grid gaps are `1–2rem`. Don't invent odd values.
- **Surfaces:** use borders rather than shadows. A shadow is allowed only on one standout hero element, never stronger than `0 8px 40px rgba(0,0,0,0.06)`.
- **Buttons and links:** the default is ink, with `--accent` on hover. Use `transition: … 0.2s`, as the existing styles do.
- **Money:** show rupees as `₹` with two decimals, e.g. `₹{{ '%.2f'|format(amount) }}`. Use `font-variant-numeric: tabular-nums` for amounts and right-align numeric table columns. Format values in the template. Never change stored values.
- **Categories:** the fixed list is Food, Transport, Bills, Health, Entertainment, Shopping, Other. Show them as small pills using `--accent-light` / `--accent-2-light` backgrounds. Don't give each category its own hardcoded colour.
- **Tables:** give rows a hover state (`--paper-warm`), `--border-soft` dividers, and right-aligned amounts. Wrap tables in a container with `overflow-x: auto`.
- **Empty states:** centre them, with one short line of text and a single next action (`.btn-primary`) linked with `url_for()`.
- **Icons:** the brand uses the text glyph `◈`. Prefer plain text or Unicode glyphs. Don't add an icon library unless the user asks for one. If they do, load it once in `base.html` with an **exact pinned version** (never `@latest`), and flag it as a new external dependency.

## Responsive rules

`style.css` uses breakpoints at **900px** (multi-column layouts collapse to one column) and **600px** (tighter padding, simplified nav). Use the same two breakpoints. At about 375px, stat cards stack, tables scroll sideways, and nothing overflows the page.

## Jinja and Flask rules

- Use `url_for()` for every internal link, form action and static file. Never hardcode a URL.
- Use only the variables the current spec says the route passes. Don't invent data in the template.
- Access fields with `row['field']` so plain dicts and `sqlite3.Row` both work.
- Never display or reference `password_hash`.
- Show form errors with `{% if error %}<div class="auth-error">{{ error }}</div>{% endif %}` and refill the fields the user typed (never the password).

## Output structure

1. **UI plan (2–5 bullets):** the sections and any UX decisions, with assumptions stated in one line each.
2. **Code:** each file in its own fenced block with a path comment:
   - `{# templates/<page>.html #}`: extends `base.html`, sets `{% block title %}` (e.g. `Profile — BrokeAF`), loads page CSS in `{% block head %}`
   - `/* static/css/<page>.css */`: page-prefixed classes, tokens only
   - JS only if it's truly needed
3. **Integration note (1–3 lines):** the route, the template variables it expects, and any `base.html` change.

## What to avoid

- Hardcoded colours, inline styles, or new fonts
- Anything that drifts from the existing paper/ink/green look, such as gradients, glows, heavy shadows, or extra accent colours
- Uneven spacing (16px in one place, 18px in another)
- Mystery icon-only buttons. In a finance app, a clear label beats a clever icon.
- Treating mobile as an afterthought
- Implementing a stub route that the current step doesn't target (see the route table in `CLAUDE.md`)

## Handling ambiguity

Make reasonable assumptions and state them in the UI plan. Ask only when the answer changes the output, for example "Should this be its own page or part of the profile page?"
