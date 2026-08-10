# Architecture Folder

Finalized architecture and design documentation for BookWriter. This is the authoritative ground truth other agents read; keep it precise and current.

## Scope

BookWriter is a multi-user app for LLM-assisted authoring of long-form texts. These docs cover technology, structure and conventions — **and, since 2026-07-24, the book domain's architecture.**

**Covered now** (updated 2026-08-10, after features `009.books`, `011.chat-panel`, `012.assistant-config-editor`, `013.codex`, `021.per-author-system-prompt`, `014.chapter-skeleton`, `015.chapter-writing-free-mode`, `016.chapter-close-continuity`, `022.reader-mode`, `023.chat-ux-revision` — the chats list as a content-pane page, the reshaped chat pane and background chat titling — and `024.chat-agent-loop` — seeded mode defaults and tool-call visibility — shipped): the entity map for `FEAT-006..018` drawn whole (`domain-model.md` — the index — plus the five `domain-*.md` area files), book-scoped authorization (`authorization.md`), **the reader surface — ACT-006's two routes, the public-book discovery list and the reader-safe DTOs** (`authorization.md` → "The reader surface", `frontend-workspace.md` → Reader, `quick-reference.md`), the retrieval/embedding pipeline (`retrieval.md`), the frontend workspace topology (`frontend-workspace.md`) and its device-local draft tier (`frontend-work-drafts.md`), plus the as-built records in `backend/features.md` and the concrete endpoint/DTO/table index in `quick-reference.md`.

**The FEAT-013 assistant is now largely covered, across two files that split by concern:**

- **`assistant-config.md` — the FEAT-020 configuration model.** Modes, sub-agents, the code-defined `TOOL_REGISTRY`, the three selection tables, replace-set save semantics, the admin write-edge validation.
- **`assistant-runtime.md` — the runtime that consumes it.** Mode determination and the `TurnRequest` wire shape, the four-layer system-prompt composition, the three-case tool gating, the `chat_with_tools` protocol, sub-agent delegation, **per-chat model selection**, **web search**, the **seven-frame** SSE vocabulary (`thinking` / `delta` / `done` / `error` / `canvas` / `tool_call` / `tool_result`), the **shared-canvas write protocol for codex entries and for chapters**, and — since feature `016` — the **close-chapter tool set and the post-turn deterministic finalize hook** (a turn is no longer "stream, persist, done", though the frame vocabulary is unchanged).

**Still not covered — do not infer it:** **context / content assembly** (US-057, UC-085/086/078 internals), **token-level canvas streaming**, and **token budgeting**. A working chat pane and a working canvas write invite the reading that the context model shipped with them; it did not. See `domain-chat.md` for the boundary and `assistant-runtime.md` → "Out of scope" for the same list with reasoning.

The standing rule survives: don't invent the domain *model* here — derive it from `docs/product/`, and cite what you derived it from. A design doc realizing product requirements carries a header naming them:

```
**Realizes:** FEAT-013, UC-054, UC-078
```

Start from `docs/product/quick-reference.md` (the canonical id registry) and `docs/product/relationships.md` (the dependency graph, build order, accepted overlaps and conflicts — note the `FEAT-012 → FEAT-017` inversion). `features.md` holds the FEAT blocks only; **the dependency graph moved to `relationships.md` in product round 5.** Where a requirement carries a `_TBD:`, it is genuinely undecided: raise it, don't resolve it by choosing a design.

Where this architecture **diverged from** `docs/product/`, the divergence is recorded in `domain-model.md` → "Product divergences" — **six items, all closed.** Read them as decision history (why the design diverged), not as an action list.

- **Items 1–4** were **reconciled by `/product-spec` round 7 (2026-07-24)**. One of them (CF1) resolves a coherence finding product left open. (Item 3 is additionally annotated as partly reversed by the fifth.)
- **Item 5 — FEAT-019's system prompts went per-author, both halves** — was **reconciled by `/product-spec`'s finalization of 2026-07-30**: FEAT-019 was rewritten whole, UC-093 / UC-094 / US-108 / US-109 are tombstoned `withdrawn`, and **UC-098 / UC-099 / US-115 / US-116 are the ids to cite** for `BookAuthorPrompt` and `ChapterAuthorPrompt`.
- **Item 6 — the chapter close has no approval gate** (feature `016.chapter-close-continuity`) — was **reconciled on arrival, 2026-07-31**. Product chose **deferral over withdrawal** for UC-048 / US-050 / US-051 / UC-066, so those ids still exist as future work; **do not cite them**, because the design contradicts their criteria.

**Never edit `docs/product/` to close a divergence** — not a future one, not any of these. Surfacing it is the orchestrator's follow-up; closing it is `/product-spec`'s.

The root-level `product.md` is a human-facing business narrative, **not** development guidance — ignore it; the canonical product layer is `docs/product/`.

## Contents and reading order

For the document catalogue and reading order, see `README.md` (the canonical index). Three structural facts a reader needs before navigating:

- **The backend layer is an index plus a `backend/` sub-tree.** `backend.md` holds the cross-cutting rules and decision history, with `backend/persistence.md`, `backend/auth-ids.md`, `backend/features.md` and `backend/book-domain.md` under it.
- **The assistant is a pair, split by concern (2026-07-29).** `assistant-config.md` is the stored configuration and the admin write edge; `assistant-runtime.md` is a turn. The split happened when features 011 and 013 built the runtime out and the combined file outgrew the ~400-line rule. Adding to the wrong half is the easy mistake — ask whether the thing you are writing is *configured* or *executed*.
- **The working page is a pair too (2026-07-29).** `frontend-workspace.md` keeps entries, routes and panes; `frontend-work-drafts.md` holds the device-local draft tier — the restore buffer, the module-state members beside it, the canvas target registry and reconciliation.

## Write-rules

- This folder holds **final, approved** documentation only. Drafts and planning live in `docs/plans/`.
- State decisions **with reasoning** — "we chose X because Y," never a bare assertion.
- Be explicit about what is **out of scope**, and about which product requirements a doc does *not* yet cover.
- **Cite product ids.** A doc designing for the book domain carries a `**Realizes:** FEAT-###, UC-###` header. `docs/product/` is read-only from here — never edit it to fit a design; if a requirement is wrong or missing, surface it for `/product-spec`.
- **Line limit: keep each file under ~400 lines.** If a topic outgrows that, split off the largest subsystem into its own cohesive file and link it from the parent and from `README.md`. This has now happened twice — `assistant-runtime.md` out of `assistant-config.md`, and `frontend-work-drafts.md` out of `frontend-workspace.md` — and both splits kept the reasoning with the thing it explains rather than leaving a stub behind. **`quick-reference.md` is the one intentional exception** and is dense by design: it is where concrete endpoints, DTOs, columns and status codes go *instead of* being repeated into every design doc, which is what keeps the rest of the folder inside the limit.
- Never silently overwrite an existing doc — surface changes so the diff is easy to review.
- Build/test commands are the root `CLAUDE.md`'s job; reference them, don't duplicate them here.
- Do not add a new top-level doc unilaterally — it must be called out in the briefing; otherwise surface the need in the hand-back.
