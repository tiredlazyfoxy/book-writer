# Fast feature 007 — codex-create-from-chat

| Status  | Verifier | Date       |
|---------|----------|------------|
| done    | PASS     | 2026-08-10 |

## Files Changed

- `backend/app/services/codex_tools.py` — `create_codex_entry`'s body: cap → duplicate-name
  check → acting-user resolution → `codex_service.create_entry` → counter → confirmation, all
  behind a never-raise guard
- `backend/app/db/mode_tools.py` — `DEFAULT_MODE_TOOL_NAMES` gains `create_codex_entry` for
  `edit-character` / `edit-location` / `edit-fact` / `write-chapter`, not `close-chapter`
- `backend/app/db/assistant_modes.py` — `DEFAULT_MODE_SYSTEM_PROMPTS` gains the
  explicit-command wording for the same four modes

## Skeleton

### Frozen interface (2026-08-10)

- `backend/app/services/codex_tools.py` — `class CreateCodexEntryArgs(BaseModel)` with
  `kind: CodexKind`, `name: str | None = None`, `body: str` — new (mirrors
  `CreateCodexEntryRequest` field for field; `CodexKind` is the shared enum, not a second
  vocabulary)
- `backend/app/services/codex_tools.py` —
  `async def create_codex_entry(context: "ToolContext", kind: CodexKind, body: str, name: str | None = None) -> str`
  — new. Body raises `NotImplementedError` (the skeleton marker only — the tool's own
  contract is that it **never raises**). `body` precedes `name` because Python forbids a
  non-defaulted parameter after a defaulted one; the `llm` client dispatches
  `func(**kwargs)`, so the free-parameter **names** are the contract and they are exactly
  `CreateCodexEntryArgs`' three fields (verified: `inspect.signature(binder(ctx))` →
  `['kind', 'body', 'name']`).
- `backend/app/services/codex_tools.py` —
  `def bind_create_codex_entry(context: "ToolContext") -> Callable[..., object]` — new;
  implemented as `functools.partial(create_codex_entry, context)`, the existing binder
  shape (a binder is interface wiring, so it is not left unimplemented).
- `backend/app/services/codex_tools.py` — module constants — new:
  `MAX_CODEX_CREATES_PER_TURN = 3` (public, the per-turn cap) and the refusal/confirmation
  strings `_CREATE_CAP_MESSAGE` (`{cap}`), `_CREATE_DUPLICATE_NAME_MESSAGE`
  (`{kind}` / `{name}` / `{entry_id}`), `_CREATE_NO_IDENTITY_MESSAGE`,
  `_CREATE_NOT_PERMITTED_MESSAGE`, `_CREATE_REFUSED_MESSAGE` (`{reason}` — carries
  `CodexError.message` through verbatim), `_CREATE_FAILED_MESSAGE`, `_CREATED_MESSAGE`
  (`{entry_id}` / `{kind}` / `{name_segment}`) and `_CREATED_NAME_SEGMENT` (`{name}`,
  omitted whole for a fact). Wording is the skeleton's; the coder may reword a message but
  not add, drop or rename one.
- `backend/app/services/codex_tools.py` — module imports — new:
  `from app.db import codex_entries, users, vector` (adds `users`),
  `from app.models.schemas.codex import CreateCodexEntryRequest`,
  `from app.services import codex as codex_service`. The D4 write path is frozen as an
  import, not left to the coder's choice. **No cycle:** `services/codex.py` imports only
  `authz` + `codex_index` from the service layer and neither reaches `tools` /
  `codex_tools`, so no `TYPE_CHECKING` deferral was needed for it — the existing
  `TYPE_CHECKING` block still covers `ToolContext` / `ResolvedSubject` only. Verified by
  importing `app.main`, `app.services.chat_turn`, and `codex_tools` / `codex` in either
  order.
- `backend/app/services/tools.py` — `ToolContext.codex_creates_this_turn: int = 0` — new
  (additive, defaulted, mutable — the `active_notes_proposal` precedent). No construction
  site changes; `chat_turn.py` was not touched.
- `backend/app/services/tools.py` — `TOOL_REGISTRY` entry `create_codex_entry` — new:
  `ToolDef(name="create_codex_entry", description=<explicit-command guard text>,
  args_schema=CreateCodexEntryArgs, binder=bind_create_codex_entry)`, placed after
  `write_codex_draft`. `binder`, never `callable` (exactly one is allowed). The
  description carries D1/D2's "only when the author has directly asked" instruction; it is
  data, so the coder may sharpen the wording but not drop the instruction.
- **Not touched, per the plan:** `backend/app/db/mode_tools.py` and
  `backend/app/db/assistant_modes.py` carry constant-data changes only, with no signature
  to freeze — `DEFAULT_MODE_TOOL_NAMES` and `DEFAULT_MODE_SYSTEM_PROMPTS` are wholly the
  coder's (DoD-8's mode half is therefore still red).
- Caller-compile edits (out of Source-files scope): None.

Import gate (no static type-check is configured for the backend):
`.venv/Scripts/python -c "import app.main"`, `import app.services.chat_turn` and a
`resolve_tools` / `build_tool_bindings` round trip for the new entry — all clean. Test
suite not run.

## Tests

### Tests (2026-08-10)

- `backend/tests/services/test_codex_create_tool.py` — covers DoD-1 — a valid
  create persists exactly one entry (kind/name/body/`author_id`) in the turn's
  book, with a **chapter** subject and with no subject at all, and returns a
  string naming kind, name and id
- `backend/tests/services/test_codex_create_tool.py` — covers DoD-2 — a `fact`
  given a non-blank name is refused with a string and writes no row
  (US-078.AC-2), while the same fact without a name lands
- `backend/tests/services/test_codex_create_tool.py` — covers DoD-3 — a
  `character` / `location` with an absent or whitespace-only name is refused with
  a string and writes no row
- `backend/tests/services/test_codex_create_tool.py` — covers DoD-4 — a
  co-author in a `proposal`-mode book, and a caller lacking
  `Capability.edit_codex_entry` (reader / non-member), are each refused with a
  **string, not an exception**, and write no row
- `backend/tests/services/test_codex_create_tool.py` — covers DoD-5 — the
  duplicate-name refusal, compared trimmed and case-insensitively, counting
  archived rows, scoped to book + kind + whole name; a `fact` is never refused
  for duplication
- `backend/tests/services/test_codex_create_tool.py` — covers DoD-6 — the 4th
  creation on one `ToolContext` is refused and writes nothing, a fresh context
  starts at zero and creates again, and refused attempts do not consume the cap
- `backend/tests/services/test_codex_create_tool.py` — covers DoD-7 — an
  exception forced out of `codex_service.create_entry` comes back as a string;
  the tool never raises and nothing is written
- `backend/tests/services/test_codex_create_tool.py` — covers DoD-8 — registry
  membership with a binder, `resolve_tools` / `build_tool_bindings` round trip
  bound to the turn's book, and `DEFAULT_MODE_TOOL_NAMES` listing the tool for
  the four authoring modes and not for `close-chapter`
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓,
  DoD-8 ✓, DoD-9 [manual/live, no test]

### Tests — amendment (2026-08-10)

- `backend/tests/db/test_mode_tools_seed.py` — covers DoD-8 — the pre-existing
  feature-024 pin on the **exact** per-mode default tool tuples (`EXPECTED_TOOLS`)
  widened to admit `create_codex_entry` in `edit-character`, `edit-location`,
  `edit-fact` and `write-chapter`; two added tests assert the tool is listed in
  `DEFAULT_MODE_TOOL_NAMES` and seeded as a `mode_tool` row for those four modes
  and **absent** from `close-chapter`. Feature 024's other assertions (five-mode
  convergence, non-blank prompts, re-seed idempotency, admin-edit/removal
  survival) are untouched and still pin exact tuples.
- Red until the coder lands DoD-8's `DEFAULT_MODE_TOOL_NAMES` change — the
  intended red-gate state for this file, not a fault.

### Tests — amendment 2 (2026-08-10)

- `backend/tests/services/test_tools.py` — covers DoD-8 — the pre-existing
  feature-024 pin on the **exact** `TOOL_REGISTRY` membership
  (`test_registry_has_single_web_search_entry__DoD3`) widened to admit
  `create_codex_entry` as a member. Still an exact-set assertion, not a
  "contains" check; every other assertion in the file is untouched.
- `backend/tests/services/test_chapter_tools.py` — covers DoD-8 — the
  pre-existing feature-024 pin on `write-chapter`'s **exact** seeded `mode_tool`
  selection (`WRITE_CHAPTER_DEFAULT_TOOLS`, used by
  `test_open_chapter_turn_is_offered_the_seeded_four__DoD12`) widened two-part:
  the expected membership gains `create_codex_entry` and the expected count
  rises seven → eight. The `len(seeded) == len(WRITE_CHAPTER_DEFAULT_TOOLS)`
  assertion is retained (it is derived from the set, so it moves with it and
  still forbids duplicate rows), and the set/allowlist equalities stay exact.
  Every other assertion in the file is untouched.
- Both widenings land **green immediately** — the implementation already exists,
  so these are pre-existing closed-set pins catching up with a delivered change,
  not a new red gate.
- Coverage unchanged: DoD-8 ✓ (now pinned in four files).

## Notes & Issues

- `backend/app/services/tools.py` is in the plan's Source files but needed **no coder edit**:
  the skeleton landed `ToolContext.codex_creates_this_turn` and the `create_codex_entry`
  `ToolDef`, and the frozen description already carries D1/D2's explicit-command instruction in
  full ("Call it ONLY when the author has directly asked … Never call it on your own
  initiative"), so there was nothing left to sharpen without weakening it.
- Gate run (no backend type-check exists): `import app.main`, `import app.services.chat_turn`,
  a `resolve_tools` / `build_tool_bindings` round trip (free params `kind` / `body` / `name`)
  and the two DB-free refusal paths (cap, no identity) — all clean. Tests not run.
