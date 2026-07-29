# Frontend Workspace — entries, routes, and the working page

**Realizes:** FEAT-006, FEAT-007, FEAT-008, FEAT-009, FEAT-012, FEAT-013, FEAT-014, FEAT-016, FEAT-017, FEAT-018, FEAT-019; UC-021..037, UC-042, UC-051, UC-069, UC-070, UC-071, UC-076, UC-077, UC-081, UC-083, UC-089, UC-090, UC-091

The book domain's frontend topology: which Vite entries exist, what each serves, and how the working page is built. This is a deep-dive off `frontend.md`, which keeps the MobX/Mantine/API rules that everything here obeys.

**The draft tier moved out.** The restore buffer, the module-state modules beside it, the canvas target registry and the reconciliation view are in **`frontend-work-drafts.md`** — along with UC-092 / US-107, which it now realizes. Features 011 and 013 tripled that material, and it is a subsystem rather than a section of a topology document. This document keeps the entries, the routes and the panes.

## Five Vite entries

The book domain took the build from three entries to five; `frontend.md` → `vite.config.ts` carries the config, this table carries what each one serves:

| Entry | Serves | Contents |
|---|---|---|
| `index.html` | **Shell SPA** | bookshelf (UC-021/022/030), book hub (skeleton UC-031..034, open/reopen UC-035/037), book settings (archive UC-023, transfer UC-024, co-authors UC-026/027, visibility UC-028, mode UC-042), read-only codex browse (UC-071), read-only continuity view (UC-051, UC-089) |
| `work/index.html` | **Working page SPA** | the two-pane working page — its own bundle |
| `read/index.html` | **Reader SPA** (ACT-006) | chapter text + table of contents **only** |
| `admin/index.html` | Admin SPA | unchanged |
| `login/index.html` | Login | unchanged |

**Why the reader is its own entry.** ACT-006 is a different audience that shares nothing with authoring — no codex, no notes, no flags, no book state, no settings, no chat (UC-029 states the exclusion list explicitly). Serving them the authoring bundle would ship every one of those surfaces to someone who may never see any of them, and would make "does a reader have this component?" a runtime question instead of a build-time one.

**Why the working page is its own entry.** It is the heavy surface — an editor, a navigator, and a streaming chat client (all three now built) — and it is the one surface most sessions spend all their time in. Isolating it keeps the Shell (bookshelf, settings, browse views) small and fast to load, which is what someone picking a book actually needs.

**Product vocabulary maps onto this cleanly**: `docs/product/`'s "working SPA" is the `work` entry; its "settings-side" surfaces are the Shell.

### Accepted costs

Stated plainly, because both are real:

- **Crossing from the book hub into the workspace is a full page load**, not a client-side route change. Accepted: it happens once per working session, and the alternative is one bundle carrying every surface.
- **Auth, `api/` bootstrap and theme setup are repeated per entry.** They already were, for the three original entries; two more entries repeat the same small cost. The shared code lives in `src/` root (`auth.ts`, `api/`, `theme.ts`) and is imported by each entry, so it is duplicated in bundles, not in source.

### Build and serving changes

- **Done (feature 010).** `vite.config.ts` carries five Rollup inputs — `work` and `read` alongside `user` / `admin` / `login`.
- **Done (feature 010).** The custom **`spaFallback`** dev plugin (`frontend.md` → `vite.config.ts`) branches `/work` and `/read` before its catch-all `else`, so their deep links resolve in dev instead of 404ing.
- **Pending, and blocked on something that does not exist.** nginx must serve two more static builds and keep proxying `/api`. Nothing was changed for it, because **`nginx/` and both `docker-compose*.yml` are absent from this repository** — verified at feature 010. The `/work` and `/read` static roots must therefore be added **when that serving layer is first created**, not retrofitted. The same pending item applies wherever `dev-environment.md` and `system-overview.md` describe nginx static roots; they describe a serving layer that is designed but not yet built.

## Route map

### Shell (`/`)

| Route | Surface | Built? |
|---|---|---|
| `/` | Bookshelf — books owned (UC-022) and shared (UC-030); create a book (UC-021) | **yes** (feature 009) |
| `/books/:bookId` | Book hub — chapter skeleton (UC-031..034), open / close / reopen (UC-035..037) | no |
| `/books/:bookId/settings` | Archive (UC-023), transfer (UC-024), co-authors (UC-026/027), visibility (UC-028), collaboration mode (UC-042), **the caller's own system prompt** (feature 021) | **yes** (feature 009) |
| `/books/:bookId/codex` | Read-only codex browse (UC-071), members-only | no |
| `/books/:bookId/continuity` | Read-only chapter summaries + note changesets (UC-089, UC-051), members-only | no |

Feature 009 delivered the bookshelf and the settings page on the **existing `index.html` Shell entry** — no new entry was needed. The book hub and the two read-only mirrors are still unbuilt, as is the whole `read/` reader entry (its `main.tsx` and a table-of-contents placeholder exist; see `frontend.md` → Folder layout).

**Why the system-prompt editor exists on two surfaces (feature 021).** The same per-author prompt is editable here on `BookSettingsPage` **and** on the working page's Book-state view, deliberately. The settings page aggregates **owner-only** capabilities, but **every author now owns a prompt**, so the editor must also live where **every member** lands — UC-091's Book-state landing view. The two surfaces share the DTOs and the `api/` functions at `src/` root but **not a state class and not a component**: crossing from the `work` entry into the `user` entry would break the folder layout, and each page owns its own state per the page-is-a-route rule. Two editors for one value is duplication only if the reason is unwritten.

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
| `/work/:bookId/codex/new?kind=<character\|location\|fact>` | a **blank** codex entry of the chosen kind |
| `/work/:bookId/codex/:id` | one codex entry |
| `/work/:bookId/variants` | variants list |
| `/work/:bookId/variants/:chapterId` | one chapter's variants and revisions |
| `/work/:bookId/chats` | **redirect only** — the chat list lives in the chat pane; see below |

**`codex/new` exists because a blank entry has no id (feature 013).** UC-076 requires a blank entry of a chosen kind to be openable *before any row exists*, and `/codex/:id` cannot express "no id yet". The **kind rides in a query param** rather than in the path because it is view state chosen at navigation time, not an identifier; the route stays deep-linkable either way. It is declared **ahead of** `codex/:id` so the static segment wins.

**The chat id is not in the URL.** The chat pane resolves its own active chat, per book, and does not participate in routing at all.

**`/work/:bookId/chats` is a redirect — resolving this document's own contradiction (feature 011).** The route table used to read as though the chat *list* rendered in the content pane, while the navigator section below says Chats "does not render into the content pane". Two sentences of the same document disagreed. **Product settles it**: US-095.AC-1 and UC-081 step 1 both say "the chat pane's list". As shipped:

- the **list lives in the chat pane**;
- the **Chats navigator entry is a control over pane state, not a router link** — it uses the `paneTarget: "chat"` discriminator feature 010 already froze on `WorkNavigator`'s items, and renders as a `<button>` that reveals the list without navigating;
- **`/work/:bookId/chats` survives only as a redirect**, so the deep link this document documented neither 404s nor renders a chat surface in the content pane.

Recorded with its product basis so the next reader does not have to re-adjudicate it.

**Why routes and not query params — the remount collision is not real.** The obvious objection is that a subject route change would remount the page and destroy the chat pane, breaking UC-083's independence. It does not, because **chats are server-persisted per book** (`domain-chat.md`): there is no in-memory conversation to lose. On mount the chat pane re-resolves its active chat from a stored active-chat id for that book, falling back to the **most recent chat by timestamp** when there is none. A remount costs a reload, not a conversation.

**UC-083's independence is preserved by persistence, not by URL shape.** That is the correct place for it — the guarantee is that the content-pane subject and the active chat are not bound to each other, and persistence makes that true no matter how either one is reached. Encoding the subject in query params to protect in-memory pane state would have been solving a problem the persistence model had already solved, at the cost of losing real routes for real resources.

Routes are the better fit on their own merits: a chapter and a codex entry are addressable resources, they deep-link and bookmark naturally, and `frontend.md`'s "page = route = fresh state instance, remount on path-param change" applies to the subject without special-casing.

**Keying the shell on `:bookId`** is what keeps the navigator, the loaded book, and the chat pane alive across subject navigation. Changing books remounts everything, which is correct — it is a different book.

Query params keep their existing job inside this page: **filter, sort and mode within a list**, handled in the event handler that changed them, never by a `useEffect` watching the query string (`frontend.md`).

**Feature 013 is the repo's first query-param consumer anywhere in the frontend** — there were zero uses of `useSearchParams` / `URLSearchParams` before it — and the first param is the codex list's **search needle**. The rule held: the query string is read **once**, in the state instance's initializer, so a deep-linked `?q=` filters the first fetch, and it is written **in the submit handler**, never watched. The *mechanism* that makes this possible under the MobX split — the returned-search-string seam — is in `frontend.md` → "Routes and pages"; it is a general rule, not a codex one, so it lives with the rules.

### Reader (`/read`)

| Route | Surface |
|---|---|
| `/read/:bookId` | Table of contents — chapter names with links (UC-029) |
| `/read/:bookId/:chapterId` | Chapter text, read-only |

Two routes, and there must never be a third that shows anything else. The exclusion list in UC-029 is the spec: no codex, notes, flags, book state, settings or chat.

**Neither route is built.** The `read` entry exists as a **stub** — a table-of-contents placeholder with no router and no gate (`frontend.md` → Folder layout). It was landed with feature 010 only so the fifth Rollup input and the `spaFallback` branch had something to serve. Do not read the stub's shallowness as the designed reader; the two routes above are still the design.

## The working page

Three regions:

```
┌──────────────┬────────────────────────────┬─────────────────────┐
│  Navigator   │       Content pane         │     Chat pane       │
│              │       <Outlet/>            │                     │
│ Book state   │   a LIST  ── or ──  an     │  list · settings    │
│ Characters   │                    ITEM    │  transcript         │
│ Locations    │   (codex: realized)        │  thinking block     │
│ Facts        │                            │  composer           │
│ Chapters     │   draft-until-saved        │                     │
│ Variants     │   restore buffer per item  │                     │
│ Chats ───────┼────────────────────────────►  chats open HERE    │
└──────────────┴────────────────────────────┴─────────────────────┘
```

The shell keyed on `:bookId` owns all three regions and does not remount when the content-pane subject changes.

### Why the workspace lands in Stage 2, not Stage 5

Round 5 established the content pane as **a real editor, free-editable by the user**. Manual block writing (FEAT-009) and manual codex editing (FEAT-017) happen *there*, and both are Stage 2. So the two-pane shell, the navigator, the content pane, the Book-state landing view (UC-091), draft-until-saved and the restore buffer (UC-092) are all **Stage-2 architecture**.

The chat pane's slot existed in the layout from Stage 2 and was expected to stay empty until Stage 5. The alternative — building throwaway standalone editing pages for Stage 2 and replacing them with the workspace at Stage 5 — means writing the same editor twice and migrating the restore buffer between them. **The slot filled early**: feature 011 landed the chat pane against the Stage-2 shell (see "Chat pane" below), which is the outcome the layout decision was designed to make cheap.

### The shell, the outlet, and who loads what

**The workspace shell renders the repository's first `<Outlet/>` (feature 010).** The precedent is now **deliberately split**, and both halves are correct:

- **`AdminShell` keeps `children`** — its content is passed in by the route element and it has no nested-route structure to project.
- **`WorkspaceShell` uses `<Outlet/>`** because it is **keyed on `:bookId`** and must not remount when the subject route changes. `children` would force the shell's own element to be rebuilt per subject, destroying the navigator's loaded book and the chat pane's state — exactly what keying on `:bookId` exists to prevent.

An in-code comment on `AdminShell` asserts a repo-wide "no `<Outlet/>` anywhere" property. **That comment is stale** and is flagged here rather than silently left to mislead; the property is now per-shell, not repo-wide.

**Subject pages load their own data by URL id.** The shell's `getBookDetail` load serves the **navigator and header chrome only**; the Book-state landing view **fetches the book again** for itself. This looks like a redundant fetch and is a deliberate one: `useOutletContext` was **rejected because it is React context**, which `frontend.md` bans outright, and warm-starting a page from a parent's data would break "each page loads its own data by URL id, every page is deep-linkable."

**The shell keyed on `:bookId` is treated as the page-level mount** for `frontend.md`'s "`useEffect` only at page level" rule. It is the thing that remounts on a path-param change and owns the load/cleanup lifecycle, so its mount effect is a page-level effect even though a nested route renders inside it. Both of these are non-obvious readings of existing rules, recorded because later features copy them.

### Navigator (UC-090)

**Book state · Characters · Locations · Facts · Chapters · Variants · Chats.**

- **Book state** is the **landing view** (UC-091, US-106.AC-1) — the first thing shown on opening the book to work. It aggregates the book's own fields, and per chapter: title, summary (UC-089), after-chapter note changeset (UC-049/UC-051), and any active **warnings** in context (FEAT-016).
- **Characters / Locations / Facts** are the one `CodexEntry` table filtered by `kind` — a fixed taxonomy, not three entities.
- **Chapters** is read/write prose; Book state is the continuity picture. Product records the overlap as accepted and deliberate, not duplication.
- **Variants** is an addition to the product-final list — see "Divergence" below.
- **Chats** is the one entry that does **not** render into the content pane: a picked chat opens in the **chat pane** (UC-090 step 5, US-105.AC-3). It is a pane control, not a router link — see the route map above.

#### What each section actually shows today

The navigator was built whole at feature 010 with **one** section carrying data and every other one a labelled empty state naming its owner. Two features have filled sections since; the current state is:

| Section | State |
|---|---|
| Book state | **has data** — the book's own fields and members (feature 010), plus the caller's own system prompt (feature 021) |
| Characters / Locations / Facts | **has data** (feature 013) |
| Chats | **has data** (feature 011), in the chat pane |
| Chapters | labelled empty state — owner `014.chapter-skeleton` |
| Variants | labelled empty state — owner `018.chapter-history-variants` |

Within Book state, one deferral survives and is deliberate: **US-106.AC-2/AC-3** — per chapter, its title, summary, after-chapter note changeset and active warnings — is deferred to **`016.chapter-close-continuity`** and ships as a labelled empty state, because no chapter, summary or flag endpoint exists to aggregate. Feature 010's record that the landing view aggregated the **book's own fields only** is retained here as history; it was true of that feature and is no longer true of the page.

A labelled empty state naming its owning feature is the convention, not a placeholder oversight: the navigator's shape is fixed by UC-090 and building it whole once is cheaper than growing it seven times, but an unlabelled blank pane reads as a bug.

**"Warning" is the author-facing word for a flag.** The entity, table, DTOs and API stay `flag` (`domain-continuity.md`); every string the author reads says *warning*. FEAT-016's own product wording is recorded as pending reconciliation, so the UI adopts the new term without half-renaming the code.

### Content pane — subject and editability

The pane holds **either a list or a single item** (UC-090, UC-083). A loaded subject is editable or read-only by one rule:

| Subject | Editable? |
|---|---|
| The book's **`open`** chapter | editable (US-097.AC-3) |
| A chapter in **`closing`** | **read-only** — the owner is approving continuity for this exact body (`domain-chapter.md`) |
| Any `planned` or `closed` chapter | **read-only** (US-097.AC-1) |
| A codex entry, not archived | editable, per collaboration mode (US-079) |
| Book state | state notes editable (UC-050) **and the caller's own system prompt** (feature 021); everything else read-only |
| Any list | read-only |

**The Book-state row gained exactly one editable region (feature 021).** The caller's own per-author system prompt is editable there; the rest of the view stays read-only. It is deliberately **outside the draft-until-saved restore buffer**: the buffer exists for large content-pane artifacts whose loss is expensive, while this is a short settings field edited from **two** surfaces (here and the Shell's book settings), and buffering it on one but not the other would be incoherent. Consequently the field has **no `baseVersion`, no stale-buffer detection, no divergence view and no 409 path** — the row has exactly one writer, its owner. An editable field missing from this table is drift, and the exclusion is sanctioned in `frontend-work-drafts.md` → "Sanctioned exclusions" the same way the buffer's inclusions are.

**`src/work/subject.ts` is the single enforcement point** for this table — the one place editability is decided, not per-component. That is what makes the symmetry in US-097.AC-2 / US-059.AC-3 hold, and it is why adding `closing` to the chapter state machine cost one row here rather than an audit of every write path. `resolveEditability` returns the verdict and the author-facing read-only reason; `checkWritePermission` is the writer-agnostic gate derived from it.

**It is now wired, and its open note is closed (feature 013).** Written by feature 010 and until then imported only by `restoreBuffer.ts`, `subject.ts` is now the live subject model: `resolveEditability` drives the codex entry page's **read-only banner**, and `LoadedSubject` is what the canvas target registry holds and what the assistant turn request is built from. Its in-code note — that "the free/proposal collaboration-mode nuance is `013.codex`'s to apply" — is **closed**: the nuance is applied **server-side**, where a co-author's write in a proposal-mode book is refused with **403**, so `subject.ts` needed no change at all. The assistant and the author are refused **by the same rule at the same place**, which is exactly what US-097.AC-2's symmetry asked for. A file written for a future feature and then satisfied differently must say so, or its note reads as unfinished work forever.

**Two implementations, two vocabularies, on purpose.** The table now has a second implementation: `backend/app/services/codex_tools.py::_refuse_write` is the assistant's **server-side mirror** of `frontend/src/work/subject.ts::checkWritePermission`. They speak different languages by design:

| Writer | Refusal lives in | Refusal looks like |
|---|---|---|
| The author's save | `services/codex.py` | the **403 / 400 / 409** HTTP taxonomy that service owns |
| The assistant's canvas write | `services/codex_tools.py::_refuse_write` | a **tool string the model reads** |

The assistant's refusal is a string rather than a status because **a raising tool would abort the turn** — the model must be told *no* and allowed to continue, where the author's client must be told *no* and shown why. Same rule, same subject model, two surfaces. `assistant-runtime.md` holds the server half.

The subject is **independent of the active chat**: loading a chapter does not change which chat is open, and switching chats does not change the subject. Because both sides are persisted — the chapter on the server, the chat on the server, the unsaved draft in the restore buffer — that independence survives navigation and reload rather than depending on either staying mounted.

### The pane's first real pages (feature 013)

The content pane is `<AppShell.Main><Outlet/></AppShell.Main>` and stays that way — **no content-pane state class was introduced.** Each page owns its own state, per the page-is-a-route rule, and the pane itself holds none. Two pages realize the "a LIST — or — an ITEM" shape:

- **`CodexListPage`** — **one parameterized page** serving `/characters`, `/locations` and `/facts`, with the `kind` fixed by the route rather than by a prop the user can change. Three routes, one component, because the three lists differ only in a filter value.
- **`CodexEntryPage`** — serving both `/codex/:id` and `/codex/new?kind=…`, the latter as a blank entry with no row behind it.

This is the pattern chapters and variants follow: a page per route, its own state class beside it, its own load in its own page-level effect, and nothing owned by the pane.

### Chat pane (feature 011)

The slot is no longer empty. Feature 010's `ChatPaneSlot` placeholder is gone — the slot is now a one-line adapter onto the real pane, and the pane's parts live in `src/work/components/chat/`:

| Part | Role |
|---|---|
| `ChatPane.tsx` | the pane itself — header, controls, and which sub-surface is showing |
| `ChatList.tsx` | the book's chats, with the active marker, per-row archive/restore and an archived toggle |
| `ChatSettingsPanel.tsx` | per-chat model and sampling, shared by the new-chat form and the settings view |
| `MessageList.tsx` | the transcript, plus the in-flight bubble while a turn streams |
| `ThinkingBlock.tsx` | the collapsible reasoning region |
| `Composer.tsx` | the prompt input with send / stop and the retry banner |
| `chatPaneState.ts` | the pane's single state class |

**One state instance, owned by the shell.** `WorkspaceShell` owns the `ChatPaneState`, starts its load in its existing mount effect, and passes the instance down; the navigator gets a zero-arg handler, not the state. The full pattern and its reasoning are in `frontend.md` → Components, because it is a general rule with a worked example here rather than a workspace-specific arrangement.

**The pane is a client of the assistant, not its design.** Prompt composition, the tool loop, mode gating and the five-frame SSE vocabulary (`thinking` / `delta` / `done` / `error` / `canvas`) are in `assistant-runtime.md`. What this document fixes is that the pane exists, that chats open in it, and that a chat is independent of the content-pane subject.

## Draft-until-saved and the restore buffer — moved

Edits in the content pane are **drafts until explicitly saved**: nothing reaches the server, and nothing reaches a co-author, until the author saves (US-103.AC-3, US-107.AC-4). That is the one fact this document needs.

Everything else about it — the buffer design table, the `localStorage` reasoning, the module-state tier it lives in and its two siblings (`activeChat.ts`, `contentSubject.ts`), the principal-text-field rule, the canvas target registry, and the two entrances to the reconciliation view — is in **`frontend-work-drafts.md`**. It moved there when features 011 and 013 turned one section into a subsystem.

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
- The chat stream uses `api/sse.ts`'s `streamPost()`, not `EventSource`. It is the repo's first call site and it bent two conventions — a refresh awaited before the stream opens, and an effect that takes no trailing `signal` because the stream owns its own `AbortController`. Both are sanctioned and both are recorded in `frontend.md` → SSE / streaming, not here, because the next streaming surface will meet them wherever it lives.

## Out of scope

- **Pane orientation, resize/divider behaviour and ratio persistence.** Product routes these to `/architect` but this pass does not settle them; they are layout mechanics with no dependency on anything above.
- **The assistant's internals.** They are no longer undesigned — `assistant-runtime.md` and `assistant-config.md` hold them — but they are not this document's. What remains genuinely undesigned there (context assembly, scoped checks UC-088, token budgets, the shared-canvas protocol for **chapters**) is bounded in those files, not here.
- **The admin moderation view** (FEAT-011, Stage 6) — an Admin SPA surface, not one of these entries.
