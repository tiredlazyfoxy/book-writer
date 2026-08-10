# Context — fast/007.codex-create-from-chat

Feature-wide context for the single plan in `plan.md`. Distilled from the persisted
harvester reports and the recorded design discussion; not a copy of either.

- Evidence: `docs/.cache/fast/007.codex-create-from-chat/harvest.md`
- Settled decisions (D1–D8, with the options rejected): `docs/.cache/fast/007.codex-create-from-chat/design-notes.md`
- Architecture: `docs/architecture/assistant-runtime.md`, `docs/architecture/assistant-config.md`,
  `docs/architecture/domain-codex.md`
- Conventions: root `CLAUDE.md` (backend layer separation, test command),
  `docs/plans/CLAUDE.md` (pipeline and ownership)

## What this feature is

While writing a chapter (or editing one codex entry), the author tells the assistant to
create a codex entry — a fact, a character, a location — and it is created. The work is a
single new mode-gated assistant tool, `create_codex_entry`, plus its registry entry, its
seeded mode defaults and one new per-turn counter field. Backend only.

**"MCP" in the user's request is the product's generic wording for a system-registered
backend tool** — confirmed with the user. This is a `TOOL_REGISTRY` entry: a plain async
Python function. It is not a Model Context Protocol server. `assistant-config.md` records
the same reading ("Tools ('MCPs' in product wording) are system-registered backend
functions"); `assistant-runtime.md` records web search calling Google through direct
`httpx`, "not an MCP client".

## Why it is exceptional, in one paragraph

**No existing bound tool performs a real database write.** Every write in the current tool
layer is either a `canvas` SSE emission or an in-memory `ToolContext` mutation. Two
architecture documents state that as a structural guarantee — `assistant-runtime.md` → "The
shared-canvas write for codex, as built" and `domain-codex.md` → "Codex authoring from the
chat (FEAT-018)" both say there is **no chat → codex write path, by construction**, and that
"nothing persists until the author saves" is a property rather than a check, explicitly
preferred because "a check can be bypassed by a later code path, an absent dependency
cannot." This feature ends that, deliberately and with an owner. `outcome.md` carries the
retraction of both passages.

## Files

### Source (the coder's scope — see `plan.md`)

| File | Role here |
|---|---|
| `backend/app/services/codex_tools.py` | the new args schema, tool function, binder, refusal/cap constants |
| `backend/app/services/tools.py` | `ToolContext` gains the per-turn creation counter; `TOOL_REGISTRY` gains the entry |
| `backend/app/db/mode_tools.py` | `DEFAULT_MODE_TOOL_NAMES` gains the tool for the four authoring modes |
| `backend/app/db/assistant_modes.py` | `DEFAULT_MODE_SYSTEM_PROMPTS` gains the explicit-command wording for the same four modes |

### Test (the test-coder's scope — disjoint)

| File | Role |
|---|---|
| `backend/tests/services/test_codex_create_tool.py` | the whole `[test]` coverage contract |

### Read-only, called into but not edited

- `backend/app/services/codex.py` — `create_entry(access, user, req)`; the single write path.
- `backend/app/db/users.py` — `get_by_id`, to turn `access.user_id` into the `User` row.
- `backend/app/db/codex_entries.py` — `list_by_book(...)`, for the duplicate-name scan.
- `backend/app/models/schemas/codex.py` — `CreateCodexEntryRequest`, `CodexKind`.
- `backend/app/services/chat_turn.py`, `backend/app/services/assistant_runtime.py` —
  **explicitly not in scope**; see below.

## Facts that bound the work

**Tool conventions (harvest 1).** A bound tool is a module-level `async def` taking
`context: "ToolContext"` positionally first, then exactly the args-schema fields as
keywords, returning `str`. The matching `bind_<tool>(context)` returns
`functools.partial(<tool>, context)`. **Every tool never raises** — every failure is an
informative string the model can respond to; a raising tool would abort the turn. Feature
`024`'s trace wrapper adds a backstop that converts an escaped exception to a string result,
but the tool must not rely on it.

**`ToolContext` is mutable and additive.** It is not frozen — it has not been since feature
`016` added `active_notes_proposal` for exactly this kind of per-turn state. Fields are added
defaulted, so no construction site has to change. `chat_turn.py` builds one `ToolContext` per
turn inside `run_turn`, which is precisely why a counter on it scopes to a turn.

**`ToolContext.book_id` is the hard scope filter.** The model can never name another book.
That is the whole cross-book boundary this tool needs (D7).

**Gating is three cases (`assistant-runtime.md`).** A mode-bearing subject gets exactly its
`mode_tool` rows; a subject with no mode gets `BASE_TOOL_NAMES` (`("web_search",)`); the
`None ⇒ whole registry` branch is unreachable from a turn. A new tool is therefore
unreachable until it is both in `TOOL_REGISTRY` **and** selected by a `mode_tool` row.

**Both seeding functions are idempotent per mode, not per row.** `seed_default_modes()`
writes a mode row only if none exists; `seed_default_mode_tools()` skips a mode entirely if
it has any `ModeTool` row. Consequences, both settled: the guard text has to live in
`ToolDef.description` because that is code resolved on every turn on every installation
(D2), and the tool ships unreachable on already-seeded databases until an admin adds it
through `012.assistant-config-editor` (D3, DoD-9). Making seeding per-row idempotent was
rejected — it would restore a tool an admin deliberately removed, on every boot.

**The single write path is `services/codex.py:create_entry(access, user, req)`** (D4). Its
internal order is `authz.require(access, Capability.edit_codex_entry)` →
`_require_writable_mode(access)` (the proposal-mode refusal) → `_resolve_name(kind, name)`
(the name/fact rule, US-078.AC-2) → `codex_entries.create(...)` →
`codex_index.index_entry(entry)` (best-effort, never raises). Forking any of that into the
tool was rejected. `create_entry` wants a `User` row and `ToolContext` carries only
`access.user_id: int`, so the tool fetches the row via `db/users.get_by_id`; the caller is
the chat's own author by construction.

**`CreateCodexEntryRequest` is `kind: CodexKind`, `name: str | None = None`, `body: str`.**
The new args schema mirrors those three fields.

**The duplicate-name scan uses the existing list function** (D5):
`codex_entries.list_by_book(book_id, kind=…, include_archived=True, needle=name)` narrows
the scan, and an exact trimmed case-insensitive comparison decides the match — `needle` is a
substring match over name *or* body and cannot decide it alone. Archived rows are included
on purpose: recreating a name that exists but is hidden is the more confusing outcome.
Adding a name-lookup function to `db/codex_entries.py` and adding a DB uniqueness constraint
were both rejected.

**Facts cannot be de-duplicated.** A fact has no name (US-078.AC-2) and comparing bodies is
not a duplicate test. Accepted.

**Archiving is not built.** `017.codex-archive-restore` is roadmapped and unbuilt and
`013.codex` shipped no `DELETE`, so an entry the model invents can be edited but never
removed. The failure mode is not "a wrong entry" but "a wrong entry that stays" — which is
why the per-turn cap (3) and the duplicate refusal exist at all.

**Do not reuse `_refuse_write`** (D7). Its first link refuses a subject that is not a codex
entry, and running while the subject is a chapter is the entire point of this feature. This
is the first codex tool whose target is the book rather than the resolved subject.

**Layer rules.** `services/codex_tools.py` must not touch `session`, `select()` or
`session.add()`; it reaches data through `services/codex.py` or a `db/` module. Cross-imports
between `assistant_runtime` / `tools` / `codex_tools` are `TYPE_CHECKING`-only to avoid
import cycles. Module-level constants for the cap and every refusal message follow the
file's existing `_CANVAS_*_MESSAGE` convention.

**Mode scope is the four authoring modes** (D6): `edit-character`, `edit-location`,
`edit-fact`, `write-chapter`. **Not `close-chapter`** — a close run is the least supervised
turn in the system (it already drafts summaries, may replace the live note set, may raise
flags and may end with the chapter `closed`), and a run nobody is watching minting codex
entries is the runaway case the cap exists to bound.

**No new SSE frame and no frontend change** (D8). Feature `024`'s generic wrapper emits
`tool_call` / `tool_result` around every bound tool and persists the pair to
`ChatMessage.tool_trace`, so the author's audit trail — what was created, with which
arguments — exists for free and survives a reload. `ToolCallTrace.tsx` renders it with its
existing per-tool-name switch.

## The guard, stated plainly

The guard chosen by the user is **prompt-level** (D1): the tool's `description` instructs the
model to call it only on the author's explicit request, and mode gating bounds where it
exists at all. Propose-and-confirm (a card in the transcript with a Create button) and
arm-the-turn (a composer toggle sending a flag on `TurnRequest`) were both presented, both
were structural rather than prompt-level, and both were **rejected by the user as friction**.

**Nothing in the system verifies that the author commanded the creation.** The model decides
whether it was asked. This is a decision with an owner, not an inferred default — the same
category as feature `024`'s seeding reversal. The two backstops (per-turn cap of 3,
duplicate-name refusal) are what bound the damage, not what verify the command.

## Accepted limitations to carry into `outcome.md`

1. An already-open codex list page does not refresh — `frontend.md` forbids cross-page
   callbacks and a shared store, so the entry appears on the list's next visit.
2. Facts cannot be de-duplicated.
3. The tool is unreachable on existing databases until an administrator selects it for the
   four modes.

## Product status

Nothing in `docs/product/` specifies creating a codex entry directly from a chat turn.
FEAT-018 (UC-076/077, US-086/087/088) specifies the **canvas draft** path and the opposite
postcondition for it. Read strictly, US-088.AC-2 is scoped to "a drafted or rewritten entry
shown in the chat", so this is a **new flow rather than a contradicted criterion** — but a
use case and a story are missing, and FEAT-018's structural language needs revisiting.
`outcome.md` carries that as a note for `/product-spec`. **Never edit `docs/product/` from
this feature.** DoD items cite `US-078.AC-2` where it applies; the rest carry no id by
necessity.

## Commands

- Backend tests: `cd backend && .venv/Scripts/python -m pytest`
- No backend static type-check is configured; no linter is configured.

## Evidence gap (for the record)

`harvest.md` carries **two** harvester reports, not three. The verbatim surfaces of
`services/codex.py` (`CodexError` / `CodexErrorReason`, `_require_writable_mode`,
`_resolve_name`), `db/codex_entries.py`'s full public surface, the seeding constants and the
backend test layout are **not** in the cache file; harvest 2 explicitly flags the first of
those as a gap it did not read. This does not block planning — `plan.md` states intent in
prose and the `fast-skeleton` agent reads code to freeze the signatures — but the skeleton
agent must confirm those surfaces itself rather than assume them, and any mismatch is a
skeleton-stage escape-valve, not a coder guess.
