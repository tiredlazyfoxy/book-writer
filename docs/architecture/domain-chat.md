# Domain — Chat and ChatMessage (entities only)

**Realizes:** FEAT-013 **entities only** — UC-053, UC-081, UC-082; US-061, US-095, US-096. **Not** the assistant subsystem.

Part of the book-domain model. **Index and cross-cutting conventions: `domain-model.md`.** Related: `frontend-workspace.md` (the chat pane's slot), `retrieval.md` (what the assistant will eventually search).

> **Read this first.** This file is a **map entry, not a subsystem design.** The two tables below exist so that the schema is drawn whole and does not need retrofitting at Stage 5. Everything that makes them useful is undesigned. Do not infer behaviour from these fields.

## Chat

| Field | Type / notes |
|---|---|
| `id` | snowflake PK |
| `book_id` | FK → `Book.id` — chats are per book |
| `author_id` | FK → `User.id` — **private to that author**, including from the owner (US-061.AC-1) |
| `title` | display label for the picker |
| `archived` | archived, not destroyed (UC-082); restorable (US-096.AC-2) |
| `created_at` / `modified_at` | timestamps |

## ChatMessage

| Field | Type / notes |
|---|---|
| `id` | snowflake PK |
| `chat_id` | FK → `Chat.id` |
| `role` | who spoke |
| `content` | the message body |
| `created_at` | timestamp |

## The two structural facts worth stating

**A chat is not bound to a chapter, codex entry or content-pane subject.** The pairing is spatial, not a data binding (UC-053, UC-083). That is why there is **no subject FK** here — a deliberate absence, not an omission. `frontend-workspace.md` carries the same independence through the working page, and it carries it **by persistence rather than by URL shape**: the content-pane subject is a nested path route, while the active chat is **not in the URL at all** — the chat pane re-resolves it from a stored per-book pointer, falling back to the most recent chat by timestamp. Because these rows are server-persisted, neither side depends on the other staying mounted.

**Privacy is an ownership rule on `author_id`, not a permission row.** No role reaches another user's chat — not a co-author, not the book's owner, not an admin. Only the *saved output* of a chat is shared (US-061.AC-2), and that output is an ordinary `ChapterChange` (`domain-chapter.md`) or `CodexEntry` (`domain-codex.md`) attributed to the author, carrying nothing about how it was produced.

**Archived, not destroyed**, consistent with books, users and codex entries.

## Out of scope — the whole assistant subsystem

None of the following is designed anywhere in `docs/architecture/`, and this pass deliberately does not attempt it. It gets its own design session **before Stage 5**:

- **Context assembly** — how the mode-dependent baseline (US-057) is built, ordered and truncated.
- **The tool / function-call protocol** — how the assistant pulls another chapter (UC-085), searches by meaning (UC-086), reaches the codex (UC-078) or consults the web (UC-087).
- **The agent loop**, and **sub-agent scoped checks** (UC-088).
- **The SSE event protocol** for shared-canvas writes — how a draft appears in the content pane as it is generated (UC-055, UC-076, UC-077).
- **Prompt design, token budgets, and model selection.** Product records the model question as an open `_TBD:` that "may resolve as architecture's"; it is not resolved here.
- **Web-search wiring** (UC-087).
- **UC-078's relevance criterion** — an open product `_TBD:` (challenge C27) with no measurable criterion offered. `retrieval.md` deliberately stops short of choosing a threshold.

What *is* settled, and what the subsystem will have to build on: the entities above; the book- and chapter-level `system_prompt` fields (`domain-book.md`, `domain-chapter.md`) that shape every chat; the save path a shared-canvas write lands on (`domain-chapter.md` → "The one write path"); and the retrieval interface it will query (`retrieval.md`).
