# Domain — Chat and ChatMessage (entities only)

**Realizes:** FEAT-013 **entities only** — UC-053, UC-081, UC-082; US-061, US-095, US-096. The runtime that uses these rows is `assistant-runtime.md`.

Part of the book-domain model. **Index and cross-cutting conventions: `domain-model.md`.** Related: `frontend-workspace.md` (the chat pane's slot), `frontend-work-drafts.md` (the restore buffer and the canvas target registry), `retrieval.md` (what the assistant searches), **`assistant-config.md`** (the FEAT-020 configuration model) and **`assistant-runtime.md`** (the runtime that composes prompts, gates tools, drives the tool loop, delegates, and streams frames).

> **Read this first.** This file is a **map entry, not a subsystem design.** The two tables below exist so that the schema is drawn whole and does not need retrofitting at Stage 5.
>
> A substantial part of the assistant is now **built**, not deferred: the FEAT-020 configuration model (`assistant-config.md`) and, in `assistant-runtime.md`, per-chat model selection, web search, the tool / function-call loop, mode-gated tools, sub-agent delegation, and the shared-canvas SSE write protocol **for codex entries**.
>
> **What remains undesigned:** context / content assembly, the shared-canvas protocol for **chapters**, token-level streaming, and token budgeting. Do not infer any of *that* from these fields — go to the two documents above for what exists, and treat the "Still deferred" list below as the boundary.

## Chat

| Field | Type / notes |
|---|---|
| `id` | snowflake PK |
| `book_id` | FK → `Book.id` — chats are per book |
| `author_id` | FK → `User.id` — **private to that author**, including from the owner (US-061.AC-1) |
| `title` | display label for the picker |
| `llm_server_id` | **nullable** FK → `LlmServer.id` — the author's model choice for this chat |
| `model_name` | **nullable** string — the model on that server; **the pair moves together exactly as `SubAgent`'s does** (both null or both set; a half-set state is refused) |
| `sampling_params` | **non-nullable** TEXT holding a JSON object, gated by a Pydantic `ChatSamplingParams` |
| `archived` | archived, not destroyed (UC-082); restorable (US-096.AC-2) |
| `created_at` / `modified_at` | timestamps |

`sampling_params` is JSON-in-TEXT rather than a column per parameter. It is **not** a free dictionary — the Pydantic model gates every read and write. `backend/persistence.md` carries the sanctioning and the reasoning (the param set is expected to be revised, and a JSON column makes a revision a Pydantic edit with no schema migration).

## ChatMessage

| Field | Type / notes |
|---|---|
| `id` | snowflake PK |
| `chat_id` | FK → `Chat.id` |
| `role` | who spoke |
| `content` | the message body |
| `reasoning` | **nullable** — the model's thinking for this message, when the server surfaced any |
| `position` | non-null `int` — the message's order within its chat, an explicit ordinal alongside `created_at` |
| `created_at` | timestamp |

## The structural facts worth stating

**A chat is not bound to a chapter, codex entry or content-pane subject.** The pairing is spatial, not a data binding (UC-053, UC-083). That is why there is **no subject FK** here — a deliberate absence, not an omission. `frontend-workspace.md` carries the same independence through the working page, and it carries it **by persistence rather than by URL shape**: the content-pane subject is a nested path route, while the active chat is **not in the URL at all** — the chat pane re-resolves it from a stored per-book pointer, falling back to the most recent chat by timestamp. Because these rows are server-persisted, neither side depends on the other staying mounted. (What the *runtime* does with the currently-open subject is a per-request field, not a stored binding — `assistant-runtime.md` → "Mode determination".)

**Privacy is an ownership rule on `author_id`, not a permission row.** No role reaches another user's chat — not a co-author, not the book's owner, not an admin. Only the *saved output* of a chat is shared (US-061.AC-2), and that output is an ordinary `ChapterChange` (`domain-chapter.md`) or `CodexEntry` (`domain-codex.md`) attributed to the author, carrying nothing about how it was produced.

*Enforcement, as built (`011.chat-panel`):* a **service-level ownership check in `services/chats.py`**, layered on top of the `book_access` dependency — membership first, then row ownership. A chat belonging to another author answers **404, not 403**, so existence is never confirmed. **No `Capability` member was added and `_CAPABILITY_MATRIX` is unchanged**, because the matrix maps capability → role and has no notion of "author of *this row*". The 404-vs-403 choice is a decision later chat-touching features must copy. (`authorization.md` records the same rule from the permissions side, alongside the second row-ownership rule, `BookAuthorPrompt`.)

**There is no chat → codex write path, by construction.** US-086.AC-2 / US-087.AC-2 / US-088.AC-2 hold **structurally, not by a check**: no code path exists from a chat turn to the `codex_entries` table. The assistant's canvas tool reads the resolved subject and emits a frame; the only writer is the ordinary codex route the author calls on save. `assistant-runtime.md` → "The shared-canvas write for codex, as built" carries the full reasoning.

**Archived, not destroyed**, consistent with books, users and codex entries.

## Assistant subsystem — what is built, what is still deferred

**Built and documented elsewhere.** `assistant-config.md` (FEAT-020) holds the admin configuration model: the fixed **modes**, admin-created **sub-agents**, the code-defined **tool** registry, and the selection/link tables. `assistant-runtime.md` holds the runtime: mode determination from the workspace activity, composition of the named system prompts, tool gating, the tool/function-call protocol (built on the `llm` client's `chat_with_tools` loop), sub-agent delegation as synthetic tools, model resolution, the SSE frame vocabulary, and the shared-canvas write for codex entries. What this file once deferred as "the tool / function-call protocol", "the agent loop", "sub-agent scoped checks (UC-088)", "model selection", "web-search wiring" and "the SSE event protocol *for codex*" is those two documents now.

**Still deferred** — undesigned anywhere, and getting its own session before the remaining assistant work:

- **Context assembly** — how the mode-dependent baseline (US-057) is built, ordered and truncated; how the assistant pulls another chapter (UC-085), searches by meaning (UC-086) or reaches the codex (UC-078) as *content* in the prompt. Feature `011.chat-panel` shipped the chat surface and one working turn; it composed only the **named system prompts**. It did **not** ship US-057 / UC-078 / UC-084 / UC-085 / UC-086. A working chat pane invites the reading that the context model shipped with it — it did not.
- **The shared-canvas write protocol for chapters** (UC-055) — feature `015`'s. The codex half shipped (below); the chapter half has not.
- **Token-level canvas streaming** — the assistant's draft currently arrives whole, not token by token; see `assistant-runtime.md` → the `chat_with_tools` seam.
- **Token budgets.**
- **UC-078's relevance criterion** — an open product `_TBD:` (challenge C27) with no measurable criterion offered. `013.codex` shipped pull-only search with a result limit and **no score threshold**, deliberately, so the product question stays open; `retrieval.md` likewise stops short of choosing one.

**No longer deferred — the shared-canvas write protocol for codex entries** (`013.codex`). The turn carries the content-pane subject; a mode-gated `write_codex_draft` tool validates editability **server-side**, emits **one `canvas` frame**, and **persists nothing**. The frontend applies it through a module-level target registry, with the restore buffer as the fallback when the entry is not open (`frontend-work-drafts.md`). The save path is unchanged UC-069 / UC-070. Moving the whole shared-canvas item out of the deferred list would have been wrong; leaving the codex half in it would have been wrong too.

**Decision history — the main-chat model selection is resolved.** It was carried here as an open product `_TBD:` for the planner to resolve. As of `011.chat-panel` the model is chosen by **the author, per chat**, stored as the `(llm_server_id, model_name)` pair on `Chat` above, and picked from the active servers' `enabled_models`. It was resolved **by a user decision, not by inference**. `docs/product/` FEAT-013 still records it as open — closing that is `/product-spec`'s.

What *is* settled, and what the rest of the subsystem builds on: the entities above; `assistant-config.md`'s configuration model and `assistant-runtime.md`'s runtime; the **per-author** `BookAuthorPrompt.system_prompt` that the composition threads together with the mode prompt (`domain-book.md` — the former **book-wide** layer was replaced by feature `021.per-author-system-prompt`, and `Chapter.system_prompt` consequently has nothing left to append to, an open question for `014.chapter-skeleton` once `/product-spec` rewrites FEAT-019; see `domain-chapter.md`); the save path a shared-canvas write lands on (`domain-chapter.md` → "The one write path", `domain-codex.md` for the codex half); and the retrieval interface it queries (`retrieval.md`).
