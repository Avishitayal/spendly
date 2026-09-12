# Spec: Edit Expense

## Overview
Spendly currently lets a user add expenses (Step 5) and filter their profile
summary by date range (Step 6), but the profile page only shows an aggregated
category breakdown — there is no way to see, or correct, a single logged
expense. This feature replaces the `/expenses/<int:id>/edit` placeholder with
a real route so a user can open one of their own expenses and change its
amount, category, date, or description. To make the new route reachable from
the UI, the profile page also gains a simple list of individual expenses
(most recent first) with an "Edit" link per row. Deleting an expense stays
out of scope — that is Step 9 (`/expenses/<int:id>/delete`).

## Depends on
- Step 1 (Database setup) — `expenses` table must exist.
- Step 3 (Login and logout) — `login_required` / `g.user` session handling.
- Step 5 (Add expense) — `EXPENSE_CATEGORIES`, `_validate_expense`, and the
  `add_expense.html` form pattern this feature reuses.
- Step 6 (Date filter profile page) — the current `profile()` route this
  feature extends with a per-expense list.

## Routes
- `GET /expenses/<int:id>/edit` — render the edit form pre-filled with the
  expense's current values — logged-in
- `POST /expenses/<int:id>/edit` — validate and update the expense, then
  redirect to the profile page — logged-in

Both methods must confirm the expense's `user_id` matches `g.user["id"]`
before showing or updating it; if the expense does not exist or belongs to
someone else, respond with a 404 (`flask.abort(404)`) rather than leaking
whether the id exists.

## Database changes
No database changes. `expenses` (id, user_id, amount, category, date,
description, created_at) already has every column this feature needs
(verified against `database/db.py`). The route needs one new read query (fetch
one expense by id + user_id) and one new `UPDATE` query; no new tables,
columns, or constraints.

## Templates
- **Create:** `templates/edit_expense.html` — same structure as
  `templates/add_expense.html` (auth-section/auth-card form with amount,
  category, date, description fields), pre-filled with the expense's current
  values and posting to `url_for('edit_expense', id=expense.id)`.
- **Modify:** `templates/profile.html` — add an "Expenses" list section below
  the category breakdown, listing each expense (date, category, description,
  amount, an "Edit" link to `url_for('edit_expense', id=row.id)`), most
  recent first. Reuse existing empty-state copy/pattern for when there are no
  expenses in the active filter.

## Files to change
- `app.py` — replace the `edit_expense` placeholder with the real
  GET/POST route; extend the `profile()` route to also fetch the
  user's individual expenses (respecting the existing date-range filter) and
  pass them to the template.
- `templates/profile.html` — add the expense list + edit links.
- `static/css/profile.css` — add styles for the new expense list rows (use
  existing CSS variables, no hardcoded hex values).

## Files to create
- `templates/edit_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (n/a to this feature, but do not touch
  existing auth code)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Reuse `_validate_expense` from `app.py` for the update path instead of
  duplicating validation logic
- Always scope expense lookups/updates to `user_id = ?` — never trust the
  `<int:id>` in the URL alone
- On successful update, `flash` a confirmation message and redirect to
  `profile` (mirrors the add-expense flow)
- On validation error, re-render `edit_expense.html` with the submitted
  values and an inline error, the same way `add_expense` does

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` for an expense you own (while logged in)
      shows a form pre-filled with its current amount, category, date, and
      description
- [ ] Visiting `/expenses/<id>/edit` for an id that does not exist, or that
      belongs to another user, returns a 404
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`
- [ ] Submitting the edit form with a valid change updates the row in
      `expenses` and redirects to `/profile`, where the new values are
      reflected in the expense list and category breakdown
- [ ] Submitting the edit form with an invalid amount, category, or date
      re-renders the form with an inline error and preserves the submitted
      values
- [ ] The profile page lists individual expenses (not just category totals),
      each with a working "Edit" link, and respects the current date-range
      filter
- [ ] `pytest` still passes with no regressions to existing add-expense,
      login, or profile-filter behavior
