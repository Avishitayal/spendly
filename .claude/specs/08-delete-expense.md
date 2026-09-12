# Spec: Delete Expense

## Overview
Spendly currently lets a user add (Step 5), filter (Step 6), and edit (Step 7)
their expenses, but there is no way to remove a mistaken or duplicate entry —
the `/expenses/<int:id>/delete` route is still the placeholder stub
`"Delete expense — coming in Step 9"`. This feature replaces that placeholder
with a real route so a user can permanently remove one of their own expenses
from the profile page, with a confirmation step so a stray click can't wipe
out a row by accident.

## Depends on
- Step 1 (Database setup) — `expenses` table must exist.
- Step 3 (Login and logout) — `login_required` / `g.user` session handling.
- Step 7 (Edit expense) — the per-expense list on `profile.html` (date,
  category, description, amount, Edit link) that this feature adds a Delete
  action to, and the `profile()` route's expense query this feature reuses
  unchanged.

## Routes
- `POST /expenses/<int:id>/delete` — delete the expense, then redirect to the
  profile page — logged-in

No GET handler: deleting is a destructive action, so it must not be
reachable via a plain link, browser prefetch, or crawler — only via a form
submission. This changes the placeholder's implicit GET-only signature, but
the `/expenses/<int:id>/delete` URL path itself is unchanged.

The route must confirm the expense's `user_id` matches `g.user["id"]` before
deleting it; if the expense does not exist or belongs to someone else,
respond with a 404 (`flask.abort(404)`) rather than leaking whether the id
exists (same pattern as `edit_expense`).

## Database changes
No database changes. Deleting is a plain
`DELETE FROM expenses WHERE id = ? AND user_id = ?`; no new tables, columns,
or constraints (verified against `database/db.py`).

## Templates
- **Modify:** `templates/profile.html` — in each `profile-expense-row`, add a
  small delete form next to the existing "Edit" link:
  `<form method="POST" action="{{ url_for('delete_expense', id=row.id) }}" class="profile-expense-delete-form">`
  containing a single `<button type="submit" class="profile-expense-delete">`
  (trash icon + "Delete" text, same `lucide` icon convention as the Edit
  link). Add an `onsubmit="return confirm('Delete this expense?')"` on the
  form so the action requires an explicit confirmation.

## Files to change
- `app.py` — replace the `delete_expense` placeholder with the real `POST`
  route.
- `templates/profile.html` — add the delete form/button per expense row.
- `static/css/profile.css` — style `.profile-expense-delete-form` /
  `.profile-expense-delete` to sit next to `.profile-expense-edit` (reuse
  existing CSS variables, no hardcoded hex values); extend the existing
  `.profile-expense-row` grid and its `@media (max-width: 600px)` block to
  fit the extra action instead of overlapping it.

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (n/a to this feature, but do not touch
  existing auth code)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Always scope the delete to `user_id = ?` — never trust the `<int:id>` in
  the URL alone
- The route accepts `POST` only; do not add a `GET` handler or a plain `<a>`
  link to the delete URL
- Require a client-side confirmation (`confirm(...)`) before the delete form
  submits, so one accidental click can't remove a row
- On successful delete, `flash` a confirmation message and redirect to
  `profile` (mirrors the add/edit-expense flow)
- Deleting a nonexistent or another user's expense returns 404 and deletes
  nothing

## Definition of done
- [ ] On the profile page, each expense row has a working "Delete" action
      next to "Edit"
- [ ] Clicking Delete prompts for confirmation before anything is submitted
- [ ] Confirming deletes the row from `expenses` and redirects to `/profile`,
      where the row no longer appears and the category breakdown/totals
      update accordingly
- [ ] Submitting `POST /expenses/<id>/delete` for an id that does not exist,
      or that belongs to another user, returns a 404 and leaves the database
      unchanged
- [ ] Submitting `GET /expenses/<id>/delete` (e.g. visiting the URL directly)
      does not delete anything (405 or no matching route)
- [ ] Visiting/submitting the delete route while logged out redirects to
      `/login`
- [ ] `pytest` still passes with no regressions to existing add-expense,
      edit-expense, login, or profile-filter behavior
