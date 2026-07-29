# Backend — Book-Domain Impact

**Realizes:** FEAT-006..018 (backend-side consequences only)

Part of the backend architecture — see `../backend.md` for the index.

The entity definitions, their reasoning and their lifecycles live in `domain-model.md` (the index) and its area files — `domain-book.md`, `domain-chapter.md`, `domain-continuity.md`, `domain-codex.md`, `domain-chat.md`. This section records what the design costs *this* document's structures.

## Module map

The existing four-layer split absorbs the domain without change — one `db/` module per entity, one service per aggregate, routes under `/api`. The table below is **as-shipped through features 008–013 and 021** (2026-07-25..29); modules that are still designed-only are marked. Names come from those features' `## Files Changed` records, not from a projection.

| Layer | Modules |
|---|---|
| `models/` | **shipped:** `book.py`, `book_member.py`, `book_author_prompt.py`, `chapter.py`, `chapter_change.py`, `chapter_text_revision.py`, `chapter_notes.py`, `flag.py`, `codex_entry.py`, `codex_entry_version.py`, `chat.py` (declares **both** `Chat` and `ChatMessage`), plus the five FEAT-020 config tables `assistant_mode.py`, `sub_agent.py`, `mode_tool.py`, `subagent_tool.py`, `mode_subagent.py` |
| `models/schemas/` | **shipped:** `books.py`, `book_author_prompts.py`, `chats.py`, `codex.py`, `tools.py`, `assistant_config.py` |
| `db/` | **shipped:** one session-free module per table — `books.py`, `book_members.py`, `book_author_prompts.py`, `chapters.py`, `chapter_changes.py`, `chapter_text_revisions.py`, `chapter_note_changesets.py`, `flags.py`, `codex_entries.py`, `codex_entry_versions.py`, `chats.py`, `chat_messages.py`, `assistant_modes.py`, `sub_agents.py`, `mode_tools.py`, `subagent_tools.py`, `mode_subagents.py` — same shape as `db/users.py` / `db/llm_servers.py`. Cross-cutting: `vector.py` (widened for the sidecar, feature 013) and `import_export_queries.py`. |
| `services/` | **shipped:** `authz.py` (the capability table), `books.py` (lifecycle, membership, visibility), `book_author_prompts.py` (the per-author prompt), `chats.py` (chat CRUD + the row-ownership rule), `chat_turn.py` (the streaming turn), `codex.py` (codex CRUD, versions, collaboration mode), `codex_index.py` (incremental vector maintenance), `embedding.py` (text → vectors), `assistant_config.py` (the FEAT-020 admin editor), plus the assistant-runtime trio `assistant_runtime.py`, `subagent_delegation.py`, `codex_tools.py` and the supporting `tools.py` / `web_search.py` / `prompt_composition.py`. **Not yet built:** chapters (skeleton, state machine, the merge path), continuity, flags. |
| `routes/` | **shipped:** `books.py`, `book_author_prompts.py`, `chats.py`, `codex.py`, `admin/assistant_config.py`. HTTP only, under `/api`; the book-access dependency resolves a typed `BookAccess`, the service decides the capability. |

Three cross-cutting additions worth naming because they are shared rather than per-entity:

- **`services/authz.py`** — one `require(access, capability)` entry point so the capability × role matrix has a single implementation. Shipped by feature `009.books`. See `authorization.md` → "Enforcement".
- **`services/embedding.py`** — the single point where text becomes vectors. Shipped by feature `013.codex`. See `retrieval.md`.
- **The assistant runtime** (`services/assistant_runtime.py`, `services/subagent_delegation.py`, `services/codex_tools.py`, composed by `services/chat_turn.py`) — shipped across features `011.chat-panel` and `013.codex`. It reads the five FEAT-020 `db/` modules directly and never imports `services/assistant_config.py`. See `assistant-runtime.md` for the runtime and `assistant-config.md` for the config model.

## The book-domain table registry

**As shipped** (features `008.data-domain` and `021.per-author-system-prompt`). `TABLE_REGISTRY` (`services/db_import_export.py`) carries a codec pair per table, appended **in FK dependency (import) order** after the two pre-existing entries. This is the canonical printed order, **19 entries**:

```
users, llm_servers,                       # pre-existing (features 003, 004)
assistant_modes, sub_agents,              # FEAT-020 instance-global config (assistant-config.md)
mode_tools, subagent_tools, mode_subagents,
books, book_members, book_author_prompts,
chapters, chapter_changes, chapter_text_revisions, chapter_note_changesets,
codex_entries, codex_entry_versions,
flags,
chats, chat_messages
```

Feature 008 landed **16** of them in one pass — the five FEAT-020 config pairs plus eleven book-domain pairs — in exactly the order above. Feature 011 added columns to `chats` / `chat_messages` and their codecs but **no table**, so it left the order untouched. Feature 021 added the nineteenth, `book_author_prompts`.

`book_author_prompts` sits **immediately after `book_members`**, and the position is deliberate on two grounds: FK import order requires it (it references `books` and `users`, both already earlier), and keeping the two `(book_id, user_id)` link tables adjacent is where a reader looks for either of them. The new table needed **model registration only** — `init_db()`'s `create_all` is additive, so `db/engine.py`'s ADDITIVE MIGRATION SEAM stayed `pass`.

The five **`FEAT-020` config tables are instance-global** (the same class as `users` / `llm_servers`), so they append **before `books`** in the global-config block, not inside the book domain — a sub-agent's `to_dict` references an `LlmServer`, and the link tables reference modes and sub-agents. `TOOL_REGISTRY` is **code, not a table** and is not registered or exported (like `VECTOR_SOURCE_REGISTRY`). Full reasoning and the codec obligations are in `assistant-config.md` → "Persistence and registry obligations"; the ordering is repeated here because this file is the canonical home of the registry order.

The rule in the root `CLAUDE.md` is not optional and not deferrable — "update the import/export logic in the **same change** whenever a model is added or altered". Every one of these tables owes its `to_dict` / `from_dict` pair (ids emitted as **strings**, accepted as string-or-legacy-number) and its ordered registry tuple in the change that introduces the model. Feature 008 honoured it per step rather than batching: skipping it would have left an instance whose export silently loses a book.

Order matters because import is a streaming UPSERT with no transactional rollback: a child row arriving before its parent has nothing to attach to.

## Vector registry

`VECTOR_SOURCE_REGISTRY` is **no longer empty** — `CodexEntry` is registered, and chapter text, summaries and notes follow for UC-086.

It arrived in **two steps**, which is worth recording because the intermediate state was shipped and tested:

- **Feature `008.data-domain`** created the `codex_entries` table as an ordinary data class and registered **no** vector source. The registry stayed empty through that whole feature, and 008 carried a guard test asserting codex's *absence* from it.
- **Feature `013.codex`** widened the registry's entry shape and added the single `codex_entry` entry, superseding that guard with its inverse in the same change. The registry now holds exactly one entry.

The widened entry shape and the full pipeline live in `retrieval.md`; "Vector storage" in `persistence.md` carries the sidecar side.

## Stage-4 columns land at Stage 2

**Confirmed as-shipped by feature `008.data-domain`.** The book domain's later-stage **columns are created with their tables**, nullable and unused, rather than added when the behaviour ships: `Chapter.state = closing`, `Chapter.summary_status`, `Book.moderation_reason` / `moderated_by` / `moderated_at`, and the `chapter_note_changesets` table with its `status`. All of them landed nullable and unused exactly as designed — nothing reads them yet.

The reason is the backend's own SQLite constraint, recorded in `features.md` → "Remediation": **`ADD COLUMN` cannot be `NOT NULL` without a default on a populated table**, so a column added later against live book data arrives nullable regardless of what the model declares, and reconciling nullability would need a table rebuild. Landing them now costs a wider `CREATE TABLE` that nothing queries and makes Stage 4 pure behaviour with **no DDL at all**. See `domain-chapter.md` → "Landing the continuity columns early".

## Chapter concurrency — the 409 rule

`Chapter.version` is bumped on every applied change, and a write carrying a stale `base_version` is **refused with 409**, never merged server-side. This is a service-layer rule (the merge is a single transaction: snapshot → apply placement → bump version), and it is what US-041's concurrent-edit warning is built from. Full reasoning, including why a uniform refusal was chosen over a placement-dependent one, is in `domain-chapter.md` → "Concurrency".

## Schema drift — no new code

FEAT-005's consistency report (`db/schema.py` + `services/db_admin.py`) compares the live database against `SQLModel.metadata`. Every table above lands in that metadata by being declared, so **the drift report covers the new tables with no change to the FEAT-005 code at all** — the ok / drift / missing report and the per-table create/sync remediation extend to the book domain for free. This is the payoff of having built drift detection against metadata rather than against a hand-maintained table list.

**Confirmed as-shipped.** Feature `008.data-domain` carried a drift-clean criterion on every one of its nine steps (each step asserts its new tables appear in `SQLModel.metadata` and the consistency report comes back all-`ok`), and **not a line of FEAT-005 code changed**. Feature 021 added the nineteenth table on the same terms.
