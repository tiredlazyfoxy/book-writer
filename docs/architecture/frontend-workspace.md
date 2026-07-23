# Frontend Workspace — entries, routes, and the working page

**Realizes:** FEAT-006, FEAT-007, FEAT-008, FEAT-009, FEAT-012, FEAT-013, FEAT-014, FEAT-016, FEAT-017; UC-021..037, UC-042, UC-051, UC-071, UC-083, UC-089, UC-090, UC-091, UC-092

The book domain's frontend topology: which Vite entries exist, what each serves, and how the working page is built. This is a deep-dive off `frontend.md`, which keeps the MobX/Mantine/API rules that everything here obeys.

## Five Vite entries

`frontend.md` describes three entries. The book domain takes it to five:

| Entry | Serves | Contents |
|---|---|---|
| `index.html` | **Shell SPA** | bookshelf (UC-021/022/030), book hub (skeleton UC-031..034, open/reopen UC-035/037), book settings (archive UC-023, transfer UC-024, co-authors UC-026/027, visibility UC-028, mode UC-042), read-only codex browse (UC-071), read-only continuity view (UC-051, UC-089) |
| `work/index.html` | **Working page SPA** | the two-pane working page — its own bundle |
| `read/index.html` | **Reader SPA** (ACT-006) | chapter text + table of contents **only** |
| `admin/index.html` | Admin SPA | unchanged |
| `login/index.html` | Login | unchanged |

**Why the reader is its own entry.** ACT-006 is a different audience that shares nothing with authoring — no codex, no notes, no flags, no book state, no settings, no chat (UC-029 states the exclusion list explicitly). Serving them the authoring bundle would ship every one of those surfaces to someone who may never see any of them, and would make "does a reader have this component?" a runtime question instead of a build-time one.

**Why the working page is its own entry.** It is the heavy surface — an editor, a navigator, and eventually a streaming chat client — and it is the one surface most sessions spend all their time in. Isolating it keeps the Shell (bookshelf, settings, browse views) small and fast to load, which is what someone picking a book actually needs.

**Product vocabulary maps onto this cleanly**: `docs/product/`'s "working SPA" is the `work` entry; its "settings-side" surfaces are the Shell.

### Accepted costs

Stated plainly, because both are real:

- **Crossing from the book hub into the workspace is a full page load**, not a client-side route change. Accepted: it happens once per working session, and the alternative is one bundle carrying every surface.
- **Auth, `api/` bootstrap and theme setup are repeated per entry.** They already are, for the three existing entries; two more entries repeat the same small cost. The shared code lives in `src/` root (`auth.ts`, `api/`, `theme.ts`) and is imported by each entry, so it is duplicated in bundles, not in source.

### Build and serving changes

- `vite.config.ts` grows two Rollup inputs (`work`, `read`) alongside `user` / `admin` / `login`.
- The custom **`spaFallback`** dev plugin (`frontend.md` → `vite.config.ts`) must rewrite deep links under `/work` and `/read` as well, or client-side routes 404 in dev.
- nginx serves two more static builds and keeps proxying `/api` (`dev-environment.md`, `system-overview.md`).

## Route map

### Shell (`/`)

| Route | Surface |
|---|---|
| `/` | Bookshelf — books owned (UC-022) and shared (UC-030); create a book (UC-021) |
| `/books/:bookId` | Book hub — chapter skeleton (UC-031..034), open / close / reopen (UC-035..037) |
| `/books/:bookId/settings` | Archive (UC-023), transfer (UC-024), co-authors (UC-026/027), visibility (UC-028), collaboration mode (UC-042) |
| `/books/:bookId/codex` | Read-only codex browse (UC-071), members-only |
| `/books/:bookId/continuity` | Read-only chapter summaries + note changesets (UC-089, UC-051), members-only |

The codex and continuity routes here are **read-only mirrors**. All *management* of codex entries, state notes, summaries and flags happens on the working page — a rule product states directly ("all management/editing of codex, state notes, summaries and flags happens ONLY on the working SPA"). Keeping the Shell copies read-only means there is exactly one editing surface per artifact, so draft-until-saved and the restore buffer have one place to live.

### Working page (`/work`)

**The content-pane subject is a nested route.** The workspace shell is keyed on `:bookId` and does not remount when the subject changes; the subject route inside it remounts per `frontend.md`'s normal path-param rule.

| Route | Content pane |
|---|---|
| `/work/:bookId` | redirects to `/work/:bookId/state` — Book state is the landing view (UC-091, US-106.AC-1) |
| `/work/:bookId/state` | Book state |
| `/work/:bookId/chapters` | chapter list |
| `/work/:bookId/chapter/:id` | one chapter |
| `/work/:bookId/characters`, `/locations`, `/facts` | codex lists, one per `kind` |
| `/work/:bookId/codex/:id` | one codex entry |
| `/work/:bookId/variants` | variants list |
| `/work/:bookId/variants/:chapterId` | one chapter's variants and revisions |
| `/work/:bookId/chats` | chat list — picking one opens it in the **chat pane**, and the route stays put |

**The chat id is not in the URL.** The chat pane resolves its own active chat, per book, and does not participate in routing at all.

**Why routes and not query params — the remount collision is not real.** The obvious objection is that a subject route change would remount the page and destroy the chat pane, breaking UC-083's independence. It does not, because **chats are server-persisted per book** (`domain-chat.md`): there is no in-memory conversation to lose. On mount the chat pane re-resolves its active chat from a stored active-chat id for that book, falling back to the **most recent chat by timestamp** when there is none. A remount costs a reload, not a conversation.

**UC-083's independence is preserved by persistence, not by URL shape.** That is the correct place for it — the guarantee is that the content-pane subject and the active chat are not bound to each other, and persistence makes that true no matter how either one is reached. Encoding the subject in query params to protect in-memory pane state would have been solving a problem the persistence model had already solved, at the cost of losing real routes for real resources.

Routes are the better fit on their own merits: a chapter and a codex entry are addressable resources, they deep-link and bookmark naturally, and `frontend.md`'s "page = route = fresh state instance, remount on path-param change" applies to the subject without special-casing.

**Keying the shell on `:bookId`** is what keeps the navigator, the loaded book, and the chat pane alive across subject navigation. Changing books remounts everything, which is correct — it is a different book.

Query params keep their existing job inside this page: **filter, sort and mode within a list**, handled in the event handler that changed them, never by a `useEffect` watching the query string (`frontend.md`).

### Reader (`/read`)

| Route | Surface |
|---|---|
| `/read/:bookId` | Table of contents — chapter names with links (UC-029) |
| `/read/:bookId/:chapterId` | Chapter text, read-only |

Two routes, and there must never be a third that shows anything else. The exclusion list in UC-029 is the spec: no codex, notes, flags, book state, settings or chat.

## The working page

Three regions:

```
┌──────────────┬────────────────────────────┬─────────────────────┐
│  Navigator   │       Content pane         │     Chat pane       │
│              │                            │                     │
│ Book state   │   a LIST  ── or ──  an     │  ┌───────────────┐  │
│ Characters   │                    ITEM    │  │ empty slot    │  │
│ Locations    │                            │  │ until Stage 5 │  │
│ Facts        │   draft-until-saved        │  │ (FEAT-013)    │  │
│ Chapters     │   restore buffer per item  │  └───────────────┘  │
│ Variants     │                            │                     │
│ Chats ───────┼────────────────────────────►  chats open HERE    │
└──────────────┴────────────────────────────┴─────────────────────┘
```

### Why the workspace lands in Stage 2, not Stage 5

Round 5 established the content pane as **a real editor, free-editable by the user**. Manual block writing (FEAT-009) and manual codex editing (FEAT-017) happen *there*, and both are Stage 2. So the two-pane shell, the navigator, the content pane, the Book-state landing view (UC-091), draft-until-saved and the restore buffer (UC-092) are all **Stage-2 architecture**.

The chat pane's **slot exists in the layout from Stage 2 and stays empty until Stage 5** adds FEAT-013 into it. The alternative — building throwaway standalone editing pages for Stage 2 and replacing them with the workspace at Stage 5 — means writing the same editor twice and migrating the restore buffer between them.

### Navigator (UC-090)

**Book state · Characters · Locations · Facts · Chapters · Variants · Chats.**

- **Book state** is the **landing view** (UC-091, US-106.AC-1) — the first thing shown on opening the book to work. It aggregates the book's own fields, and per chapter: title, summary (UC-089), after-chapter note changeset (UC-049/UC-051), and any active **warnings** in context (FEAT-016).
- **Characters / Locations / Facts** are the one `CodexEntry` table filtered by `kind` — a fixed taxonomy, not three entities.
- **Chapters** is read/write prose; Book state is the continuity picture. Product records the overlap as accepted and deliberate, not duplication.
- **Variants** is an addition to the product-final list — see "Divergence" below.
- **Chats** is the one entry that does **not** render into the content pane: a picked chat opens in the **chat pane** (UC-090 step 5, US-105.AC-3).

**"Warning" is the author-facing word for a flag.** The entity, table, DTOs and API stay `flag` (`domain-continuity.md`); every string the author reads says *warning*. FEAT-016's own product wording is recorded as pending reconciliation, so the UI adopts the new term without half-renaming the code.

### Content pane — subject and editability

The pane holds **either a list or a single item** (UC-090, UC-083). A loaded subject is editable or read-only by one rule:

| Subject | Editable? |
|---|---|
| The book's **`open`** chapter | editable (US-097.AC-3) |
| A chapter in **`closing`** | **read-only** — the owner is approving continuity for this exact body (`domain-chapter.md`) |
| Any `planned` or `closed` chapter | **read-only** (US-097.AC-1) |
| A codex entry, not archived | editable, per collaboration mode (US-079) |
| Book state | state notes editable (UC-050); everything else read-only |
| Any list | read-only |

A read-only subject refuses writes **from the author and from the assistant alike** (US-097.AC-2, US-059.AC-3). Enforcing it in one place — the subject model, not per-component — is what makes that symmetry hold when the assistant arrives at Stage 5, and it is why adding `closing` to the chapter state machine cost one row here rather than an audit of every write path.

The subject is **independent of the active chat**: loading a chapter does not change which chat is open, and switching chats does not change the subject. Because both sides are persisted — the chapter on the server, the chat on the server, the unsaved draft in the restore buffer — that independence survives navigation and reload rather than depending on either staying mounted.

## Draft-until-saved and the restore buffer

**Realizes:** UC-092, US-107; closes the CF-r6 conflict question with `domain-model.md`

Edits in the content pane are **drafts until explicitly saved**. Nothing reaches the server, and nothing reaches a co-author, until the author saves (US-103.AC-3, US-107.AC-4).

### Buffer design

| Property | Decision |
|---|---|
| Storage | **`localStorage`** — device-local browser storage |
| Scope | one buffer **per item**, keyed `(bookId, subjectKind, subjectId)` |
| Contents | the draft text, the `Chapter.version` (or codex entry `modified_at`) it forked from, and when it was written |
| Privacy | private to the author, on that device; **invisible to co-authors** (US-107.AC-3) |
| Lifetime | survives navigating away, a full reload, and closing the browser (US-107.AC-1/AC-2) |
| Loss | **lost if browser data is cleared** — accepted and stated to the author |
| Status | **never a substitute for saving** |

**`localStorage`, not `sessionStorage`**, because product requires the buffer to survive a full reload and be there "next day" — `sessionStorage` dies with the tab. **Not the server**, because the buffer is explicitly device-local and private; persisting drafts server-side would make them co-author-visible content the moment anything queried them, which is the opposite of the requirement.

**Keyed per item, not per pane**, so editing chapter 3, jumping to a codex entry and coming back restores chapter 3's draft rather than the last thing typed anywhere.

**Accepted limitation — quota.** `localStorage` is a few megabytes per origin, and a chapter body is not small. When a write hits quota, the oldest buffers are evicted, oldest-first, and the author is told. Silently dropping the buffer they are currently typing into would be the one unacceptable outcome, so the *current* item's buffer is never the eviction victim.

### Where the buffer lives in the state ladder

**Module-level state in the `work` entry, not `<Page>State`.** `frontend.md`'s ladder puts app-lifetime state at the module level (`auth.ts` is the existing example, and it already reads `localStorage`). The buffer must outlive any page-state instance by definition — surviving a reload is the requirement — so a page-scoped home would be wrong even before the remount question. The buffer module exposes plain functions (`readBuffer(key)`, `writeBuffer(key, draft)`, `clearBuffer(key)`); it is not a reactive store, matching how `auth.ts` is treated.

This is a **sanctioned exception** to `frontend.md`'s "URL query params are the persistence layer" rule. That rule is about *view* state — filter, sort, mode, scroll anchor — which is small, shareable and belongs in a bookmarkable URL. Draft content is none of those things: it is large, private, and must not travel in a link. Recorded here so the exception is deliberate rather than drift.

**The active-chat pointer lives in the same module tier.** The chat pane needs to know which chat to reopen for a book after a remount or a reload. That pointer is one id per book, device-local, stored beside the buffer — not in the URL (a chat is private, so it must not travel in a shared link) and not on the server (it is view focus, not book content). Losing it is harmless: the pane falls back to the **most recent chat by timestamp**, which is what a returning author almost always wants anyway. The conversation itself is never at risk — it is server-persisted (`domain-chat.md`).

### Returning to a stale buffer

When a buffer's recorded base version does not match the server's current version, it is a **visible merge problem — never an auto-merge** (`domain-chapter.md` → "Concurrency"):

1. The pane shows the server's current text **against** the buffered draft.
2. The author reconciles manually. This path **ships with the buffer** and is not optional.
3. An LLM-assisted merge is offered as a **Stage-5** capability, once the assistant subsystem exists.

A save carrying a stale base version is refused by the server with **409**; the client's job is to turn that refusal into the reconciliation view above rather than a raw error. This is also what US-041's "warn the second author" looks like in the UI — the warning *is* the divergence view.

## Divergences from `docs/product/`

Recorded, not resolved; `docs/product/` is read-only from here. The full list of four lives in `domain-model.md` → "Product divergences". Two of them show up on this surface:

- **A Variants navigator entry.** Round 6 declared the navigator list final (Characters / Locations / Facts / Chapters / Book state / Chats). This design adds **Variants**, because `ChapterChange` and `ChapterTextRevision` give a chapter revision history from the first chapter written, and no other navigator entry reaches it.
- **The Variants view offers *apply*, not *select*.** FEAT-014's UC-060 / US-064 describe picking which variant *is* the chapter. There is no pointer to move: an un-applied variant is not selectable as the chapter's text, and making it the text **is applying it** (`domain-chapter.md`). The view lists a chapter's un-applied changes and its prior revisions and diffs any two (UC-059, US-063); the action on one is **Apply**, which takes the ordinary write path and therefore runs the same consistency-check path a fix does (US-065). A variant whose base version has gone stale is refused, with no offer to merge — merge mechanics are post-MVP.

## Conventions this page does not break

Everything in `frontend.md` still binds — they are listed because a page this large is where they get bent:

- **`observer` on every component**, no exceptions.
- **State is data + computeds**; all loads and saves are external `(state, args, signal)` functions using `runInAction`.
- **Async resource trio** per loadable — the working page has several (subject, list, book state), so it has several trios and no aggregation type.
- **No custom `useX` hooks**, no `useCallback` / `useMemo` / `useReducer`. `useEffect` only at page level.
- **All HTTP in `src/api/`**; entity ids are `string` in every DTO.
- The eventual chat stream uses `api/sse.ts`'s `streamPost()`, not `EventSource`.

## Out of scope

- **Pane orientation, resize/divider behaviour and ratio persistence.** Product routes these to `/architect` but this pass does not settle them; they are layout mechanics with no dependency on anything above.
- **Everything inside the chat pane.** The FEAT-013 assistant — context assembly, tool protocol, the agent loop, the SSE event protocol for shared-canvas writes, scoped checks (UC-088), web search (UC-087) — is undesigned and gets its own session before Stage 5. This document fixes only that the slot exists, that chats open in it, and that a chat is independent of the content-pane subject.
- **The admin moderation view** (FEAT-011, Stage 6) — an Admin SPA surface, not one of these entries.
