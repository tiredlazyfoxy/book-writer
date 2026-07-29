# Assistant Runtime — how configuration and a request become one assistant call

**Realizes:** FEAT-013 (the built slice) — UC-081 (the turn-execution half only; the stored-chat entities and their management are `domain-chat.md`'s), UC-087, UC-088; FEAT-018 (the assistant-side canvas write only) — UC-076, UC-077; US-086, US-087

This document realizes the **FEAT-013 runtime**; the **FEAT-020 configuration requirements it consumes (UC-095, UC-096, UC-097, US-110..US-114) are realized by `assistant-config.md`** — the runtime reads that stored configuration but does not implement the admin surface.

How the stored FEAT-020 configuration plus the author's request become **one live assistant call**: which mode the turn runs in, what system prompt it carries, which tools it may call, how the tool loop is driven, how a sub-agent is delegated to, which model answers, and what comes back over the wire.

This is the **built slice of the otherwise-deferred FEAT-013 assistant subsystem**. `assistant-config.md` holds the configuration model it reads. `domain-chat.md` holds the `Chat` / `ChatMessage` entities and the boundary of what remains deferred.

> **Provenance.** This document was carved out of `assistant-config.md` on 2026-07-29, when features `011.chat-panel` and `013.codex` built the runtime out and the combined file outgrew the folder's ~400-line rule. The configuration half stayed there; everything here moved, and was extended with what those two features shipped.

Index and cross-cutting conventions: `domain-model.md`. Related: `assistant-config.md`, `domain-chat.md`, `frontend-workspace.md` (the activity that determines the mode), `frontend-work-drafts.md` (the canvas target registry and the restore buffer), `retrieval.md` (what the codex search tool queries), `backend/persistence.md` (settings, secrets, the `$ENV` indirection), `backend/features.md` (the shipped route inventory).

## The as-built modules

| Module | Owns |
|---|---|
| `services/assistant_runtime.py` | mode determination, mode prompt lookup, tool allowlist resolution |
| `services/subagent_delegation.py` | synthetic delegation tools and the nested loop |
| `services/codex_tools.py` | the first mode-gated tools, including the shared-canvas write |
| `services/prompt_composition.py` | the pure prompt-composition function |
| `services/chat_turn.py` | **the single call site** that composes them all |

**The runtime reads the five FEAT-020 `db/` modules directly and never touches `services/assistant_config.py`.** It therefore carries **no dependency on feature `012.assistant-config-editor`** — the config half and the runtime half were built independently against the same tables. This is deliberate and worth keeping: the admin editor's validation and error taxonomy are a write-edge concern (`assistant-config.md`), and importing them into a read path would couple a turn to CRUD rules it does not need.

## Mode determination — from the workspace activity

The runtime "current mode" is **not stored on a chat** (a chat is not bound to a subject — `domain-chat.md`); it is derived from the **workspace activity** — which navigator subject / content-pane artifact the author is acting on (`frontend-workspace.md`). The mapping resolves FEAT-013's coarse "chapter mode / codex-entry mode" to FEAT-020's five:

| Workspace subject | FEAT-013 coarse mode | FEAT-020 mode |
|---|---|---|
| Codex entry, `kind = character` | codex-entry mode | `edit-character` |
| Codex entry, `kind = location` | codex-entry mode | `edit-location` |
| Codex entry, `kind = fact` | codex-entry mode | `edit-fact` |
| Chapter in state `open` | chapter mode | `write-chapter` |
| Chapter in state `closing` | chapter mode | `close-chapter` |

`close-chapter` mode is the assistant's behaviour while the owner approves continuity for a chapter in `closing`; that the chapter body is **read-only** in that state (`frontend-workspace.md`) is orthogonal — the mode selects prompt and tools, not write permission. Subjects outside these five (Book state, any list, the chats view) fall **outside FEAT-020's mode set**; what the assistant may do there is answered under "Tool gating" below, not left open.

### The wire shape it derives from

The workspace activity reaches the backend as **three optional fields on `TurnRequest`**: `subject_kind`, `subject_id` and `codex_kind`. Two rules are load-bearing:

**Why `codex_kind` exists at all.** UC-076 opens a *blank* codex entry with no row behind it, so the kind cannot be read off a row — and without the request carrying it, mode determination would be impossible for exactly the case FEAT-018 is about. For an **existing** entry the row's `kind` wins and the request's `codex_kind` is ignored; the client cannot talk the runtime into a different mode for a row that already says what it is.

**A `subject_id` naming an entry in another book resolves to no subject**, not to that entry's mode. Mode determination reads a row, so it would otherwise be a cross-book read dressed as a routing hint. No subject means no mode, which means the base tool set (below) — a safe, non-leaking fallback.

## System-prompt composition

When the assistant runs (US-110.AC-3), the runtime composes the **named** system prompts in this fixed order, each as its own delimited section:

```
1. base prompt      — app-level assistant identity (a module constant)
2. mode prompt      — AssistantMode.system_prompt      (admin: how to behave in this activity)
3. author prompt    — BookAuthorPrompt.system_prompt   (the author running the turn; per-author, not per-book)
4. chapter prompt   — Chapter.system_prompt            (chapter modes only — see the caveat)
```

The section label the runtime renders for layer 3 is **`AUTHOR`**. The parameter was **renamed, not merely repointed**: a parameter named `book` carrying an author's prompt is a trap for the next reader, and the rename is the cheap way to stop that reading before it starts.

**An empty or absent prompt contributes nothing** — no section, no separator, no blank block (US-110.AC-4 for the mode prompt; the chapter prompt is optional by FEAT-019). Composition concatenates only the non-empty layers, in the order above.

Realized as a **pure function** in `backend/app/services/prompt_composition.py` taking four optional layers, with the base layer as a module constant. Pure because composition has no reason to touch a session or a clock, and because the ordering and skip rules are exactly the kind of thing that should be testable without a database.

**Why this order.** The base establishes ground identity; the **mode** prompt layers the admin's operational "what activity is this and how to behave in it"; the **author** and **chapter** prompts belong closest to the material. Most-general → most-specific, admin → author, the most-specific layer nearest the task. The mode prompt is orthogonal to the author and chapter prompts (admin authorship vs author authorship, FEAT-020 vs FEAT-019), so the two never contend for the same slot.

> The earlier justification — that the chapter prompt must follow the book prompt because FEAT-019 defines it as *narrowing* the book's — **no longer holds and has been removed.** There is no book-wide layer left for it to narrow. The ordering survives on the argument above alone.

**Layer 4 caveat.** `Chapter.system_prompt` now has nothing to append to. What a chapter prompt *narrows* is an **open question**, and it is **`014.chapter-skeleton`'s to answer once `/product-spec` has rewritten FEAT-019**. No answer is invented here. See `domain-chapter.md`.

**How the runtime obtains layer 3.** `services/chat_turn.py` reads the `(book_id, author_id)` row through the `db/` module **directly** (`services → db`, the enforced direction), using **the chat's own author** — the same identity `services/chats.py`'s ownership guard scopes every chat read and write to. **No `BookAccess` is built for this**, and the reason matters: the turn is already scoped to the chat's author by construction, so a second access resolution would re-derive an identity that cannot differ. "Whose prompt?" is now a real question with a non-obvious answer, and this is the answer every future runtime slice must reuse.

**Decision history.** At feature `011.chat-panel` the layers were `base / mode / book / chapter`, and only **base and book** were ever non-empty — the mode was always null (no mode-bearing subject existed yet) and `Chapter.system_prompt` had no chapter subject to come from. Feature `021.per-author-system-prompt` replaced layer 3 `BOOK` with `AUTHOR`. That is history, not current state.

Only the composition of these named prompts is in scope here. Assembling retrieved book/chapter/codex **content** into context (US-057, UC-085/086/078) stays deferred — see "Out of scope" and `retrieval.md`.

## Tool gating

The settled rule is **three cases, not two**:

1. **A mode-bearing subject** gets **exactly its `mode_tool` rows.** Zero rows is an **empty allowlist**, not the whole registry (`assistant-config.md` carries the reasoning). A tool not selected for the mode is never built into the definitions, so it is unavailable to the model in that mode (US-111.AC-2).
2. **A subject with no mode** — book state, any list, the chats view, or no subject at all — gets a code-defined **`BASE_TOOL_NAMES`**, holding `web_search` as shipped.
3. `services/tools.py:resolve_tools`'s **`None ⇒ whole registry` branch is no longer reached by the turn.** Feature `011.chat-panel` opened that seam; feature `013.codex` closed it.

**Case 2 is the load-bearing part, and it was a new decision made during `013.codex`'s planning.** Without a base allowlist, wiring real gating would have **silently stripped web search from the chats view feature `011.chat-panel` had just shipped** — a null mode would then have meant "no tools". A capability disappearing as a side effect of tightening a different rule is the failure mode this case exists to prevent.

**Mechanics.** Read the mode's `mode_tool` rows → resolve each `tool_name` against `TOOL_REGISTRY` → build the OpenAI tool definitions with `pydantic_to_openai_tool(name, description, args_schema)` and a name→callable map (context-bearing tools bound from the turn's `ToolContext` — `assistant-config.md`). A selected name with **no registry entry is skipped and logged**: the code catalogue is the source of truth and a selection is only an allow-mark. Allowlist resolution deliberately does *not* filter against the registry itself, so the skip-and-log rule lives in exactly one place.

**Decision history, two lines.** Feature `011.chat-panel` shipped an interim rule where **a null mode allowed the whole `TOOL_REGISTRY`**, because no mode-bearing subject existed yet — a deliberate temporary widening of an allowlist, recorded as a seam rather than discovered later as a hole. Feature `012.assistant-config-editor` explicitly left the seam in place and named `013.codex` as its owner; `013.codex` closed it as above.

## The tool / function-call protocol — built on `chat_with_tools`

The protocol is the `llm` client's built-in agent loop:

```
chat_with_tools(
    messages,
    tools_definitions = [pydantic_to_openai_tool(t.name, t.description, t.args_schema) for t in allowed],
    tools            = {t.name: t.callable for t in allowed},   # + synthetic delegation tools, below
    system           = composed_prompt,
    max_loops        = MAX_LOOPS,
) -> str    # final assistant text only
```

`chat_with_tools` **owns the loop**: it dispatches to the callables (sync or async), iterates up to `max_loops`, and returns the **final assistant string only** — it surfaces no per-tool-call events. `MAX_LOOPS` is a module constant in `services/chat_turn.py`, **4** as shipped.

**The seam, recorded with reasoning.** Choosing the built-in loop was deliberate. It satisfies everything the FEAT-020 runtime needs — prompt composition, tool gating and delegation all resolve *before and around* the call — and it avoided pulling forward a manual driver (calling `chat` in a loop, dispatching tools and emitting SSE per step) before anything needed per-step visibility.

**The seam is realized as designed** (`011.chat-panel`): `chat_with_tools` is called from **one place**, `services/chat_turn.py`, and the config model, registry, gating and composition are all independent of it. Swapping in a manual driver is therefore an **interior change**.

**The shared-canvas write did not force the swap** (`013.codex`), and the reason it did not is the design's load-bearing part. This document previously predicted that the canvas protocol would require driving the loop manually. It did not: the canvas tool **emits its frame onto the same `asyncio.Queue` `run_turn` already pumps** for `thinking` and `delta`, so a tool can reach the wire without the loop surfacing anything per-step.

**Accepted consequence: the draft arrives whole, not streamed.** `chat_with_tools` hands a tool its arguments only after the model has finished emitting them, so the canvas frame carries a complete draft rather than growing token by token. **Token-level canvas streaming remains the later manual-loop swap**, and the seam is still replaceable.

## Sub-agent delegation — allowed sub-agents as synthetic tools

A mode's allowed sub-agents (`mode_subagent` rows, **excluding `disabled` ones**) are exposed to the parent assistant as **synthetic tools** — one per sub-agent, alongside the real `TOOL_REGISTRY` tools in the same `tools` / `tools_definitions` maps. Invoking a synthetic tool runs a **nested, bounded `chat_with_tools`** for that sub-agent, with:

- the sub-agent's own `system_prompt` as `system` — **its own prompt alone**, not the mode/author/chapter composition; a sub-agent is a self-contained admin-configured worker (whether the author's voice should thread into delegated work is a later question, not decided here);
- its own tool allowlist (`subagent_tool` rows → `TOOL_REGISTRY`) — **tools only, never other sub-agents**, so the nested loop cannot itself delegate;
- its own model (assigned, or inherit-parent — below);
- its **own `max_loops` constant, separate from `chat_turn.MAX_LOOPS`**, so tightening the parent's bound does not silently retune delegation.

The nested call's returned string becomes the synthetic tool's result to the parent. **Only sub-agents in the mode's set are invokable** (US-112.AC-3), and a disabled one is invokable through neither its (deleted) links nor a stale reference — the runtime filters on `disabled` as well. This is the concrete form of UC-088's "sub-agent scoped check", and the one-level-deep bound is structural (no `subagent_subagent` table) plus the per-call `max_loops`.

**As built** (`013.codex`, `services/subagent_delegation.py`):

- Synthetic tools are derived **one per non-disabled sub-agent of the mode**, with names **derived and sanitised from `SubAgent.name`, not stored**. Nothing persists a tool name for a sub-agent, so renaming one cannot leave a stale identifier behind.
- A **collision guard** protects the derived names — against real `TOOL_REGISTRY` names and against each other. A colliding name is **skipped and logged**, and **the real tool always wins**: a registry entry is code the system depends on, while a synthetic name is a derived convenience.
- The nested call receives the sub-agent's `system_prompt` alone, its `subagent_tool` allowlist only, and its own `max_loops`.
- Every delegation failure — a missing or inactive assigned server, an unresolvable credential, a transport or LLM error, a raising nested tool, an exhausted nested loop — comes back to the parent as a **short error string**, never an exception: a raising tool would abort the whole turn.

**Clients are constructed per delegation, not cached.** This closes an open note the design previously left to the planner. `LLMClient` must be entered as `async with` and has **no standalone `close()`**, so a cache would have to own client lifetimes across a whole turn — real bookkeeping, for a call already bounded by `max_loops`. The construction cost is not worth the lifetime problem it would create.

## Model resolution

For a sub-agent with a set `(llm_server_id, model_name)`, the runtime constructs a client:

```
get_llm_client(
    server_type = <mapped from LlmServer.backend_type>,   # ollama | openai | llamaswap
    base_url    = LlmServer.base_url,
    model       = model_name,
    bearer_token= resolve_env_ref(LlmServer.api_key),      # services/secrets.py, $ENV at use time
)
```

For a sub-agent with a **null** assignment, the runtime uses the **parent turn's own server, resolved key and model** (US-113.AC-6).

**The main chat's model is chosen by the author, per chat.** It is stored as a `(llm_server_id, model_name)` pair on `Chat` and picked from the active servers' `enabled_models` (`domain-chat.md`). This was previously recorded here as an open FEAT-013 `_TBD:`; it was **resolved by a user decision during `011.chat-panel`'s planning**, not by inference. `docs/product/` FEAT-013 still records it as open — that is **`/product-spec`'s to close**, a follow-up, not an architecture edit.

**A set-but-unusable assignment is a delegation failure, not an inherit-main fallback.** The two happy cases above say nothing about a sub-agent whose assigned `LlmServer` has been deleted, deactivated, or carries an unresolvable `$ENV` key. As built, the delegation **does not silently fall back to the parent's model** — it returns a short error string to the parent loop. The reasoning: a sub-agent explicitly assigned a model **is not the same worker when run on someone else's**, so quietly substituting one would produce output the admin did not configure and could not detect.

### Client construction — one path, and one known leak

`services/llm_servers.py` grew a **model-bound** construction path beside the pre-existing `_create_client` (which hardcodes `model=""` for `list_models()` and is a documented test seam); both share one `backend_type` → `server_type` branch, so the mapping (`"llama-swap"` → `"llamaswap"`) lives in exactly one place. Clients are entered as **async context managers**, because `LLMClient` exposes `__aenter__` / `__aexit__` and **no standalone `close()`**.

**Known defect, recorded once rather than rediscovered:** the pre-existing `_create_client` / `list_models` path **still leaks its `aiohttp.ClientSession`**. It was deliberately out of scope for `011.chat-panel` and is **still open** — worth its own fix.

### Two `llm-client` v0.1.4 constraints that shape every sampling decision

Verified during `011.chat-panel`. These are dependency facts that silently change behaviour and would otherwise be re-discovered by whoever next touches sampling.

- **(a) Options are filtered against a hardcoded allowlist** — `temperature`, `top_p`, `max_tokens`, `presence_penalty`, `frequency_penalty`, `seed`, `enable_thinking`, `reasoning_effort`. Consequently **`top_k`, `repeat_penalty` and `min_p` are persisted by feature `011.chat-panel` but cannot reach either backend.** They go live with **no schema and no API change** if the dependency is patched — which is why they are stored anyway.
- **(b) The allowlist always injects** `temperature=1.0` / `top_p=1.0` / `presence_penalty=0.0` / `frequency_penalty=0.0`. So **"unset means server default" is not expressible**, and there is **no `extra_body` escape hatch**.
- **Sampling emission is backend-conditional:** params are sent only to a `llama-swap` server; an `openai` server gets none.

## The SSE frame vocabulary

Five named frames as shipped: **`thinking`, `delta`, `done`, `error`** (`011.chat-panel`) and **`canvas`** (`013.codex`). The first four were chosen to match what the frontend's `api/sse.ts` already special-cases, so the first streaming surface in the repo needed no transport work.

`canvas` carries `CanvasFrame(subject_kind, subject_id, field, text)`. Two properties make it safe to add:

- the emitting tool **touches no database** (see below), so a frame can never be mistaken for a write;
- `routes/chats.py`'s serializer is **generic over the event name** — `event: <name>` / `data: <payload JSON>` — so a new frame needed **no route change** at all.

`field` exists because a character entry has both a `name` and a `body`, and the assistant may draft either.

**This vocabulary is deliberately narrow — a floor, not the design.** Feature `011.chat-panel` recorded its four frames as exactly that; feature `013.codex` is the first widening. The shared-canvas write protocol for **chapters** (UC-055) and token-level streaming are still undesigned. A shipped frame set tends to be read as the protocol; it is not.

## The shared-canvas write for codex, as built

A **mode-gated `write_codex_draft` tool** validates editability **server-side**, emits **one `canvas` frame**, and **persists nothing**.

**There is no chat → codex write path, by construction.** US-086.AC-2 / US-087.AC-2 / US-088.AC-2 hold **structurally, not by a check**: no code path exists from a chat turn to the `codex_entries` table. The canvas tool reads the resolved subject and writes a frame; the only writer is the ordinary codex route the author calls on save (UC-069 / UC-070, `domain-codex.md`). "Nothing persists until saved" is normally an assertion about a check; here it is a structural property, **and that is worth more than the check would be** — a check can be bypassed by a later code path, an absent dependency cannot.

The frontend half — the module-level canvas target registry, and the restore buffer as the fallback when no target is registered — is **`frontend-work-drafts.md`**'s; it is not duplicated here.

**The editability rule now has two implementations, deliberately.** `services/codex_tools.py:_refuse_write` is the assistant's **server-side mirror** of `frontend/src/work/subject.ts:checkWritePermission`, and **its refusals are tool strings, not HTTP statuses**. The assistant's canvas write is refused with a message **the model reads**; the author's save is refused with the 403 / 400 / 409 taxonomy `services/codex.py` owns. The two speak different languages **by design**: a raising tool would abort the turn, so the assistant's refusal must be something the model can respond to rather than an exception. Both express the same rule — a read-only subject refuses the author and the assistant alike.

## Out of scope — still deferred

Built here: the FEAT-020 runtime and the FEAT-013 slice above. **Still deferred** (see `domain-chat.md` for the full assistant boundary):

- **Context / content assembly** — building, ordering, ranking and truncating retrieved book/chapter/codex material into the prompt (US-057, UC-085/086/078 internals). Only the *named system prompts* are composed; retrieval ends at "here are the relevant chunks" (`retrieval.md`).
- **The shared-canvas write protocol for chapters** (UC-055) — the codex half shipped; the chapter half has not.
- **Token-level canvas streaming** — the manual-loop swap described under the protocol seam, still deferred.
- **Token budgeting and truncation.**
- **UC-078's relevance criterion** — an open product `_TBD:` (challenge C27). `013.codex` shipped **pull-only** codex search with a result limit and **no score threshold**, deliberately, so the product question is not closed by a design choice.

**No longer deferred:** web search (UC-087) shipped with `011.chat-panel` — see `backend/persistence.md` for its two settings and the decision to call the Google Custom Search JSON API through **direct `httpx`, not an MCP client** (the product's "MCP" wording is generic; tools here are plain backend functions).
