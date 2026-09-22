# fast/007.codex-create-from-chat — create a codex entry from a chat turn

Feature-wide context: `context.md`. Settled decisions with the options rejected:
`docs/.cache/fast/007.codex-create-from-chat/design-notes.md` (D1–D8) — those are closed;
nothing below re-opens one.

## Goal

Add a mode-gated assistant tool, `create_codex_entry`, that **persists** a codex entry in
the turn's book when the author asks for one, available in `edit-character`,
`edit-location`, `edit-fact` and `write-chapter`. Backend only; no frontend, no new SSE
frame, no change to the turn runner or the gating rules.

## Decisions carried (do not re-derive)

- **The guard is prompt-level, by the user's explicit choice.** The `ToolDef.description`
  instructs the model to call the tool only on the author's explicit request; mode gating
  bounds where it exists. Propose-and-confirm and arm-the-turn were offered and rejected as
  friction. Nothing verifies the command.
- **The guard text must live in the `ToolDef.description`**, because both seeding functions
  are idempotent per mode and never reach an already-seeded database. The seeded mode
  prompts get the same wording, but only fresh installs see it.
- **The tool ships unreachable on existing databases** and an admin adds it once through
  `012.assistant-config-editor`. That is DoD-9, not a code workaround.
- **One write path:** `codex_service.create_entry(access, user, req)`. The capability check,
  the proposal-mode refusal, the name/fact rule and the vector indexing are not re-expressed
  here.
- **Two backstops:** a per-turn creation cap of 3, and a duplicate-name refusal for
  `character` / `location`.
- **Book-scoped, not subject-scoped.** `_refuse_write`'s chain must **not** be reused — its
  first link refuses a non-codex subject, and running while the subject is a chapter is the
  point.

## Source files

- `backend/app/services/codex_tools.py` — the args schema, the tool function, the binder, the cap and refusal constants
- `backend/app/services/tools.py` — the new per-turn counter field on `ToolContext`; the new `TOOL_REGISTRY` entry
- `backend/app/db/mode_tools.py` — `DEFAULT_MODE_TOOL_NAMES` for the four authoring modes
- `backend/app/db/assistant_modes.py` — `DEFAULT_MODE_SYSTEM_PROMPTS` wording for the same four modes

## Test files

- `backend/tests/services/test_codex_create_tool.py`
- `backend/tests/db/test_mode_tools_seed.py` — pre-existing pin on the **exact** per-mode
  default tool tuples (`EXPECTED_TOOLS`); widened by this feature for DoD-8 only, to admit
  `create_codex_entry` in `edit-character`, `edit-location`, `edit-fact` and `write-chapter`
  and to keep it absent from `close-chapter`. The file's other assertions are left alone.
- `backend/tests/services/test_tools.py` — pre-existing feature-024 pin on the **exact**
  `TOOL_REGISTRY` membership; widened by this feature for DoD-8 only, to admit
  `create_codex_entry` as a registry member. The pin stays an **exact-set** assertion — do
  not weaken it into a "contains" check. Every other assertion in the file is left alone.
- `backend/tests/services/test_chapter_tools.py` — pre-existing feature-024 pin on
  `write-chapter`'s **exact** seeded `mode_tool` selection; widened by this feature for
  DoD-8 only, to admit `create_codex_entry` in that selection. This pin asserts the set's
  **length** as well as its membership, so the widening is **two-part**: the expected
  membership gains the new name *and* the expected count goes up by one. The pin stays an
  **exact-set** assertion — do not weaken it into a "contains" check, and do not drop the
  length assertion. Every other assertion in the file is left alone.

Those three pre-existing pins are in scope **for the DoD-8 widening only**; no other
pre-existing test is in scope. This list stays disjoint from `## Source files` — every entry
above is under `backend/tests/`, every source entry is under `backend/app/`.

## Interface intent

Prose only — the `fast-skeleton` agent reads the code and freezes the exact signatures.

**Args schema (`codex_tools.py`).** A Pydantic model carrying the entry's **kind**, an
optional **name**, and the **body** — mirroring `CreateCodexEntryRequest`'s three fields.
Ids and enums cross the model boundary the same way the neighbouring codex tools' args
schemas do (`CodexSearchArgs`, `CodexEntryReadArgs`, `WriteCodexDraftArgs`); do not invent a
second vocabulary for `kind`.

**Tool function (`codex_tools.py`).** An async module-level function taking the
`ToolContext` positionally first, then exactly the args-schema fields as keywords, returning
a **string**. On success it returns a message naming what it created — the kind, the name
and the id. On every failure it returns an informative refusal string. **It never raises:**
`CodexError`, `authz.BookAuthorizationError` and any other exception all become strings.

**Order of work inside the tool**, and it is load-bearing because the cheap refusals must
precede the write:

1. the per-turn cap;
2. the duplicate-name check, for `character` / `location` only;
3. resolve the acting `User` from `context.access.user_id`;
4. delegate to `codex_service.create_entry`;
5. increment the per-turn counter;
6. format the result string.

**Binder (`codex_tools.py`).** A `bind_*` function beside the tool, following the existing
`functools.partial` pattern of `bind_codex_search` / `bind_write_codex_draft`.

**Duplicate-name check.** Scope by `ToolContext.book_id` and the requested kind, over
`codex_entries.list_by_book(..., include_archived=True, needle=name)`, and decide the match
with an exact trimmed case-insensitive comparison — the needle narrows the scan but is a
substring match over name *or* body and cannot decide it. A `fact` is never checked.

**`ToolContext` (`tools.py`).** A new mutable integer field counting codex creations in the
current turn: additive, defaulted to zero, the same discipline `access`, `subject`,
`emit_frame`, `selection_text` and `active_notes_proposal` were added under. `chat_turn.py`
constructs `ToolContext` once per turn and passes no such argument, so **no construction
change is needed and `chat_turn.py` is not in scope.**

**`TOOL_REGISTRY` (`tools.py`).** A new `ToolDef` with the tool name, the new args schema,
the binder, and a **description carrying the explicit-command instruction** — the model must
be told, in the description, to call this only when the author has directly asked for an
entry to be created, and not on its own initiative while writing or discussing.

**Seeded defaults (`db/mode_tools.py`).** The tool name added to `DEFAULT_MODE_TOOL_NAMES`
for `edit-character`, `edit-location`, `edit-fact` and `write-chapter` — and **not** for
`close-chapter`. Do not restructure the constant or change the seeding function's per-mode
idempotency.

**Seeded prompts (`db/assistant_modes.py`).** Wording added to the four corresponding
`DEFAULT_MODE_SYSTEM_PROMPTS` entries carrying the same explicit-command constraint. Do not
change how or when the modes are seeded.

**Constants.** The cap and every refusal message are module-level constants in
`codex_tools.py`, following the file's existing `_CANVAS_*_MESSAGE` convention.

## Definition of done

1. `[test]` — Creating with a valid kind/name/body persists one `CodexEntry` in the turn's
   book with that kind, name and body, `author_id` set to the acting user, and returns a
   string naming the created entry.
2. `[test]` — A `fact` supplied with a non-blank name is refused with a string and **no row
   is created** (US-078.AC-2 — a fact has no name).
3. `[test]` — A `character` or `location` supplied with no name (absent or blank) is refused
   with a string and no row is created.
4. `[test]` — A co-author in a `proposal`-mode book is refused with a string and no row is
   created; a caller lacking `Capability.edit_codex_entry` is likewise refused with a
   string, not an exception.
5. `[test]` — A `character` or `location` whose name already exists in the book for that
   kind — compared trimmed and case-insensitively, **including archived rows** — is refused
   with a string and no row is created. A `fact` is never refused for duplication.
6. `[test]` — The 4th creation attempt within one turn is refused with a string and no row
   is created; the count is held per `ToolContext`, so a fresh context starts at zero.
7. `[test]` — Any exception escaping the create path becomes a string result; the tool never
   raises.
8. `[test]` — `create_codex_entry` is present in `TOOL_REGISTRY` with a binder and resolves
   through `resolve_tools` / `build_tool_bindings`; `DEFAULT_MODE_TOOL_NAMES` lists it for
   `edit-character`, `edit-location`, `edit-fact` and `write-chapter` and **not** for
   `close-chapter`.
9. `[manual/live]` — On an already-seeded database, an administrator adds
   `create_codex_entry` to the four modes in the assistant-config editor; a live chat turn
   where the author asks for an entry creates exactly one, and an ordinary chapter-writing
   turn that does not ask creates none.

## Out of scope

- Any confirm-or-arm affordance — the propose-and-confirm card, the composer toggle. Both
  were explicitly rejected by the user.
- Editing, archiving or deleting a codex entry from chat.
- Refreshing an already-open codex list page — `frontend.md` forbids cross-page callbacks;
  the entry appears on the list's next visit, recorded as an accepted limitation.
- Any duplicate-name rule on the human-facing `POST /books/{id}/codex` route, and any DB
  uniqueness constraint on `(book_id, kind, name)`.
- Any frontend file, any new SSE frame, and any change to `chat_turn.py`,
  `assistant_runtime.py` or the mode/tool gating rules.
- Any edit to `docs/product/` or `docs/architecture/` — the intended doc changes are
  `outcome.md`'s, applied later by `/architect`.
- Making the seeding functions per-row idempotent.
