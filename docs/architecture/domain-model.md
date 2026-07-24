# Domain Model — the book layer (index)

**Realizes:** FEAT-006, FEAT-007, FEAT-008, FEAT-009, FEAT-010, FEAT-011, FEAT-012, FEAT-014, FEAT-015, FEAT-016, FEAT-017, FEAT-018 in full; **FEAT-013 entities only** (UC-053, UC-055, UC-081, UC-082, UC-092 — not the assistant subsystem). Use cases: UC-021..052, UC-058..060, UC-069..075, UC-079, UC-089, UC-091

The first architectural pass over the book domain: every persistent entity behind `FEAT-006..018`, its lifecycle, the single write path into a chapter, and the concurrency contract.

**This file is the entry point.** It holds the scope, the whole-domain shape, the conventions every entity inherits, and the recorded divergences from `docs/product/`. The entities themselves live in the five `domain-*.md` files listed below. Companion docs outside the model: `authorization.md` (who may do what), `retrieval.md` (how codex entries reach an LLM), `frontend-workspace.md` (the surfaces these entities are edited on).

## Scope of this pass

**In:** the entity map for `FEAT-006..018` drawn **whole** — including tables no stage before 5 or 6 will build — plus chapter concurrency and the write path.

**Out, and deliberately so:** the **internals of the FEAT-013 assistant** (context assembly, the shared-canvas SSE protocol, the main-chat model selection, web search, token budgets). It gets its own design session before Stage 5. The `Chat` / `ChatMessage` **entities** are in the map below; the rest of their subsystem is undesigned. **One slice is now designed** — the FEAT-020 admin config (assistant **modes**, **sub-agents**, the code-defined **tool** registry and their selection tables) **and** the runtime that consumes it (prompt composition, tool gating, the `chat_with_tools` loop, sub-agent delegation, sub-agent model resolution): see **`assistant-config.md`** (2026-07-24). Do not infer the *rest* of the subsystem from those tables — see `domain-chat.md` for the full boundary.

### Why the map is drawn whole when only Stage 2 gets built

There is no Alembic. Schema evolution is hand-written, idempotent, additive `ALTER` run at startup (`backend/persistence.md` → "Relational storage"). That makes the two kinds of change asymmetric:

- **Adding a nullable column later is cheap** — one idempotent `ALTER TABLE … ADD COLUMN`, which is exactly what the existing migration path does well.
- **Adding a table, or changing a key or a relationship later, is expensive** — it means reworking codecs, the `TABLE_REGISTRY` order, and any code that already reads around the missing table.

So the tables and their keys are settled now, while the field lists of the later-stage tables stay open to additive refinement. Drawing a table early costs a `CREATE TABLE` that nothing queries; retrofitting one costs a migration plus a rewrite of everything built on its absence.

This asymmetry is also what decided which open questions got answered in this pass. Anything that would have cost a **table or a key** was settled now; anything that is an **additive nullable column** could safely have waited — and the 2026-07-24 review chose to land those early anyway (see "Recorded gaps"), so that later stages are pure behaviour. What remains open is behavioural, not structural.

## The entity map

```
User ──owns──────────► Book ◄──────── BookMember ──► User
                        │  ▲
                        │  └── active_notes (materialised free text)
                        │
        ┌───────────────┼────────────────┬──────────────┬───────────┐
        ▼               ▼                ▼              ▼           ▼
     Chapter        CodexEntry          Flag           Chat      (clone: a
        │               │                                │        new Book,
        ├─ ChapterChange│                                │        no link)
        ├─ ChapterTextRevision                           │
        └─ ChapterNoteChangeset                          │
                        └─ CodexEntryVersion             └─ ChatMessage
```

The book-rooted entities above are not the whole schema: a small **instance-global / admin-config** cluster hangs off the admin layer (like `User` and `LlmServer`), **not** off any `Book`. The FEAT-020 assistant configuration lives here:

```
LlmServer ◄──(nullable model assignment)── SubAgent
                                             │   │
                                subagent_tool┘   └mode_subagent── AssistantMode (seeded, keyed)
                                     │                                  │
                                     ▼                                  ▼
                            TOOL_REGISTRY  ◄──────── mode_tool ─────────┘
                          (code, not a row; referenced by string name)
```

| Entity | Owns | Defined in | First needed | Vector-backed |
|---|---|---|---|---|
| `Book` | the book and its book-wide settings | `domain-book.md` | Stage 2 | no |
| `BookMember` | co-author membership | `domain-book.md` | Stage 2 | no |
| `Chapter` | one chapter, one main body | `domain-chapter.md` | Stage 2 | later (UC-086) |
| `ChapterChange` | every write into a chapter body | `domain-chapter.md` | Stage 2 | no |
| `ChapterTextRevision` | pre-apply body snapshots | `domain-chapter.md` | Stage 3 | no |
| `ChapterNoteChangeset` | a chapter's note delta | `domain-continuity.md` | Stage 4 *(table at Stage 2)* | later (UC-086) |
| `Flag` | chapter annotation ("warning") | `domain-continuity.md` | Stage 4 | no |
| `CodexEntry` | character / location / fact | `domain-codex.md` | Stage 2 | **yes — first** |
| `CodexEntryVersion` | entry edit history | `domain-codex.md` | Stage 5 | no |
| `Chat` / `ChatMessage` | assistant conversations | `domain-chat.md` | Stage 5 | no |
| `AssistantMode` | one of the fixed five modes + its prompt (admin config) | `assistant-config.md` | Stage 5 | no |
| `SubAgent` | an admin-created delegated worker | `assistant-config.md` | Stage 5 | no |
| `mode_tool` / `subagent_tool` / `mode_subagent` | admin selections wiring modes, sub-agents and tools | `assistant-config.md` | Stage 5 | no |

The last three entity rows are **instance-global admin config**, not `Book`-rooted — they sit on the admin/instance layer alongside `LlmServer`, and are exported with the global config rather than inside any book (`assistant-config.md` → "Persistence and registry obligations"). Tools themselves are **not a table** — a code-defined `TOOL_REGISTRY`, referenced by string name.

"First needed" is when a stage *uses* the entity, not when its table is created — the whole map lands early, per the reasoning above. **The Stage-4 continuity structures go further and land their columns at Stage 2**, nullable and unused (`Chapter.state = closing`, `Chapter.summary_status`, the `ChapterNoteChangeset` table and its `status`), so that Stage 4 is pure behaviour with no DDL at all. See `domain-chapter.md` → "Landing the continuity columns early".

A few relationships cross file boundaries and are cross-linked at both ends:

- `Chapter.summary` is a **chapter field** (`domain-chapter.md`) whose lifecycle is a **continuity** story (`domain-continuity.md`).
- `Book.active_notes` is a **book field** (`domain-book.md`) materialised from **chapter note changesets** (`domain-continuity.md`).
- A state note references a codex entry **by name, not by foreign key** (`domain-continuity.md` ↔ `domain-codex.md`, UC-079).
- A chat's saved output is an ordinary `ChapterChange` or `CodexEntry` (`domain-chat.md` → `domain-chapter.md` / `domain-codex.md`).

## Where to read next

| File | Covers |
|---|---|
| **`domain-book.md`** | `Book`, `BookMember`, the book lifecycle state machine (archive vs. quarantine→destroy), visibility, the moderation fields, the system-prompt fields, `active_notes`, and cloning |
| **`domain-chapter.md`** | `Chapter` and its four-state machine (`planned` → `open` → `closing` → `closed`), **CF1**, `ChapterChange` (the unified write record and the one write path), placement, stale-changes-are-refused, **variants-as-apply**, `ChapterTextRevision`, and the `version` / 409 / CF-r6 concurrency rules |
| **`domain-continuity.md`** | `ChapterNoteChangeset`, the active note set, the summary lifecycle and the `draft` / `approved` / `stale` continuity status, and `Flag` (author-facing: "warning") |
| **`domain-codex.md`** | `CodexEntry` and `CodexEntryVersion` — kinds, naming, archival, history, cross-book copy |
| **`domain-chat.md`** | `Chat` / `ChatMessage` — **entities only**, with the deferred-subsystem boundary stated in full |
| **`assistant-config.md`** | FEAT-020 — the assistant config model (`AssistantMode`, `SubAgent`, the `TOOL_REGISTRY`, the selection tables) **and** the runtime slice that consumes it (mode determination, prompt composition, tool gating, the `chat_with_tools` loop, sub-agent delegation, model resolution) |

## Conventions inherited

Every entity in those files follows the existing system-wide rules — none of them are restated per-entity:

- **Ids** — application-generated 64-bit snowflakes (`app/ids.py` `generate_id()`, `default_factory=generate_id`), **serialized as strings** at every JSON boundary (API DTOs, JSONL codecs, frontend `.d.ts`). See `backend/auth-ids.md` → "Conventions — entity ID strategy".
- **Layers** — one `db/` module per entity; services per aggregate; `routes/` is HTTP-only. See `backend.md` → "Layer separation".
- **Timestamps** — `created_at` / `modified_at` on every mutable entity; not listed per-table unless the entity carries only one.

### Two registry obligations

Both are non-optional and both are due **in the same change as the model**, not batched for later:

- **Import/export.** Every table owes a `to_dict` / `from_dict` codec pair (ids emitted as strings, accepted as string-or-legacy-number) and one ordered `TABLE_REGISTRY` tuple, appended in **FK dependency order**. That is roughly a dozen codec pairs across the domain. The root `CLAUDE.md` rule is explicit; skipping it leaves an instance whose export silently loses a book. See `backend/book-domain.md` → "The book-domain table registry".
- **Vector sources.** A vector-backed model appends a `VECTOR_SOURCE_REGISTRY` entry — `CodexEntry` is the first, at Stage 2, with chapter text, summaries and notes following for UC-086. See `retrieval.md`.

## Product divergences this design assumes

The design contradicted, exceeded or resolved `docs/product/` in **four** places. **All four were reconciled by `/product-spec` round 7 (2026-07-24, commit `987a75a`)** — `docs/product/` now carries the enforced wording, so the items below are retained as **decision history** (why the design diverged), not as an open action list. Item 4 is the one that *resolved* something product left open rather than merely differing from it — its reconciliation closed product's own coherence finding CF1, not just a wording mismatch.

**1. FEAT-014 — the operation is *apply*, not *select*.** UC-060 ("Select the active variant") and US-064 ("Owner selects which variant *is* the chapter") describe variants as parallel readable texts with a pointer selecting which one is live. This design has **one main `Chapter.text`** plus stored change-suggestions beside it (`domain-chapter.md`). A variant is an **un-applied `ChapterChange`**; it is not selectable as the chapter's text, and making it the text **is applying it** — through the same write path every other change takes. There is no pointer and no switch. UC-059's "view and compare" is served unchanged (revisions are full bodies, so any two diff cleanly), and US-065 holds necessarily rather than by special rule: an apply *is* a change, so it runs the consistency-check path a fix runs. **Merge mechanics are explicitly post-MVP** — a variant whose base version has gone stale is refused, and the author redoes it by hand.

✓ Reconciled — product round 7 (2026-07-24, `987a75a`): UC-060 retitled "Apply a variant to the chapter", US-064 reworded, and the *variant* (un-applied) vs *revision* (recoverable prior body) split adopted into product, including its glossary.

**2. A Variants navigator entry.** Round 6 declared the working-page navigator list final: Characters / Locations / Facts / Chapters / Book state / Chats. This design adds a **Variants** entry (see `frontend-workspace.md`), because `ChapterChange` and `ChapterTextRevision` give it real content from the first chapter written and there is otherwise no surface that reaches revision history.

✓ Reconciled — product round 7 (2026-07-24, `987a75a`): the Variants navigator entry was added to product UC-090 / US-105.

**3. The system prompts have no requirement behind them.** Neither `Book.system_prompt` (applied to all chats in the book, `domain-book.md`) nor the optional `Chapter.system_prompt` (which appends to the book's, `domain-chapter.md`) was, at design time, covered by any product requirement. The three sub-questions this pass flagged are now settled by FEAT-019: **who may edit them** — the book prompt is owner-only, the chapter prompt is editable by any member; **whether they survive cloning** (FEAT-015) — yes, both carry over (product US-071.AC-5); and **whether they reach the FEAT-016 consistency check** as inspected content — no, they are instructions, not chapter content, so the check does not inspect them. They are in the map because they are book-shaping state that has to live somewhere.

✓ Reconciled — product round 7 (2026-07-24, `987a75a`): a **new feature FEAT-019 was allocated** (UC-093 / UC-094, US-108 / US-109) to give the system-prompt fields a requirement, and it settles the three previously-undecided sub-questions above — book prompt owner-only / chapter prompt any member, both carry over on clone, neither inspected by the FEAT-016 check. (The FEAT-019 authorization rule and `**Realizes:** FEAT-019` headers are a deliberately deferred follow-up — not yet recorded in `authorization.md` / `domain-book.md` / `domain-chapter.md`.)

**4. CF1 — reopen is refused, not auto-closing.** UC-037 says reopening a closed chapter *auto-closes* whichever chapter is currently open. Once FEAT-012 added the approval gate, that became incoherent: an auto-close either skips the approval the gate exists to require, or strands a chapter mid-close. Product round 5 recorded this as coherence finding **CF1** — *"open-chapter singleton vs. the continuity close-gate — UC-037 reopen silently auto-closes past the UC-036 approval gate"* — and left it unresolved. **This architecture resolves it by refusing the reopen** while any chapter is `open` or `closing`; the owner closes the current chapter properly first (`domain-chapter.md` → "CF1"). That keeps both invariants and replaces a silent side effect with an explainable error — but it is a direction UC-037 did not, at design time, describe, so it was recorded here rather than assumed.

✓ Reconciled — product round 7 (2026-07-24, `987a75a`): UC-037 / US-039 were rewritten to **refuse** the reopen while another chapter is open or closing, which also closed product's own round-5 coherence finding **CF1**.

Product round 7 **additionally** reconciled two design decisions this pass had *not* flagged as divergences, so the "four" above should not be read as the full set of places product trailed the design. First, the **block-as-`ChapterChange`** model: product's UC-039 had described addressable, separately-versioned blocks, whereas this design treats a block edit as an ordinary change through the one write path (product recorded the correction as C-r7-2). Second, the **`closing` chapter state**: product had carried only three chapter states, and round 7 adopted the fourth (product C-r7-4). Both were the design all along; product caught up rather than the design changing.

## Recorded gaps

Design questions this pass deliberately leaves open. **Three earlier gaps closed on 2026-07-24 review** — the moderation fields (`domain-book.md`), the continuity status columns and the `closing` state (`domain-chapter.md`, `domain-continuity.md`), and stale pending changes (refused, not rebased). They are design, not gaps, and are no longer listed.

One genuinely open item remains:

| Gap | Lives in | Due at |
|---|---|---|
| Whether an **archived book** refuses writes. UC-023 says content and history are preserved and archive is reversible; nothing states whether a member may keep writing into one | `authorization.md` | open |

`authorization.md` carries its own "Not settled" list for questions that are authorization-shaped rather than model-shaped (the moderation view's route surface, proposal review for notes and codex entries).

## Decision history

- **2026-07-24 — First book-domain architecture pass (Stage-2 architect gate).** Drew the `FEAT-006..018` entity map whole, settled the unified `ChapterChange` write record, chose full-snapshot `ChapterTextRevision` over reverse patches, materialised `Book.active_notes`, and closed the parked **CF-r6** concurrency item with the version / 409 / visible-merge rules. Deliberately left FEAT-013's assistant internals undesigned — see "Scope of this pass". Recorded three divergences from `docs/product/` rather than resolving them; a fourth was added by the review below.
- **2026-07-24 — Six amendments from user review.** (1) The working page's content-pane subject became a **nested route** keyed on `bookId`, replacing the query-param design — the remount collision it was avoiding is not real, because chats are server-persisted and the chat pane re-resolves its own active chat (`frontend-workspace.md`). (2) FEAT-014's operation is **apply**, not select or revert. (3) A stale `pending` change is **refused, not rebased**; merge mechanics are post-MVP. (4) `Book` gained `moderation_reason` / `moderated_by` / `moderated_at`. (5) `Chapter` gained a fourth state, **`closing`**, and the continuity artifacts gained `draft` | `approved` | `stale` status, all landing at Stage 2 nullable and unused. (6) **CF1 resolved** — reopen is refused while another chapter is open, recorded as divergence 4. Gaps 1–3 from the original pass are closed by (4), (5) and (3).
- **2026-07-24 — Product reconciled (round 7).** `/product-spec` enforced this pass's decisions onto `docs/product/` (commit `987a75a`): all four recorded divergences are reconciled, plus the **block-as-`ChapterChange`** and **`closing`-state** decisions this pass had not flagged as divergences, and a **new product feature FEAT-019** was allocated to give the `Book` / `Chapter` system-prompt fields a requirement. Deferred follow-up: FEAT-019's authorization rule and the `**Realizes:** FEAT-019` headers are **not yet** recorded in `authorization.md` / `domain-book.md` / `domain-chapter.md`.
- **2026-07-24 — FEAT-020 assistant config + its runtime slice designed (`assistant-config.md`).** A new linked doc designs the FEAT-020 configuration model — the fixed five `AssistantMode` rows (seeded, keyed by a stable natural string rather than a snowflake, a **deliberate narrow exception** to the id convention so the seeded rows and their links survive cross-instance export/import), admin-created `SubAgent` (disable-not-delete, nullable `(llm_server_id, model_name)` model assignment), the **code-defined `TOOL_REGISTRY`** (not a table, referenced by string name, not exported), and the three selection tables (`mode_tool`, `subagent_tool`, `mode_subagent` — the last stored canonically on the sub-agent side, edited from both views). It also designs the **runtime slice** that consumes them: mode determination from the workspace activity, composition of the named system prompts (base → mode → book → chapter), tool gating, the tool/function-call protocol on the `llm` client's built-in `chat_with_tools` loop (with the SSE-manual-loop seam recorded), sub-agent delegation as synthetic tools, and sub-agent model resolution. This **narrows the previously-deferred FEAT-013 assistant subsystem** — context assembly, the SSE shared-canvas protocol, the main-chat model selection, web search and token budgets remain deferred (`domain-chat.md`). **This is scope expansion / decision history, not a product divergence** — product FEAT-020 already specifies this material; the design realizes it.
- **2026-07-24 — Split into `domain-*.md`.** The pass was first written as a single `domain-model.md`; it was split the same day into this index plus `domain-book.md`, `domain-chapter.md`, `domain-continuity.md`, `domain-codex.md` and `domain-chat.md`, following the folder's `frontend-*.md` split convention and the ~400-line file rule. **Organisational only** — no design decision changed.
