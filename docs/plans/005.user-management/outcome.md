# Outcome — feature 005 user-management

Intended documentation changes to apply at finalization (architect + product-spec
routing). FEAT-003 is fully `[confirmed: user]` with no `_TBD`, so **no
product-spec back-propagation is needed** — these are architecture + quick-ref
deltas only. Keep to real deltas.

## `docs/architecture/backend.md`

- **Authentication section** — record that `require_role` is now realized (closing
  the 004→005 deferral): a dependency factory over `get_current_user` with the
  role ladder `{author: 0, admin: 1}`, insufficient → 403. Note it follows the
  same sanctioned pattern as `get_current_user` (an auth dependency in
  `services/auth.py` raising the HTTP error directly is not a routes-layer
  violation).
- **A user-management surface** — the admin user-management endpoints under
  `/api/admin/users` (list / create / reset-password / change-role / disable), all
  gated by `require_role(admin)`, and the admin service boundary: password
  validation, self-guards, credential minting/nulling, and the hand-built
  secret-excluding response mapping all live in `services/admin.py`; routes stay
  HTTP-only and map the service's typed error to the status taxonomy (409 taken /
  404 not-found / 400 self-target / 400 already-disabled / 400 password-invalid).
- **Derived-not-stored `active`** — call out that `AdminUserResponse.active` is
  **derived** (`pwdhash is not None`) at response time, **not** a `User` column,
  so no one adds a table column or import/export codec entry for it. Disable nulls
  `pwdhash` + `jwt_signing_key` (no `salt`); the preserved row is what keeps data
  + attribution intact, and re-enable is *only* via password reset.
- **Password policy** — note the shared min-length-8 + confirm-match policy is now
  used by both first-run setup (003) and admin create/reset (005). If step 001
  extracted a shared validator, record its home; **deferred convergence:** if
  003's `services/setup.py` still inlines its own copy, flag converging it onto the
  shared validator as a small follow-up (this feature deliberately did not touch
  `setup.py`).

## `docs/architecture/frontend.md`

- **Admin SPA — first real pages** — record that the Admin SPA now hosts real
  pages (users list + create/reset/role modals) under a **minimal** local layout;
  the shared cross-SPA `AppLayout/AppHeader/AppSidebar` shells remain deliberately
  deferred until 006/007.
- **A worked MobX reference example** — the users page (list async trio + external
  `loadUsers`/`disableUserAction` + local `refresh`) and the modal form pattern
  (`*Draft` class + `get`-computed validation + separate `serverErrors` + external
  `submit*` effects; modal open/target as component-local `useState`; no Mantine
  `useForm`) are a good canonical example to cite for future admin pages.

## `docs/architecture/quick-reference.md` (create if still absent)

- Add the `/api/admin/users` surface: `GET ""`, `POST ""`,
  `PUT /{user_id}/password`, `PUT /{user_id}/role`, `PUT /{user_id}/disable`
  (all `require_role(admin)`; statuses 200 / 201 / 204 / 204 / 204 with the
  refusal taxonomy above).
- Add the DTOs: `AdminUserResponse{id:int, username, role, last_login, active}`,
  `AdminCreateUserRequest{username, password, password_confirm, role}`,
  `AdminSetPasswordRequest{password, password_confirm}`, `AdminSetRoleRequest{role}`.

## Observations

_populated by the coder / fixer as steps complete_
