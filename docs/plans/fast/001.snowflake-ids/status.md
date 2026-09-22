# Fast feature 001 — snowflake-ids

| Status  | Verifier | Date |
|---------|----------|------|
| done    | PASS     | 2026-07-22 |

## Files Changed

- `backend/app/ids.py` — implemented `generate_id()`: monotonic per-ms snowflake with lock-guarded sequence, spin-wait on overflow, backwards-clock clamp; reads `node_id` at call time.
- `backend/app/db/users.py` — updated `create` docstring for app-generated snowflake id (no reliance on refresh for the id); body unchanged (refresh retained to un-expire attributes after commit).
- `backend/app/services/db_import_export.py` — `_user_to_dict` emits `id` as `str`; `_dict_to_user` parses `id` to `int` accepting string or legacy number.
- `backend/app/settings.py` — verified `node_id` field complete (no change).
- `backend/app/models/user.py` — verified `id` snowflake field + docstring complete (no change).

## Skeleton

### Frozen interface (2026-07-22)

- `backend/app/ids.py` — `EPOCH_MS = 1704067200000` — new (pinned module constant, real value).
- `backend/app/ids.py` — bit-layout constants (all new, real values):
  `TIMESTAMP_BITS = 41`, `NODE_ID_BITS = 10`, `SEQUENCE_BITS = 12`,
  `SEQUENCE_SHIFT = 0`, `NODE_ID_SHIFT = 12`, `TIMESTAMP_SHIFT = 22`,
  `MAX_NODE_ID = 1023`, `MAX_SEQUENCE = 4095`.
- `backend/app/ids.py` — `def generate_id() -> int` — new; body raises `NotImplementedError` (behavior is the coder's).
- `backend/app/settings.py` — `node_id: int = Field(default=0, ge=0, le=1023, validation_alias="BOOKWRITER_NODE_ID")` on `Settings` — new; fully implemented (declarative field with real default + 0–1023 range validation via `ge`/`le`). `get_settings()` untouched.
- `backend/app/models/user.py` — `id: int = Field(default_factory=generate_id, primary_key=True)` — changed (was `id: int | None = Field(default=None, primary_key=True)`). Imports `generate_id` from `app.ids`. Module import does NOT call `generate_id` (class definition only; factory runs at instantiation). Stale autoincrement docstring updated to snowflake.
- `backend/app/db/users.py` — `async def create(user: User) -> User` — unchanged/confirmed. `async def get_by_id(user_id: int) -> User | None` — unchanged/confirmed. Behavioral change (not relying on `session.refresh()` for the id) is the coder's; existing body left intact.
- `backend/app/services/db_import_export.py` — `_user_to_dict(user: User) -> dict[str, object]` and `_dict_to_user(data: dict[str, object]) -> User` — signatures unchanged/confirmed (frozen in feature 003). Existing working codec bodies left as-is; the id string-out / string-or-int-in serialization change is the coder's behavioral edit (do not treat these as stubbed).
- Caller-compile edits (out of Source-files scope): None.

## Tests

### Tests (2026-07-22)

- `backend/tests/test_ids.py` (NEW) — covers DoD-1, DoD-2, DoD-3 — snowflake
  positivity/64-bit/uniqueness, node-id field decode via frozen constants, and
  monotonic + same-ms distinct ordering.
- `backend/tests/db/test_users.py` (AMEND) — covers DoD-4 — `users.create`
  yields a populated snowflake id above the frozen `TIMESTAMP_SHIFT` range that
  round-trips via `get_by_username` (no autoincrement assertion).
- `backend/tests/services/test_db_import_export.py` (AMEND) — covers DoD-5,
  DoD-6 — user codec emits `id` as a JSON string and round-trips it, and accepts
  a legacy JSON-number `id` (back-compat).
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓,
  DoD-7 [manual/live, no test], DoD-8 [manual/live, no test]

## Notes & Issues

_populated by the coder when worth saying_
