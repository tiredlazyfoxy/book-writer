# Assistant Configuration — modes, sub-agents and tools

**Realizes:** FEAT-020, UC-095, UC-096, UC-097, US-110, US-111, US-112, US-113, US-114

The admin-configured behaviour of the AI assistant: the fixed working **modes**, the admin-created **sub-agents**, the code-defined **tool** catalogue, and the selections that wire them together. This document holds the **stored configuration model** — what an admin can express and how it persists.

**The runtime that consumes it is `assistant-runtime.md`**: mode determination, system-prompt composition, tool gating, the `chat_with_tools` protocol, sub-agent delegation, model resolution and the SSE frame vocabulary.

> **Why this is two documents** (split 2026-07-29). This file was one document about two things — the admin's stored configuration, and the runtime that turns it into a live assistant call. Features `011.chat-panel` and `013.codex` tripled the runtime half. Splitting keeps each file cohesive and inside the folder's ~400-line rule. Nothing was dropped in the split; the runtime material moved verbatim-and-extended into `assistant-runtime.md`.

Index and cross-cutting conventions: `domain-model.md`. Related: `assistant-runtime.md` (the runtime), `domain-chat.md` (chats and the remaining assistant boundary), `authorization.md` (admin-only rule), `retrieval.md` (the search surface the codex tools call), `frontend-workspace.md` (the activity that determines the current mode), `backend/persistence.md` + `backend/book-domain.md` (`TABLE_REGISTRY`, codecs), `quick-reference.md` (the endpoint and DTO tables).

**Built as of 2026-07-27.** The config half shipped with `012.assistant-config-editor`; its tables and codecs shipped earlier with `008.data-domain`; the runtime half shipped with `011.chat-panel` and `013.codex`. This is no longer a design-ahead document — where it describes as-built behaviour it says so.

## The configuration model

Five entities. Two are admin-editable config tables (`AssistantMode`, `SubAgent`); three are link tables that record the admin's selections. The tool catalogue is **code, not a table**.

### AssistantMode — the fixed five, seeded

| Field | Type / notes |
|---|---|
| `key` | **primary key**, string ∈ `{edit-character, edit-location, edit-fact, write-chapter, close-chapter}` |
| `system_prompt` | nullable text — the admin's standing instruction for this activity; **null or empty is valid** (US-110.AC-4) |
| `created_at` / `modified_at` | timestamps |

The five modes are a **fixed system set, not admin-creatable** (UC-095 precondition: "one of the fixed system set of five"). They are **seeded rows** written once at instance setup; the admin edits their `system_prompt` and their tool / sub-agent selections but never adds or removes a row. A `disabled` non-admin, or any author, cannot reach them (see `authorization.md`).

**Why the primary key is the `key` string, not a snowflake — a deliberate, narrow exception to the system-wide id convention.** Every other entity uses an application-generated snowflake (`domain-model.md` → "Conventions"). Modes are the exception because they are a **fixed, seeded, enum-like set whose identity must be identical across every instance**: the `mode_tool` and `mode_subagent` link rows reference a mode, and instance-global config is exported and re-imported (below). A snowflake would differ between instances, so a seeded mode on the target instance and the same mode in an incoming archive would collide on any natural-key uniqueness while their surrogate ids disagreed — breaking the links. A stable natural key makes import an idempotent UPSERT on `key` and keeps every link instance-independent. This mirrors the same reasoning that has tools referenced **by registry name, not FK** (below). Recorded as decision history in `domain-model.md`.

### SubAgent — admin-created delegated worker

| Field | Type / notes |
|---|---|
| `id` | snowflake PK (string at every JSON boundary, per the id convention) |
| `name` | **unique at the DB level** (US-113.AC-3); non-blank (UC-096 exception) |
| `system_prompt` | text — the worker's own standing instruction |
| `disabled` | bool, default false — **disable-not-delete** (US-114.AC-2/AC-3); mirrors FEAT-003's user disable |
| `llm_server_id` | nullable FK → `LlmServer.id` — the model assignment (below) |
| `model_name` | nullable string — the model on that server |
| `created_at` / `modified_at` | timestamps |

A sub-agent is a reusable delegated worker the admin creates freely (UC-096). **Disable, never delete**, the same pattern as user accounts (FEAT-003): disabling **detaches it from every mode** (delete its `mode_subagent` rows) and stops it being invoked; it is reversible, and a **re-enabled sub-agent stays unattached** until modes select it again (US-114.AC-3) — because the links were deleted, not merely suppressed, re-enabling restores nothing.

**Model assignment is nullable, and the two model fields move together** (US-113.AC-5/AC-6, US-114.AC-4). Either **both null** — inherit the main chat's model, the default (US-113.AC-6) — or **both set** — a specific `(server, model)` the configured LLM servers expose. A half-set state (one null, one not) is invalid and refused at the service edge. The reference is `(llm_server_id, model_name)` rather than a bare model string because the `llm` client **binds a model at client construction** (`backend.md` → "LLM client") and a model only exists on a registered `LlmServer` (FEAT-004): naming the server is what makes the assignment resolvable to a client. **Modes carry no model field** — model is a sub-agent concept only. The **main chat's** own model is not configured here either: it is chosen by the author, per chat, and stored on `Chat` (`domain-chat.md`, `assistant-runtime.md` → "Model resolution").

### Tool registry — code-defined, not a table

Tools ("MCPs" in product wording) are **system-registered backend functions** exposed to the assistant. The catalogue is **code, not a DB table**, matching the product's "the registry itself is code-defined" and the reference project. It mirrors the existing static-list registries — `TABLE_REGISTRY` in `services/db_import_export.py` and `VECTOR_SOURCE_REGISTRY` in `db/vector.py` — both plain module-level lists with no decorator or register-function machinery.

**As built** (`011.chat-panel`, extended by `013.codex`): `TOOL_REGISTRY` lives at **`backend/app/services/tools.py`** as a module-level literal list of **frozen `ToolDef` dataclasses**, alongside the builder that turns a resolved list into OpenAI tool definitions (`pydantic_to_openai_tool`) plus a name→callable map.

```
TOOL_REGISTRY: list[ToolDef]     # module-level literal list

ToolDef:
    name        : str                 # stable string identifier — what a selection stores
    description : str                 # shown to the model in the tool definition
    args_schema : type[BaseModel]     # Pydantic arg schema
    callable    : Callable            # sync or async; dispatched by chat_with_tools
    binder      : ToolBinder | None    # 013: builds the callable from a ToolContext
```

**Why a frozen dataclass rather than a 4-tuple** (the shape the neighbouring registries use): the fields are read by name in three places (definition building, callable binding, the skip-and-log path), and a tuple would make each of those a positional index. Frozen, because the catalogue is a constant — nothing may mutate an entry at runtime.

**Registry membership as shipped:** `web_search` (feature `011.chat-panel`, its first and at the time only entry) plus three codex tools defined in `services/codex_tools.py` and registered here by `013.codex` — `codex_search`, `codex_read_entry` and `write_codex_draft`. The codex three are **context-bearing**: they need the book (and, for the canvas write, the resolved subject and the frame emitter), which a plain module function cannot know, so `ToolDef` gained an optional `binder` that builds the callable from a per-turn `ToolContext`. A bound tool offered with no context is skipped and logged. **Which of these a given turn may call is not a registry property — it is the runtime's gating question** (`assistant-runtime.md` → "Tool gating").

**Only *selections* persist; the catalogue itself is never exported** — the same stance as `VECTOR_SOURCE_REGISTRY` (`backend/persistence.md`). A tool is identified everywhere by its stable string `name`; link rows store that name, never a foreign key, because a tool is not a row.

### The three link tables

Each records an admin selection. Following `BookMember`'s reasoning (`domain-book.md`), each carries a **surrogate snowflake `id` PK plus a unique constraint on its natural columns**, so the import/export codec has the same shape as every other table while the natural pair carries the "one selection" semantics.

| Table | Natural columns (unique) | Records |
|---|---|---|
| `mode_tool` | `(mode_key, tool_name)` | a tool selected for a mode (US-111) |
| `subagent_tool` | `(sub_agent_id, tool_name)` | a tool selected for a sub-agent (UC-096 step 4) |
| `mode_subagent` | `(mode_key, sub_agent_id)` | a mode may delegate to this sub-agent (US-112) |

`mode_key` references `AssistantMode.key`; `sub_agent_id` references `SubAgent.id`; `tool_name` references `TOOL_REGISTRY` **by string, not FK**.

**The mode↔sub-agent link is one row, stored canonically on the sub-agent side, edited from both views.** US-112.AC-2 requires the link to be shown and editable from the mode view *and* from the sub-agent view. There is exactly **one `mode_subagent` row** per `(mode, sub-agent)` pair; both UIs read and write that same row. "Canonically on the sub-agent side" means the model treats the sub-agent as the owning side of the many-to-many (which is also why disabling a sub-agent deletes its links) — but there is no second table and no direction-of-truth ambiguity: the mode view and the sub-agent view are two editors over one set of rows.

**A selection save is delete-all-then-recreate for that owner** (as built, `012.assistant-config-editor`). Four bulk operations back it: `mode_tools.delete_by_mode`, `mode_subagents.delete_by_mode`, `subagent_tools.delete_by_sub_agent` and `mode_subagents.delete_by_sub_agent`. The requested set is **de-duplicated before recreate**, so a client sending the same name twice cannot violate the natural-key unique constraint. The two-editors-over-one-row-set property above depends on **each bulk delete touching only its own slice** — a mode save clears that mode's links and no others, a sub-agent save clears that sub-agent's, so the two editors never erase each other's work.

### Validation at the config edge — and why the runtime is deliberately more tolerant

Read side by side these two rules look contradictory; they address **different moments**, and both are correct.

**The config edge refuses** (as built, `012.assistant-config-editor`): an unknown tool name, an unknown or `disabled` sub-agent, an unknown mode key, a blank name (**400**), a duplicate sub-agent name (**409**) and a half-set model pair (**400**). Validation happens at write time against the **live registry and the live rows**, because an admin who selects something that does not exist has made a mistake worth telling them about immediately.

**The runtime skips and logs** a stored selection whose tool has since left `TOOL_REGISTRY`. The code catalogue is the source of truth and a selection is only an allow-mark; a tool retired in code must not break a stored configuration or fail a turn.

**Accepted consequence, recorded rather than fixed:** deactivating or deleting an `LlmServer` after the fact leaves stored sub-agent assignments **unusable at runtime**, and there is **no re-validation sweep**. The config edge validated the pair when it was written; nothing re-checks it later. What the runtime does with such an assignment is `assistant-runtime.md` → "Model resolution" (it is a delegation failure, not a silent fallback).

### Structural bound: delegation is one level deep

There is no `subagent_subagent` table. Modes select sub-agents; sub-agents select **tools only**. A sub-agent therefore cannot delegate to another sub-agent — the model makes unbounded delegation recursion **unrepresentable**, not merely discouraged, which is what keeps the runtime loop bounded by construction.

## Persistence and registry obligations

These are **instance-global admin config** — the same class as `users` and `llm_servers`, **not** book-scoped. They are exported alongside the global config, **never inside a book export**.

**As shipped** (`008.data-domain`): all five tables, their codecs and their registry positions are realized in code.

- **Codecs.** Every table owes its `to_dict` / `from_dict` pair in the same change that adds it (root `CLAUDE.md`; `backend/persistence.md`). Snowflake ids emit as strings and parse string-or-legacy-number; `AssistantMode.key` emits verbatim as its own PK — the first codec whose PK is a natural key rather than an `int()`-coerced snowflake.
- **`TABLE_REGISTRY` order.** The five tables sit **in FK dependency (import) order, in the global-config block before `books`**, because a sub-agent references an `LlmServer` and the link tables reference modes and sub-agents:

  ```
  users, llm_servers,
  assistant_modes, sub_agents, mode_tools, subagent_tools, mode_subagents,   # FEAT-020 global config
  books, book_members, chapters, …                                           # book domain
  ```

  See `backend/book-domain.md` → "The book-domain table registry", which carries the full list.
- **`TOOL_REGISTRY` is code, not exported** — like `VECTOR_SOURCE_REGISTRY`. Nothing about the catalogue crosses the import/export boundary; only the selection rows do.
- **Seeding, both first-run paths.** `seed_default_modes()` writes the five `AssistantMode` rows and is wired into **`services/setup.py::create_database`** and — added by `012.assistant-config-editor` — into **`import_database`**. It is **idempotent by `key`**, so a fresh instance that seeds its own modes and then restores an archive converges rather than colliding; that convergence is exactly what the natural-key PK exists to provide. Before the second wiring, an instance bootstrapped by DB import had no modes and showed an empty editor. Full detail lives in `backend/persistence.md` (the startup lifecycle) — it is not repeated here.

Module placement follows the four-layer split (`backend/book-domain.md`): one `db/` module per table (`db/assistant_modes.py`, `db/sub_agents.py`, `db/mode_tools.py`, `db/subagent_tools.py`, `db/mode_subagents.py`), `models/` tables + DTOs in `models/schemas/assistant_config.py`, and `services/assistant_config.py` holding the CRUD and the name-unique / model-pair invariants.

## The admin route surface

Frozen by `012.assistant-config-editor`: **`routes/admin/assistant_config.py`**, prefix **`/api/admin/assistant-config`**, eight endpoints —

`GET /tools` · `GET /modes` · `PUT /modes/{mode_key}` · `GET /sub-agents` · `POST /sub-agents` · `PUT /sub-agents/{sub_agent_id}` · `POST /sub-agents/{sub_agent_id}/disable` · `POST /sub-agents/{sub_agent_id}/enable`

The **endpoint and DTO tables live in `quick-reference.md`**, not here; this section carries the taxonomy and the reasoning. The reason→status map is the one described under "Validation at the config edge" (400 / 404 / 409, with 403 from `require_role`); `backend/features.md` carries the as-shipped route inventory.

**Two deliberate absences.** There is **no single-mode GET** — the mode list is five rows, so a detail fetch would add a route with no caller. There is **no DELETE anywhere**: modes are a fixed seeded set and sub-agents are disable-not-delete, so a delete verb would express something the model forbids.

**Both save endpoints are full-replace `PUT`s, not partial `PATCH`es.** The model pair is therefore always explicitly present in the body, and `null` + `null` unambiguously means *inherit* rather than *leave as it was*. This deliberately does **not** mirror `services/chats.py:update_chat`, whose partial `PATCH` re-validates the pair only when at least one half is present in the body (so a title-only patch cannot wipe an existing pair). Two adjacent features handle the same `(llm_server_id, model_name)` invariant with different update semantics: the chat's is a small mixed-concern resource edited field-by-field from a settings panel, while a mode or sub-agent save is a whole-form replace including its selections. Without this note the difference reads as an inconsistency; it is a consequence of the two surfaces, and either would be wrong in the other's place.

## Runtime consumption

**Moved.** How the stored configuration becomes one assistant call — mode determination from the workspace activity, the four-layer system-prompt composition, tool gating, the `chat_with_tools` protocol and its seam, sub-agent delegation as synthetic tools, model resolution, and the SSE frame vocabulary — is **`assistant-runtime.md`**. That document is the built slice of the otherwise-deferred FEAT-013 subsystem; it reads the tables above through the `db/` layer and never through `services/assistant_config.py`.

## Authorization

**Admin-only, system-global (ACT-001).** All of FEAT-020's configuration sits behind the existing `require_role(admin)` dependency, the same configuration class as LLM servers (FEAT-004) — it is **not** a book-scoped capability and never enters the `BookAccess` matrix. Authors never view or configure it. This does **not** breach FEAT-011's "admin never participates in a book," because it is **global assistant configuration, not book participation** — the same admin-interface-only pattern as FEAT-011's moderation view. See `authorization.md` → "Global assistant configuration (FEAT-020)".

## Out of scope

This document covers the FEAT-020 configuration model only.

- **The runtime**, and everything still deferred around it, is `assistant-runtime.md` — see its "Out of scope — still deferred" section for the current boundary (context assembly, the chapter canvas protocol, token-level streaming, token budgeting).
- **Two questions this document used to list as open are now closed.** Whether a mode's tools default on or off is settled: **an unconfigured mode grants no tools — zero `mode_tool` rows is an empty allowlist, not the whole registry.** The reasoning: there must be a representable way to say *"this mode gets no tools"*, and overloading empty to mean *all* both makes that state unexpressible and points the default in the unsafe direction. This settles the **architectural** answer only — the matching `_TBD:` on FEAT-020 in `docs/product/` remains **`/product-spec`'s to close**. The main-chat model selection is likewise settled (chosen by the author, per chat) — see `assistant-runtime.md` and `domain-chat.md`.
