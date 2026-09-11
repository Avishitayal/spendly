# Spec: Date Filter for Profile Page

## Overview
The `/profile` page (Step 4) currently shows all-time stats only: total spent,
expense count, top category and the category breakdown are always computed
over every expense the signed-in user has ever logged. This step adds an
optional date range filter to that same page so a user can narrow those same
stats to "This Month", "Last Month", or a custom start/end range, without
introducing a new route, table, or page. It builds directly on the stat panel
and `rupees` filter from Step 4 and is a stepping stone toward the full
expense list (Steps 7–9), where date filtering will be reused.

## Depends on
- **Step 1 — Database setup** (complete): the `expenses` table's `date` column
  (`TEXT`, `'YYYY-MM-DD'`).
- **Step 3 — Login and Logout** (complete): `g.user`, `login_required`.
- **Step 4 — Profile Page Design** (complete): the `GET /profile` route, the
  stat panel it renders, `templates/profile.html`, `static/css/profile.css`,
  and the `rupees` template filter. This step modifies all of these in place.

## Routes
No new routes. `GET /profile` (endpoint `profile`) is widened to read two
optional query-string parameters:
- `start` — `YYYY-MM-DD`, inclusive lower bound.
- `end` — `YYYY-MM-DD`, inclusive upper bound.

Both are optional and independent. Access level is unchanged — **logged-in**
only, still redirecting to `/login` when signed out.

## Database changes
No database changes. `expenses.date` already exists and is already stored as
`'YYYY-MM-DD'` text, which sorts and compares correctly with SQLite's string
comparison operators — no new column, table, or index needed.

## Templates
- **Modify:**
  - `templates/profile.html` — add a filter control above the stat panel:
    three quick-filter links ("This Month", "Last Month", "All Time") plus a
    small custom-range form (`GET`, two `<input type="date">` fields named
    `start` and `end`, an "Apply" button). The active quick filter is
    highlighted; the custom inputs stay populated with whatever `start`/`end`
    were actually applied. When the filtered range has zero expenses, show
    "No expenses in this range" in place of the top-category line, distinct
    from the existing zero-expenses-ever empty state.

## Files to change
- `app.py`
  - Widen `profile()`:
    - Read `request.args.get("start")` / `request.args.get("end")`.
    - Validate each with `datetime.strptime(value, "%Y-%m-%d")`; treat a
      missing, malformed, or reversed (`start > end`) pair as "no filter" and
      fall back to all-time, rather than erroring.
    - Build the summary and breakdown queries so a valid range adds
      `AND date >= ?` / `AND date <= ?` to the existing
      `WHERE user_id = ?` clause, with values bound as parameters (never
      string-formatted into the SQL).
    - Pass `selected_start`, `selected_end`, and an `is_filtered` flag to
      `render_template` so the template can highlight the active quick filter,
      repopulate the custom inputs, and choose the right empty-state copy.
  - Add a small helper (e.g. `_month_range(offset=0)`) that returns the
    `(start, end)` strings for the current or previous calendar month, used to
    build the "This Month" / "Last Month" links' query strings.
- `templates/profile.html` — see Templates above.

## Files to create
- `.claude/specs/06-date-filter-profile-page.md` — this spec.
- `tests/test_date_filter.py` — pytest coverage (see Definition of done).
  Follows the same DB-isolation fixture pattern as the other test files
  (monkeypatch `database.db.DB_PATH` to a `tmp_path` file, `init_db()`, seed
  known expenses with specific dates, log in via the test client).

## New dependencies
No new dependencies. `datetime` is already imported in `app.py`.

## Rules for implementation
- No SQLAlchemy or ORMs — stdlib `sqlite3` through `database.db.get_db()` only.
- Parameterised queries only — `start`/`end` are always bound as `?`
  parameters, never concatenated or f-strung into SQL, even after validation.
- Passwords hashed with `werkzeug` — unaffected by this step.
- Use CSS variables — never hardcode hex values in `profile.css`; reuse the
  existing palette, radii, and font variables.
- All templates extend `base.html`.
- Every expense query stays scoped to `user_id = ?` bound to `g.user["id"]` —
  the date filter narrows a user's own expenses, never another user's.
- Keep the `profile` endpoint name and URL (`/profile`) unchanged so
  `url_for("profile")` and the navbar link from Step 4 keep working; the
  filter is query-string only.
- Invalid input never 500s: a bad or reversed date range is silently treated
  as "no filter", never surfaced as a server error.

## Definition of done
- [ ] `GET /profile` with no query params behaves exactly as before Step 6
      (all-time count, total, top category, breakdown).
- [ ] `GET /profile?start=YYYY-MM-DD&end=YYYY-MM-DD` returns 200 and the stat
      panel and breakdown reflect only that signed-in user's expenses with
      `date` between `start` and `end` inclusive.
- [ ] The "This Month" and "Last Month" quick-filter links produce the correct
      `start`/`end` for the current date and are highlighted as active when
      selected.
- [ ] A malformed date (e.g. `start=not-a-date`) or a reversed range
      (`start` after `end`) falls back to all-time results with no error page.
- [ ] A valid range with zero matching expenses shows ₹0.00, count 0, and
      "No expenses in this range" (not the zero-expenses-ever message).
- [ ] After applying a custom range, the two date inputs still show the
      applied `start`/`end` values.
- [ ] `grep -i '#[0-9a-f]\{3,\}' static/css/profile.css` is empty (no
      hardcoded hex colours).
- [ ] `pytest tests/test_date_filter.py` passes.
- [ ] `python app.py` starts with no errors and filtering works end to end at
      http://localhost:5001/profile.
