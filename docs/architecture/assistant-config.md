# Assistant Configuration — modes, sub-agents, tools, and the runtime slice that consumes them

**Realizes:** FEAT-020, UC-095, UC-096, UC-097, US-110, US-111, US-112, US-113, US-114

The admin-configured behaviour of the AI assistant: the fixed working **modes**, the admin-created **sub-agents**, the code-defined **tool** catalogue, and the selections that wire them together — **plus** the runtime slice that turns that configuration into a live assistant call. This is the **first designed slice of the otherwise-deferred FEAT-013 assistant subsystem**; `domain-chat.md` holds the `Chat` / `ChatMessage` entities and the boundary of what is still deferred, and points here for the part that is now designed.

Index and cross-cutting conventions: `domain-model.md`. Related: `domain-chat.md` (chats), `domain-book.md` / `domain-chapter.md` (the FEAT-019 `system_prompt` fields this composes with), `authorization.md` (admin-only rule), `retrieval.md` (the search surface a tool will eventually call), `frontend-workspace.md` (the activity that determines the current mode), `backend/persistence.md` + `backend/book-domain.md` (`TABLE_REGISTRY`, codecs).

> **Scope.** This pass designs FEAT-020's config model **and** the runtime that consumes it — but only that slice of the assistant. Context assembly (retrieved book/chapter/codex *content* into the prompt), the SSE shared-canvas write protocol, web search, the main-chat model selection, and token budgeting remain deferred; see "Out of scope" and `domain-chat.md`.

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

**Model assignment is nullable, and the two model fields move together** (US-113.AC-5/AC-6, US-114.AC-4). Either **both null** — inherit the main chat's model, the default (US-113.AC-6) — or **both set** — a specific `(server, model)` the configured LLM servers expose. A half-set state (one null, one not) is invalid and refused at the service edge. The reference is `(llm_server_id, model_name)` rather than a bare model string because the `llm` client **binds a model at client construction** (`backend.md` → "LLM client") and a model only exists on a registered `LlmServer` (FEAT-004): naming the server is what makes the assignment resolvable to a client. **Modes carry no model field** — model is a sub-agent concept only; the main chat's own model is the open FEAT-013 `_TBD:`.

### Tool registry — code-defined, not a table

Tools ("MCPs" in product wording) are **system-registered backend functions** exposed to the assistant. The catalogue is **code, not a DB table**, matching the product's "the registry itself is code-defined" and the reference project. It mirrors the existing static-list registries — `TABLE_REGISTRY` in `services/db_import_export.py` and `VECTOR_SOURCE_REGISTRY` in `db/vector.py` — both plain module-level lists of tuples with no decorator or register-function machinery:

```
TOOL_REGISTRY: list[ToolDef]     # module-level literal list

ToolDef:
    name        : str                 # stable string identifier — what a selection stores
    description : str                 # shown to the model in the tool definition
    args_schema : type[BaseModel]     # Pydantic arg schema
    callable    : Callable            # sync or async; dispatched by chat_with_tools
```

**Only *selections* persist; the catalogue itself is never exported** — the same stance as `VECTOR_SOURCE_REGISTRY` (`backend/persistence.md`). A tool is identified everywhere by its stable string `name`; link rows store that name, never a foreign key, because a tool is not a row. A selection naming a tool absent from the current `TOOL_REGISTRY` (a tool retired in code) is **skipped and logged** at runtime — the code catalogue is the source of truth, the selection is only an allow-mark.

### The three link tables

Each records an admin selection. Following `BookMember`'s reasoning (`domain-book.md`), each carries a **surrogate snowflake `id` PK plus a unique constraint on its natural columns**, so the import/export codec has the same shape as every other table while the natural pair carries the "one selection" semantics.

| Table | Natural columns (unique) | Records |
|---|---|---|
| `mode_tool` | `(mode_key, tool_name)` | a tool selected for a mode (US-111) |
| `subagent_tool` | `(sub_agent_id, tool_name)` | a tool selected for a sub-agent (UC-096 step 4) |
| `mode_subagent` | `(mode_key, sub_agent_id)` | a mode may delegate to this sub-agent (US-112) |

`mode_key` references `AssistantMode.key`; `sub_agent_id` references `SubAgent.id`; `tool_name` references `TOOL_REGISTRY` **by string, not FK**.

**The mode↔sub-agent link is one row, stored canonically on the sub-agent side, edited from both views.** US-112.AC-2 requires the link to be shown and editable from the mode view *and* from the sub-agent view. There is exactly **one `mode_subagent` row** per `(mode, sub-agent)` pair; both UIs read and write that same row. "Canonically on the sub-agent side" means the model treats the sub-agent as the owning side of the many-to-many (which is also why disabling a sub-agent deletes its links) — but there is no second table and no direction-of-truth ambiguity: the mode view and the sub-agent view are two editors over one set of rows.

### Structural bound: delegation is one level deep

There is no `subagent_subagent` table. Modes select sub-agents; sub-agents select **tools only**. A sub-agent therefore cannot delegate to another sub-agent — the model makes unbounded delegation recursion **unrepresentable**, not merely discouraged, which is what keeps the runtime loop below bounded by construction.

## Persistence and registry obligations

These are **instance-global admin config** — the same class as `users` and `llm_servers`, **not** book-scoped. They are exported alongside the global config, **never inside a book export**.

- **Codecs.** Every table owes its `to_dict` / `from_dict` pair in the same change that adds it (root `CLAUDE.md`; `backend/persistence.md`). Snowflake ids emit as strings and parse string-or-legacy-number; `AssistantMode.key` emits verbatim as its own PK.
- **`TABLE_REGISTRY` order.** The five tables append **in FK dependency (import) order, in the global-config block before `books`**, because a sub-agent references an `LlmServer` and the link tables reference modes and sub-agents:

  ```
  users, llm_servers,
  assistant_modes, sub_agents, mode_tools, subagent_tools, mode_subagents,   # FEAT-020 global config
  books, book_members, chapters, …                                           # book domain
  ```

  See `backend/book-domain.md` → "The book-domain table registry", which carries this list.
- **`TOOL_REGISTRY` is code, not exported** — like `VECTOR_SOURCE_REGISTRY`. Nothing about the catalogue crosses the import/export boundary; only the selection rows do.
- **Seeding.** The five `AssistantMode` rows are seeded at instance setup and are idempotently UPSERTed by `key` on import, so a fresh instance that seeds its own modes and then restores an archive converges rather than colliding — the reason the PK is the natural key.

The module placement follows the existing four-layer split (`backend/book-domain.md`): one `db/` module per table (`db/assistant_modes.py`, `db/sub_agents.py`, `db/mode_tools.py`, `db/subagent_tools.py`, `db/mode_subagents.py`), `models/` tables + DTOs, and an admin config service (`services/assistant_config.py`) holding the CRUD and the name-unique / model-pair-invariant checks. The runtime pieces below are the first built slice of the assistant subsystem; exact runtime module boundaries are the planner's to finalise.

## Runtime consumption — the FEAT-020 slice

How the stored configuration becomes one assistant call. Everything here is the assistant runtime, the first slice of it built.

### Mode determination — from the workspace activity

The runtime "current mode" is **not stored on a chat** (a chat is not bound to a subject — `domain-chat.md`); it is derived from the **workspace activity** — which navigator subject / content-pane artifact the author is acting on (`frontend-workspace.md`). The mapping resolves FEAT-013's coarse "chapter mode / codex-entry mode" to FEAT-020's five:

| Workspace subject | FEAT-013 coarse mode | FEAT-020 mode |
|---|---|---|
| Codex entry, `kind = character` | codex-entry mode | `edit-character` |
| Codex entry, `kind = location` | codex-entry mode | `edit-location` |
| Codex entry, `kind = fact` | codex-entry mode | `edit-fact` |
| Chapter in state `open` | chapter mode | `write-chapter` |
| Chapter in state `closing` | chapter mode | `close-chapter` |

`close-chapter` mode is the assistant's behaviour while the owner approves continuity for a chapter in `closing`; that the chapter body is **read-only** in that state (`frontend-workspace.md`) is orthogonal — the mode selects prompt and tools, not write permission. Subjects outside these five (Book state, any list) fall **outside FEAT-020's mode set**; whether and how the assistant runs there is part of the still-deferred assistant subsystem, not decided here.

### System-prompt composition — the named prompts only

When the assistant runs in a mode (US-110.AC-3), the runtime composes the **named** system prompts in this fixed order, each as its own delimited section:

```
1. base prompt      — optional app-level assistant identity (if one exists)
2. mode prompt      — AssistantMode.system_prompt   (admin: how to behave in this activity)
3. book prompt      — Book.system_prompt            (author: this book's voice, FEAT-019 — every chat)
4. chapter prompt   — Chapter.system_prompt         (author: narrows the book's, FEAT-019 — chapter modes only)
```

**An empty or absent prompt contributes nothing** — no section, no separator, no blank block (US-110.AC-4 for the mode prompt; the chapter prompt is optional by FEAT-019). Composition concatenates only the non-empty prompts, in the order above.

**Why this order.** The base establishes ground identity; the **mode** prompt layers the admin's operational "what activity is this and how to behave in it"; the **book** and **chapter** prompts are the author's standing *voice* and belong closest to the material. The chapter prompt must follow the book prompt because FEAT-019 defines it as **narrowing rather than replacing** the book's — a narrowing instruction has to read *after* the thing it narrows. Putting the admin's operational instruction first and the author's voice last (most-general → most-specific, admin → author) keeps each contributor's material contiguous and the most-specific layer nearest the task. The mode prompt is orthogonal to the book/chapter prompts (admin authorship vs author authorship, FEAT-020 vs FEAT-019), so the two never contend for the same slot.

Only the composition of these named prompts is in scope. Assembling retrieved book/chapter/codex **content** into context (US-057, UC-085/086/078) stays deferred — see `domain-chat.md` and `retrieval.md`.

### Tool gating

A mode's selected tool set **is the allowlist** (US-111). At runtime: read the mode's `mode_tool` rows → resolve each `tool_name` against `TOOL_REGISTRY` → build the OpenAI tool definitions with `pydantic_to_openai_tool(name, description, args_schema)` and a name→callable map. A tool **not** selected for the mode is simply never built into the definitions, so it is unavailable to the model in that mode (US-111.AC-2). A selected name with no registry entry is skipped and logged (the catalogue is source of truth).

### The tool / function-call protocol — built on `chat_with_tools`

The protocol is the `llm` client's built-in agent loop:

```
chat_with_tools(
    messages,
    tools_definitions = [pydantic_to_openai_tool(t.name, t.description, t.args_schema) for t in allowed],
    tools            = {t.name: t.callable for t in allowed},   # + synthetic delegation tools, below
    system           = composed_prompt,
    max_loops        = <bounded>,
) -> str    # final assistant text only
```

`chat_with_tools` **owns the loop**: it dispatches to the callables (sync or async), iterates up to `max_loops`, and returns the **final assistant string only** — it surfaces no per-tool-call events.

**The seam, recorded with reasoning.** Choosing the built-in loop **now** is deliberate. It satisfies everything FEAT-020 needs — prompt composition, tool gating and delegation all resolve *before and around* the call — and it avoids pulling forward the deferred **SSE shared-canvas write protocol** (UC-055/076/077), which needs to surface intermediate writes *as they generate* and will likely require **driving the loop manually** (calling `chat` in a loop, dispatching tools and emitting SSE per step) precisely because `chat_with_tools` gives no per-step visibility. Nothing outside the assistant runtime binds to `chat_with_tools`: the config model, tool registry, gating and delegation are all independent of it, so when the SSE session arrives the loop is a **replaceable interior**, swappable for a manual driver without touching any of them. This is the concrete narrowing of `domain-chat.md`'s previously-deferred "tool / function-call protocol".

### Sub-agent delegation — allowed sub-agents as synthetic tools

A mode's allowed sub-agents (`mode_subagent` rows, **excluding `disabled` ones**) are exposed to the parent assistant as **synthetic tools** — one per sub-agent, alongside the real `TOOL_REGISTRY` tools in the same `tools` / `tools_definitions` maps. Invoking a synthetic tool runs a **nested, bounded `chat_with_tools`** for that sub-agent, with:

- the sub-agent's own `system_prompt` as `system` — **its own prompt alone**, not the mode/book/chapter composition; a sub-agent is a self-contained admin-configured worker (whether book/chapter voice should thread into delegated work is a later assistant-session question, not decided here);
- its own tool allowlist (`subagent_tool` rows → `TOOL_REGISTRY`) — **tools only, never other sub-agents**, so the nested loop cannot itself delegate;
- its own model (assigned, or inherit-main — below);
- a `max_loops` bound.

The nested call's returned string becomes the synthetic tool's result to the parent. **Only sub-agents in the mode's set are invokable** (US-112.AC-3), and a disabled one is invokable through neither its (deleted) links nor a stale reference — the runtime filters on `disabled` as well. This is the concrete form of UC-088's "sub-agent scoped check", and the one-level-deep bound is structural (no `subagent_subagent` table) plus the per-call `max_loops`.

### Model resolution

For a sub-agent with a set `(llm_server_id, model_name)`, the runtime constructs/resolves a client:

```
get_llm_client(
    server_type = <mapped from LlmServer.backend_type>,   # ollama | openai | llamaswap
    base_url    = LlmServer.base_url,
    model       = model_name,
    bearer_token= resolve_env_ref(LlmServer.api_key),      # services/secrets.py, $ENV at use time
)
```

For a sub-agent with a **null** assignment, the runtime uses the **main chat's own client/model** (US-113.AC-6). The **main chat's** model selection stays the open FEAT-013 `_TBD:` — FEAT-020 resolves the model question for sub-agents only.

**Reuse the existing construction path.** `services/llm_servers.py` already builds `llm` clients (today only for `list_models()`), including the `LlmServer.backend_type` → `server_type` mapping (stored `"llama-swap"` → client `"llamaswap"`). Delegation should call through that existing path rather than re-deriving the mapping, so the translation lives in one place.

**Planner note — construct-per-delegation vs. cache.** The model is **bound at client construction**; switching model means a new client (harvested). Two viable strategies: construct a client per delegation, or cache clients keyed by `(llm_server_id, model_name)` for the life of a request/process. Both are correct; the choice is a performance trade-off (client construction cost vs. cache bookkeeping) and is left to the planner. The config model and resolution rule above are the same either way.

## Authorization

**Admin-only, system-global (ACT-001).** All of FEAT-020 sits behind the existing `require_role(admin)` dependency, the same configuration class as LLM servers (FEAT-004) — it is **not** a book-scoped capability and never enters the `BookAccess` matrix. Authors never view or configure it. This does **not** breach FEAT-011's "admin never participates in a book," because it is **global assistant configuration, not book participation** — the same admin-interface-only pattern as FEAT-011's moderation view. See `authorization.md` → "Global assistant configuration (FEAT-020)".

## Out of scope — still deferred

Designed here: the FEAT-020 config model and the runtime slice above. **Still deferred** (see `domain-chat.md` for the full assistant boundary):

- **Context / content assembly** — building, ordering, ranking and truncating retrieved book/chapter/codex material into the prompt (US-057, UC-085/086/078 internals). Only the composition of *named system prompts* is designed here; retrieval ends at "here are the relevant chunks" (`retrieval.md`).
- **The SSE shared-canvas write protocol** (UC-055/076/077) — and the manual loop it will likely require; see the seam above.
- **Web search wiring** (UC-087).
- **The main-chat model selection `_TBD:`** — FEAT-020 resolves it for sub-agents only (FEAT-013 records the remaining open question).
- **Token budgeting and truncation.**
- **`_TBD:` whether a mode's tools default on or off** before the admin configures it (product-open on FEAT-020) — a seeding/default question, not resolved here.
