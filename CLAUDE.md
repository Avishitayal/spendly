# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

"Spendly" is a Flask-based personal expense tracker built as an **incremental teaching scaffold**. Much of the app is intentionally unimplemented: `app.py` contains placeholder routes that return plain strings like `"Add expense — coming in Step 7"`, and `database/db.py` is a stub describing the functions a student must write. Treat the "Step N" labels and the docstring in `database/db.py` as the spec for what those pieces should become.

## Commands

```bash
# One-time setup (venv/ is gitignored and may already exist)
python -m venv venv
venv\Scripts\activate          # Windows (PowerShell/cmd)
pip install -r requirements.txt

# Run the dev server — http://localhost:5001, debug + reloader on
python app.py

# Tests (pytest + pytest-flask are installed; no tests written yet)
pytest
pytest path/to/test_file.py::test_name    # single test
```

## Architecture

- **`app.py`** — the entire application: `Flask(__name__)` plus every route. Two categories:
  - *Live routes* (`/`, `/register`, `/login`, `/terms`, `/privacy`) render Jinja templates.
  - *Placeholder routes* (`/logout`, `/profile`, `/expenses/add`, `/expenses/<int:id>/edit`, `/expenses/<int:id>/delete`) return stub strings. Their URL patterns are the intended final routing scheme — preserve them when implementing.

- **`database/db.py`** — currently a stub. Intended to expose `get_db()` (SQLite connection with `row_factory` and foreign keys enabled), `init_db()` (`CREATE TABLE IF NOT EXISTS`), and `seed_db()`. The database file is `expense_tracker.db` at the repo root (gitignored). SQLite via the stdlib; no ORM.

- **`templates/`** — Jinja2. `base.html` is the shared layout (navbar + footer, "Spendly" branding). Every page does `{% extends "base.html" %}` and fills blocks: `title`, `head` (page-specific CSS), `content`, `scripts`. Example: `landing.html` pulls in `css/landing.css` via the `head` block and inlines JS in the `scripts` block.

- **`static/css/`** — `style.css` is global (loaded by `base.html`); per-page stylesheets like `landing.css` are opted into through each template's `head` block. `static/js/main.js` is loaded globally but is currently empty.

## Conventions

- Currency is the Indian rupee ("Track every rupee"); keep copy and formatting consistent with that.
- Fonts: DM Serif Display (headings) + DM Sans (body), loaded from Google Fonts in `base.html`.
- Brand mark is the `◈` glyph with the name "Spendly".
