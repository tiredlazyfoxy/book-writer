# Frontend Workspace — entries, routes, and the working page

**Realizes:** FEAT-006, FEAT-007, FEAT-008, FEAT-009, FEAT-012, FEAT-013, FEAT-014, FEAT-016, FEAT-017, FEAT-018, FEAT-019; UC-021..037, UC-042, UC-051, UC-069, UC-070, UC-071, UC-076, UC-077, UC-081, UC-083, UC-089, UC-090, UC-091, UC-100

The book domain's frontend topology: which Vite entries exist, what each serves, and how the working page is built. This is a deep-dive off `frontend.md`, which keeps the MobX/Mantine/API rules that everything here obeys.

**The draft tier moved out.** The restore buffer, the module-state modules beside it, the canvas target registry and the reconciliation view are in **`frontend-work-drafts.md`** — along with UC-092 / US-107, which it now realizes. Features 011 and 013 tripled that material, and it is a subsystem rather than a section of a topology document. This document keeps the entries, the routes and the panes.

## Five Vite entries

The book domain took the build from three entries to five; `frontend.md` → `vite.config.ts` carries the config, this table carries what each one serves:

| Entry | Serves | Contents |
|---|---|---|
| `index.html` | **Shell SPA** | bookshelf (UC-021/022/030, **and public-book discovery UC-100**), book hub (**read-only** chapter list — no state transitions; see the route map), book settings (archive UC-023, transfer UC-024, co-authors UC-026/027, visibility UC-028, mode UC-042), read-only codex browse (UC-071), read-only continuity view (UC-051, UC-089) |
| `work/index.html` | **Working page SPA** | the two-pane working page — its own bundle |
| `read/index.html` | **Reader SPA** (ACT-006) | chapter text + table of contents **only** — built by feature `022.reader-mode` |
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
| `/` | Bookshelf — books owned (UC-022), shared (UC-030) and **public books the caller is not a member of (UC-100, US-118)**; create a book (UC-021) | **yes** (features 009, `022`) |
| `/books/:bookId` | Book hub — a **read-only** ordered chapter list with state badges, linking into the working page. **No chapter editing and no state transitions** | no |
| `/books/:bookId/settings` | Archive (UC-023), transfer (UC-024), co-authors (UC-026/027), visibility (UC-028), collaboration mode (UC-042), **the caller's own system prompt** (feature 021) | **yes** (feature 009) |
| `/books/:bookId/codex` | Read-only codex browse (UC-071), members-only | no |
| `/books/:bookId/continuity` | Read-only chapter summaries + note changesets (UC-089, UC-051), members-only | no |

Feature 009 delivered the bookshelf and the settings page on the **existing `index.html` Shell entry** — no new entry was needed. The book hub and the two read-only mirrors are still unbuilt. **The `read/` reader entry is built** as of feature `022.reader-mode` (see Reader below and `frontend.md` → Folder layout).

**The bookshelf gained a third section (feature `022`, design-notes D13/D16): "Public books", below "My books" and "Shared with me".** It is fed by a **third async-resource trio** in the delivered bookshelf page state, loaded by the **same existing mount effect** as the other two — one page, one load, three trios, per `frontend.md`'s no-aggregation-type rule. Each row links via a **plain `<a href="/read/<id>">`, not a router `<Link>`**: crossing Vite entries is a full page load, matching the delivered `<a href="/work/<id>">` idiom. Empty means a **labelled** empty state, not a blank table. The three sections are **disjoint by construction** — the discovery query excludes both books the caller owns and books they co-author (`authorization.md` → "The reader surface") — which is the same disjointness the product layer records as a testable invariant.

**Why the system-prompt editor exists on two surfaces (feature 021).** The same per-author prompt is editable here on `BookSettingsPage` **and** on the working page's Book-state view, deliberately. The settings page aggregates **owner-only** capabilities, but **every author now owns a prompt**, so the editor must also live where **every member** lands — UC-091's Book-state landing view. The two surfaces share the DTOs and the `api/` functions at `src/` root but **not a state class and not a component**: crossing from the `work` entry into the `user` entry would break the folder layout, and each page owns its own state per the page-is-a-route rule. Two editors for one value is duplication only if the reason is unwritten.

The codex and continuity routes here are **read-only mirrors**. All *management* of codex entries, state notes, summaries and flags happens on the working page — a rule product states directly ("all management/editing of codex, state notes, summaries and flags happens ONLY on the working SPA"). Keeping the Shell copies read-only means there is exactly one editing surface per artifact, so draft-until-saved and the restore buffer have one place to live.

**The chapter skeleton moved to the working page (feature `014.chapter-skeleton`), and the book hub became a read-only mirror like the other two.** UC-031..034 — add, remove, reorder and the sketch editor — are **off** the Shell row above and on the working page's `/chapters` and `/chapter/:id` rows below. This **diverges from this document's own earlier route table but agrees with this document's own stated rule**: the chapter skeleton was the one row still claiming a second editing surface for an artifact, and it no longer does. **The divergence is internal to this document, not with `docs/product/`** — no UC or US says which SPA the skeleton is built from, so nothing is owed to `/product-spec` for it.

**Feature `015.chapter-writing-free-mode` finished that move: UC-035..037 are not on the Shell either.** Open, close and reopen live on the **working page's chapter item** (`/work/:bookId/chapter/:id`) — one surface per action, per `014`'s "the Book hub READS, the working page EDITS". The Shell hub is now a read-only ordered chapter list and nothing more. Two surfaces claiming one action is exactly what the one-editing-surface rule exists to prevent, and this row was the last place still claiming it.

### Working page (`/work`)

**The content-pane subject is a nested route.** The workspace shell is keyed on `:bookId` and does not remount when the subject changes; the subject route inside it remounts per `frontend.md`'s normal path-param rule.

| Route | Content pane |
|---|---|
| `/work/:bookId` | redirects to `/work/:bookId/state` — Book state is the landing view (UC-091, US-106.AC-1) |
| `/work/:bookId/state` | Book state |
| `/work/:bookId/chapters` | chapter list — **add (UC-031), remove (UC-034) and reorder (UC-032)** |
| `/work/:bookId/chapter/:id` | one chapter — **the sketch editor (`planned`, UC-033)**, **the caller's own chapter system prompt (all states)**, **the body editor (`open`, UC-038/039)**, **the state transition control (open / close / reopen, UC-035..037)**, the divergence view and the undo control |
| `/work/:bookId/characters`, `/locations`, `/facts` | codex lists, one per `kind` |
| `/work/:bookId/codex/new?kind=<character\|location\|fact>` | a **blank** codex entry of the chosen kind |
| `/work/:bookId/codex/:id` | one codex entry |
| `/work/:bookId/variants` | variants list |
| `/work/:bookId/variants/:chapterId` | one chapter's variants and revisions |
| `/work/:bookId/chats` | the book's **chats list** — an ordinary content-pane page (feature `023`), active and archived; picking a row opens that chat in the **chat pane** with no route change |

**`codex/new` exists because a blank entry has no id (feature 013).** UC-076 requires a blank entry of a chosen kind to be openable *before any row exists*, and `/codex/:id` cannot express "no id yet". The **kind rides in a query param** rather than in the path because it is view state chosen at navigation time, not an identifier; the route stays deep-linkable either way. It is declared **ahead of** `codex/:id` so the static segment wins.

**The chat id is not in the URL.** The chat pane resolves its own active chat, per book, and does not participate in routing at all.

**`/work/:bookId/chats` is a real page — the second and final resolution of this document's own contradiction (feature 011, then feature `023.chat-ux-revision`).** The route table once read as though the chat *list* rendered in the content pane while the navigator section below said Chats "does not render into the content pane"; two sentences of the same document disagreed.

**Feature 011 resolved it toward the pane**, citing US-095.AC-1 and UC-081 step 1 — which at that time both said "the chat pane's list". As shipped by 011: the list lived in the chat pane, the Chats navigator entry was a **pane control** (`paneTarget: "chat"`, the discriminator feature 010 froze on `WorkNavigator`'s items) rendering as a `<button>` rather than a link, and `/work/:bookId/chats` survived only as a redirect.

**Feature `023.chat-ux-revision` inverted it.** As shipped now: the list is **its own content-pane page** (`ChatsListPage`), the **Chats navigator entry is an ordinary router link** — its `paneTarget` is `"content"` like every other entry — and a **picked** chat is opened in the chat pane through a **module-level controller registry**, with no route change and still no chat id in the URL.

**`docs/product/` was amended to match on 2026-08-10** (UC-081, US-095.AC-1, US-105.AC-3/AC-5). Say the sequence plainly rather than smoothing it: 023 was built on 2026-08-08 **knowing it contradicted a delivered acceptance criterion** — the author chose to build now and reconcile after — so between 2026-08-08 and 2026-08-10 the code was deliberately ahead of the spec. The reconciliation was owed, and it has been paid.

**Why the inversion is the better shape, not merely the newer one.** Chats was the navigator's **only** entry that was a pane control rather than a link, and that exception is exactly what produced the contradiction in the first place. Removing it makes the navigator uniform — every entry is a link to a content-pane page — and leaves the chat pane with one job: showing the one conversation that is open.

**Why routes and not query params — the remount collision is not real.** The obvious objection is that a subject route change would remount the page and destroy the chat pane, breaking UC-083's independence. It does not, because **chats are server-persisted per book** (`domain-chat.md`): there is no in-memory conversation to lose. On mount the chat pane re-resolves its active chat from a stored active-chat id for that book, falling back to the **most recent chat by timestamp** when there is none. A remount costs a reload, not a conversation.

**UC-083's independence is preserved by persistence, not by URL shape.** That is the correct place for it — the guarantee is that the content-pane subject and the active chat are not bound to each other, and persistence makes that true no matter how either one is reached. Encoding the subject in query params to protect in-memory pane state would have been solving a problem the persistence model had already solved, at the cost of losing real routes for real resources.

Routes are the better fit on their own merits: a chapter and a codex entry are addressable resources, they deep-link and bookmark naturally, and `frontend.md`'s "page = route = fresh state instance, remount on path-param change" applies to the subject without special-casing.

**Keying the shell on `:bookId`** is what keeps the navigator, the loaded book, and the chat pane alive across subject navigation. Changing books remounts everything, which is correct — it is a different book.

Query params keep their existing job inside this page: **filter, sort and mode within a list**, handled in the event handler that changed them, never by a `useEffect` watching the query string (`frontend.md`).

**Feature 013 is the repo's first query-param consumer anywhere in the frontend** — there were zero uses of `useSearchParams` / `URLSearchParams` before it — and the first param is the codex list's **search needle**. The rule held: the query string is read **once**, in the state instance's initializer, so a deep-linked `?q=` filters the first fetch, and it is written **in the submit handler**, never watched. The *mechanism* that makes this possible under the MobX split — the returned-search-string seam — is in `frontend.md` → "Routes and pages"; it is a general rule, not a codex one, so it lives with the rules.

### Reader (`/read`)

| Route | Surface |
|---|---|
| `/read/:bookId` | Table of contents — the book's **written** chapters as links (UC-029); keyed on `bookId` |
| `/read/:bookId/:chapterId` | Chapter text, read-only; keyed on `chapterId` |
| `*` | Not-found page — static copy that discloses nothing about the attempted address |

**Both routes are built (feature `022.reader-mode`).** The pre-022 `read` entry — a table-of-contents placeholder with no router and no gate, landed with feature 010 so the fifth Rollup input and the `spaFallback` branch had something to serve — is gone.

**There must never be a third *content surface*.** UC-029's exclusion list is the spec: no codex, notes, flags, book state, settings or chat, ever. The rule is about what a reader can **see**, not about how many `<Route>` elements the table has — the **terminal `*` catch-all is required**, not an exception carved out of the rule, because it renders a page that shows nothing about the book and reveals nothing about the address that missed. This document previously stated the constraint as *"two routes, and there must never be a third"*; as built there are three `<Route>`s and the constraint is unbroken, so the wording is corrected here rather than left to read as drift.

**Which chapters appear** is `authorization.md` → "The reader surface": written chapters only, with a chapter vanishing from the table of contents for the duration of a close run as an accepted, product-recorded cost.

#### `src/read/`, as built

`readGate.ts`, `main.tsx`, `App.tsx`, `routes.tsx`, and `pages/` holding the table-of-contents page, the chapter page and the not-found page — each page component with its adjacent state file, per the house shape (`frontend.md`).

- **The gate is auth-only** and a verbatim structural mirror of `work/workGate.ts`, redirecting to `/login/`. **There is no book-level pre-check on the client** (design-note D8): the backend already refuses a book the caller may not read with a `404`, and a client pre-check would duplicate a rule that has exactly one implementation. Membership is not in the JWT either, so the pre-check would cost a probe request on top.
- **The gate runs outside React, before `createRoot`**, matching `work/`'s bootstrap.
- **`App.tsx` uses `<BrowserRouter basename="/read">`**, never `createBrowserRouter`.
- **A member navigating to `/read/:bookId` gets the reader view** (D1) — no redirect into the workspace. `Capability.read_book` already admits owner, co-author and reader, so it works for free and doubles as an author's "preview as a reader" path.
- **The chapter body renders through `react-markdown`, with no plugins and no `components` prop** — inherited from the content pane's existing call below, not re-decided (D11). **`@mantine/tiptap` and every save/edit control are absent from `src/read/` entirely**, which is what makes "does a reader have an edit affordance?" answerable at build time without running the app. Stated honestly: that property has **no automated enforcement** beyond inspection and `npm run build` — a future shared component that transitively imported the editor would slip past the test suite.
- **Refusal copy is chosen in the load functions, not the components** (D9), per `frontend.md`'s state/component split. The not-found copy deliberately does **not** speculate about which of the five collapsed refusal sources fired.

## The working page

Three regions:

```
┌──────────────┬────────────────────────────┬─────────────────────┐
│  Navigator   │       Content pane         │     Chat pane       │
│              │       <Outlet/>            │                     │
│ Book state   │   a LIST  ── or ──  an     │  header · popovers  │
│ Characters   │                    ITEM    │  transcript         │
│ Locations    │   (codex: realized)        │  thinking block     │
│ Facts        │                            │  tool-call trace    │
│ Chapters     │   draft-until-saved        │  composer           │
│ Variants     │   restore buffer per item  │                     │
│ Chats ───────┼──► the chats LIST ─pick──► │  the picked chat    │
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

- **Book state** is the **landing view** (UC-091, US-106.AC-1) — the first thing shown on opening the book to work. It aggregates the book's own fields, and per chapter: title, summary (UC-089), after-chapter note changeset (UC-049/UC-051), and any active **flags** in context (FEAT-016).
- **Characters / Locations / Facts** are the one `CodexEntry` table filtered by `kind` — a fixed taxonomy, not three entities.
- **Chapters** is read/write prose; Book state is the continuity picture. Product records the overlap as accepted and deliberate, not duplication.
- **Variants** is an addition to the product-final list — see "Divergence" below.
- **Chats** renders its **list** into the content pane like every other entry (UC-090 step 2), and only a **picked** chat opens in the **chat pane** (UC-090 step 5, US-105.AC-5). It is an **ordinary router link** — feature `023.chat-ux-revision` removed the pane-control exception, and the route map above carries the decision history.

#### What each section actually shows today

The navigator was built whole at feature 010 with **one** section carrying data and every other one a labelled empty state naming its owner. Three features have filled sections since; the current state is:

| Section | State |
|---|---|
| Book state | **has data** — the book's own fields and members (feature 010), the caller's own system prompt (feature 021), and the live state notes plus per-chapter continuity (feature `016`) |
| Characters / Locations / Facts | **has data** (feature 013) |
| Chats | **has data** — the list is a content-pane page (feature `023`); a picked chat opens in the chat pane (feature 011) |
| Chapters | **has data** (features `014`, `015`, `016`) — the ordered skeleton with add / remove / reorder, the sketch editor, the caller's own chapter prompt, the `open` chapter's body editor with its state transitions, and the close procedure's surfaces |
| Variants | labelled empty state — owner `018.chapter-history-variants` |

**Book state's deferral is closed (feature `016.chapter-close-continuity`).** **US-106.AC-2/AC-3** — per chapter, its title, summary, after-chapter note changeset and active flags — shipped, and the two labelled empty states this document recorded as blocked ("no chapter, summary or flag endpoint exists to aggregate") now have endpoints behind them. The view carries two things: the book's **state notes**, viewable by any member and editable per collaboration mode (UC-049/UC-050), and a **per-chapter continuity list** (UC-051, UC-089, UC-091). Feature 010's record that the landing view aggregated the **book's own fields only** is retained above as history; it was true of that feature and is no longer true of the page.

A labelled empty state naming its owning feature is the convention, not a placeholder oversight: the navigator's shape is fixed by UC-090 and building it whole once is cheaper than growing it seven times, but an unlabelled blank pane reads as a bug.

**"Flag" is the word, on screen and in the code.** The entity, table, DTOs and API say `flag` (`domain-continuity.md`) and so does every string the author reads. Round 6 had made **"warning"** the author-facing term and this document recorded that mapping from the UI side; **product reversed it on 2026-07-31** (`docs/product/features.md` → FEAT-016, *"Reversed 2026-07-31"*, `[confirmed: user]`), so the split is gone and FEAT-016's parked reconciliation is resolved by not renaming at all. The reversal is recorded rather than quietly applied, because the split was a deliberate decision and dropping it is another one. The **verb** survives untouched: the consistency check *warns* and never blocks.

### Content pane — subject and editability

The pane holds **either a list or a single item** (UC-090, UC-083). A loaded subject is editable or read-only by one rule:

| Subject | Editable? |
|---|---|
| The book's **`open`** chapter | **partly editable** — its **body text** (US-097.AC-3) and the caller's own chapter system prompt; its **`sketch` is read-only** (UC-033 confines sketch edits to `planned`) |
| A chapter in **`closing`** | **read-only** — a close run is streaming continuity drafts against this exact body (`domain-chapter.md`) |
| A **`planned`** chapter | **partly editable** — its `sketch` (UC-033) and the caller's own chapter system prompt; its `text` is **read-only** (US-097.AC-1) |
| A **`closed`** chapter | **read-only** (US-097.AC-1) |
| A codex entry, not archived | editable, per collaboration mode (US-079) |
| Book state | state notes editable (UC-050) **and the caller's own system prompt** (feature 021); everything else read-only |
| Any list | read-only |

**The table gained its first *partial* row (feature `014.chapter-skeleton`), and the shape it uses is the one to copy.** A `planned` chapter is editable in two regions and read-only in the one the table was originally written about. It needed a partial row because **US-097.AC-1's read-only rule is about the chapter's body**, and the sketch is editable in exactly the *opposite* window from the body: the sketch only while `planned` (UC-033), the body only while `open`. One verdict per subject could not express that.

As built, in `src/work/subject.ts`:

- **`Editability` gained an optional `editableRegions?: EditableRegion[]`** — `editable` stays a single verdict and was **not** turned into an array.
- **`EditableRegion` gained `"chapter-sketch"` and `"chapter-own-prompt"`.**
- **`WriteRegion` was *not* widened.** A chapter **body** write is still `checkWritePermission(subject, "whole")`, so `checkWritePermission` still refuses a body write on a `planned` chapter and the shared-canvas symmetry (US-097.AC-2, US-059.AC-3) is untouched — the assistant and the author are still refused by the same rule.
- **The invariant when `editableRegions` is absent:** the editable set is `editable === "none" ? [] : [editable]`. Every existing row keeps its meaning unchanged, which is what makes the field additive rather than a migration.

A later subject needing a partial row **copies this shape** — an optional region list beside the verdict — rather than turning `editable` into an array.

**The `open` row became region-explicit too (feature `015.chapter-writing-free-mode`).** "The open chapter is editable" was ambiguous the moment `014` made the `planned` row partial, so the `open` row now names its regions in the same vocabulary: the **body text** is editable and the caller's own chapter prompt stays editable, while the **sketch is not** — UC-033 confines sketch edits to `planned`, which is the exact **opposite window** from the body. An editable region that is not in this table is drift.

`src/work/subject.ts` remains the **single enforcement point**: `checkWritePermission` now **allows** a body write on `open` while still refusing one on `planned`, `closing` and `closed`. The shared-canvas symmetry (US-097.AC-2, US-059.AC-3) is therefore preserved with **the assistant refused by the same rule as the author**.

**A read-only chapter body renders through `react-markdown`, not through a disabled editor.** The heavy editor (`@mantine/tiptap`, `frontend.md`) is mounted **only when the chapter is `open`**, which removes editable-toggling entirely and keeps the read path light. `react-markdown`'s **no-plugin default was inherited, not re-decided**.

**Neither new field enters the draft-until-saved restore buffer.** The buffer exists for large artifacts carrying a version token; the sketch is explicitly **last-write-wins with no version** (no `expected_version`, no `409`, and a sketch edit does not bump `Chapter.version`, which tracks the body only), and the prompt row has exactly **one writer**. Consequently there is **no stale-buffer detection, no divergence view and no `409` path** on either. The exclusion is sanctioned in `frontend-work-drafts.md` → "Sanctioned exclusions", the same way feature 021's was.

**The Book-state row gained exactly one editable region (feature 021).** The caller's own per-author system prompt is editable there; the rest of the view stays read-only. It is deliberately **outside the draft-until-saved restore buffer**: the buffer exists for large content-pane artifacts whose loss is expensive, while this is a short settings field edited from **two** surfaces (here and the Shell's book settings), and buffering it on one but not the other would be incoherent. Consequently the field has **no `baseVersion`, no stale-buffer detection, no divergence view and no 409 path** — the row has exactly one writer, its owner. An editable field missing from this table is drift, and the exclusion is sanctioned in `frontend-work-drafts.md` → "Sanctioned exclusions" the same way the buffer's inclusions are.

**`src/work/subject.ts` is the single enforcement point** for this table — the one place editability is decided, not per-component. That is what makes the symmetry in US-097.AC-2 / US-059.AC-3 hold, and it is why adding `closing` to the chapter state machine cost one row here rather than an audit of every write path. `resolveEditability` returns the verdict and the author-facing read-only reason; `checkWritePermission` is the writer-agnostic gate derived from it.

**It is now wired, and its open note is closed (feature 013).** Written by feature 010 and until then imported only by `restoreBuffer.ts`, `subject.ts` is now the live subject model: `resolveEditability` drives the codex entry page's **read-only banner**, and `LoadedSubject` is what the canvas target registry holds and what the assistant turn request is built from. Its in-code note — that "the free/proposal collaboration-mode nuance is `013.codex`'s to apply" — is **closed**: the nuance is applied **server-side**, where a co-author's write in a proposal-mode book is refused with **403**, so `subject.ts` needed no change at all. The assistant and the author are refused **by the same rule at the same place**, which is exactly what US-097.AC-2's symmetry asked for. A file written for a future feature and then satisfied differently must say so, or its note reads as unfinished work forever.

**Two implementations, two vocabularies, on purpose.** The table now has a second implementation per writable subject: a server-side **mirror** of `frontend/src/work/subject.ts::checkWritePermission`, expressed for the assistant. They speak different languages by design:

| Writer | Refusal lives in | Refusal looks like |
|---|---|---|
| The author's codex save | `services/codex.py` | the **403 / 400 / 409** HTTP taxonomy that service owns |
| The assistant's codex canvas write | `services/codex_tools.py::_refuse_write` | a **tool string the model reads** |
| The author's chapter save / transition | `services/chapters.py` | the **403 / 409 / 422** HTTP taxonomy (`authorization.md`) |
| The assistant's chapter canvas write | `services/chapter_tools.py`'s refusal chain | a **tool string the model reads** |

The assistant's refusal is a string rather than a status because **a raising tool would abort the turn** — the model must be told *no* and allowed to continue, where the author's client must be told *no* and shown why. Same rule, same subject model, two surfaces. `assistant-runtime.md` holds the server half.

**One refusal exists only on the client, and it is the exception that proves the rule (feature `015`).** A **`replace_selection` canvas frame arriving when no selection is active** is refused **at page level**, with **no server-side counterpart** — the tool cannot know that the author cleared the selection while the model was writing. The frame is **not applied**: never appended, never applied at position zero, and the author is told. Do not try to move this into the tool's refusal chain; the information it needs does not exist on the server.

The subject is **independent of the active chat**: loading a chapter does not change which chat is open, and switching chats does not change the subject. Because both sides are persisted — the chapter on the server, the chat on the server, the unsaved draft in the restore buffer — that independence survives navigation and reload rather than depending on either staying mounted.

### The pane's first real pages (feature 013)

The content pane is `<AppShell.Main><Outlet/></AppShell.Main>` and stays that way — **no content-pane state class was introduced.** Each page owns its own state, per the page-is-a-route rule, and the pane itself holds none. Two pages realize the "a LIST — or — an ITEM" shape:

- **`CodexListPage`** — **one parameterized page** serving `/characters`, `/locations` and `/facts`, with the `kind` fixed by the route rather than by a prop the user can change. Three routes, one component, because the three lists differ only in a filter value.
- **`CodexEntryPage`** — serving both `/codex/:id` and `/codex/new?kind=…`, the latter as a blank entry with no row behind it.

This is the pattern chapters and variants follow: a page per route, its own state class beside it, its own load in its own page-level effect, and nothing owned by the pane.

### The chapter surfaces, as built (features 014 and 015)

The chapter **item** page is the pane's **second editable subject** and the **first with a numeric version token** — a different template from the codex entry's, so copy from the right one.

- **Three trios, no aggregation type**: the chapter, its body, and the caller's own prompt each load as their own `<name>` / `<name>Status` / `<name>Error` triple (`frontend.md`).
- **Three editable regions** on one page — sketch, prompt, body — each with its own state window, gated by the editability table above.
- **The remount-by-key idiom for external draft writes.** The third-party editor reads its initial content once, so the page keys it on a counter bumped by every *external* write (assistant apply, undo, buffer restore, reconciliation) and never by a keystroke. The rule and its cost are in `frontend.md` → "React hook rules".
- **It registers itself as a *writable* canvas target**, where `014` registered the chapter as a subject only. The registry is `frontend-work-drafts.md`'s.

#### The close procedure's surfaces (feature `016.chapter-close-continuity`)

Three additions to the same chapter item page, all reusing surfaces that already existed rather than adding a route or a navigator entry (design-note D8):

- **A Flags section** — the chapter's flags, with raise and resolve. Raise is `{owner, co_author}`, resolve is owner-only (`authorization.md`); the client mirrors that to show or hide the control and the server re-checks, per the `can_reorder` precedent.
- **The `close` transition control became the close-procedure trigger**, behind a **confirmation dialog**. The confirmation is not decoration: close now posts an assistant turn that writes continuity and may end with the chapter closed, and this is the last point at which the author can decline without cancelling something already running.
- **The verbatim `closing` placeholder became an in-progress view** with a cancel control. `offeredTransition` for a `closing` chapter is now `"cancel"` where it used to be `null` — **Stop is the cancel**, and there is no other exit from `closing` (`domain-chapter.md`).

**A closed chapter also gained a read-only summary and changeset**, which puts the close run's output where it was produced rather than only on Book state.

**The chat composer is read-only for the whole `closing` window**, driven by `closeTurn.ts`'s stored active value rather than by "a stream is running" — so a reload mid-close still renders it read-only with no stream running. The module and its sanction are `frontend-work-drafts.md`'s.

**The settings-side mirror was deliberately not built.** The Shell's `/books/:bookId/continuity` route stays unbuilt: the working-page surfaces satisfy UC-051 and UC-089 on their own, and this document's one-editing-surface rule already makes the Shell copy a **read-only convenience** rather than a requirement. Building it would have doubled the feature's surface area for a view nobody is blocked on. It remains designed — see the Shell route map above — and unbuilt.

### Chat pane (feature 011, reshaped by feature `023.chat-ux-revision`)

The slot is no longer empty. Feature 010's `ChatPaneSlot` placeholder is gone — the slot is now a one-line adapter onto the real pane, and the pane's parts live in `src/work/components/chat/`:

| Part | Role |
|---|---|
| `ChatPane.tsx` | the pane itself — header, the model and settings **popovers**, and the "+" that creates a chat |
| `ChatSettingsPanel.tsx` | per-chat model and sampling, rendered inside the settings popover |
| `MessageList.tsx` | the transcript, plus the in-flight bubble while a turn streams |
| `ThinkingBlock.tsx` | the collapsible reasoning region |
| `ToolCallTrace.tsx` | the turn's tool calls, per message (feature `024`) |
| `Composer.tsx` | the prompt input with its in-input send / stop control and the retry banner |
| `chatPaneState.ts` | the pane's single state class |

**`ChatList.tsx` left this table at feature `023`.** It belongs to the chats list page now (`pages/ChatsListPage.tsx` + `chatsListPageState.ts`) — the pane's own list, rendered in the content pane like every other list. **There is no in-pane chat list, no inline new-chat form, and no "Save settings" button anywhere in the tree**; each of the facts below follows from one of those three removals.

**A "+" creates a chat instantly, with no form.** The new chat inherits the active chat's model pair, or the first available option when there is none, so the author never fills a form to start typing. It is **refused with an author-facing message when no model is available at all** — UC-053's exception flow (US-056.AC-4/AC-5) — because a chat with no model is a chat that cannot take a turn.

**The pane controller seam.** `WorkspaceShell` registers a **module-level controller** (`src/work/chatPaneController.ts`) so the chats list page can open a chat in the pane **without a route change**; the page never touches `ChatPaneState`. The controller **moves the active-chat pointer *and* loads that chat's transcript** — two calls, not one. The plan sketched it as a single `pickChat`, and pointer-only would leave the previous conversation on screen under the new chat's header; the two-call shape is the contract, so the sketch is not later read as authoritative. The module tier it joins is `frontend-work-drafts.md`'s.

**One `openedPanel` discriminator drives both header popovers.** The pane holds `"model" | "settings" | null`, so opening one closes the other **by construction** rather than by a handler that remembers to close its sibling — and an accepted send clears it.

**Settings are flushed before the turn stream opens.** A dirty settings draft is persisted first; a **failed flush aborts the send** with an author-facing error and opens **no** stream. The reason is not client tidiness: the backend's turn preparation reads the chat's **stored** model pair (`assistant-runtime.md`), so client and server must agree *before* the turn starts, or the turn runs on a model the author did not pick.

**A consequence worth stating plainly.** With the Save-settings button gone, that send-time flush is **the only path in the whole app that persists a model change**. A model or creativity change the author makes and never follows with a message is **lost on reload** — design-note D8's accepted trade-off, and an **open `_TBD:` on UC-081** in `docs/product/` as of 2026-08-10. The visible symptom is that the header's model label lags the author's pick until a message is sent; that is **feedback round 3 / F5, open and unbuilt as of 2026-08-10**. No decision is recorded here, deliberately — the as-built behaviour above and the open question are the whole of it.

**The pane's vertical contract, stated because feature 023's feedback round 1 found it broken.** The aside is fixed-height, the pane root fills it, the **transcript is the single growing child** (`flex: 1` **plus `minHeight: 0`**), and the composer is **non-shrinking**. The `minHeight: 0` is **required, not defensive**: Mantine's `AppShell.Aside` is already a flex column, so the pane root is already a flex item whose automatic minimum would otherwise be its own content height. Provenance, honestly: the 320px transcript cap and the missing chain were **011-era**, hidden by the bulk that 023 removed; 023 owns the repair because it owns the pane's current shape. A pane change that breaks this chain breaks it silently — jsdom has no layout engine, so no test will catch it.

**The composer's send control is an icon inside the input's bottom-right corner**, with Send and Stop swapping in **one slot** (feedback round 2). 011's description of a Send `Button` in a row below the textarea is stale. The accessible names `Send` / `Stop` are the only handle on an icon-only control, which makes them a **test contract, not decoration**. The Mantine mechanics are in `frontend.md` → Mantine inventory.

**Chats are titled automatically** from their own content (UC-101, US-119) — the trigger and the swallow-on-failure policy are `domain-chat.md`'s and are not duplicated here. **The transcript shows the assistant's tool calls** (UC-102, US-120) — the wrapper that produces them is `assistant-runtime.md`'s.

**One state instance, owned by the shell.** `WorkspaceShell` owns the `ChatPaneState`, starts its load in its existing mount effect, and passes the instance down; since `023` the navigator receives **nothing at all** for chats — its entry is a link — and the only cross-component seam left is the controller registration above. The full pattern and its reasoning are in `frontend.md` → Components, because it is a general rule with a worked example here rather than a workspace-specific arrangement.

**The pane is a client of the assistant, not its design.** Prompt composition, the tool loop, mode gating and the **seven-frame** SSE vocabulary (`thinking` / `delta` / `done` / `error` / `canvas` / `tool_call` / `tool_result`) are in `assistant-runtime.md`. What this document fixes is that the pane exists, that a picked chat opens in it, and that a chat is independent of the content-pane subject.

#### Three known defects and one known gap

Recorded once rather than rediscovered, following `assistant-runtime.md`'s precedent:

1. **An unresolvable saved model option silently clears the chat's model pair.** The settings save resolves the draft's chosen option against the loaded options and falls back to a **null pair** when nothing matches — so when a chat's stored pair names a server or model that is no longer offered (server deactivated, model removed), a temperature-only edit reads as dirty and the flush writes an **empty** pair, clearing the chat's own model immediately before the turn that depends on it. **Pre-existing 011 behaviour**: 023's dirty-check closed the unseeded-draft door but not this one, so 023 added a **second route to the defect, not the defect**. Worth hardening — an unresolvable option should arguably leave the stored pair alone.
2. **An archived chat picked from the list opens an empty pane.** The pane loads only non-archived chats while the list page loads both, so an archived pick points the active-chat id at a chat the pane has no row for. Out of scope in 023, and **`docs/product/` now records it as a `_TBD:` on UC-081** — restore-only archived view, or a pane that fetches any picked chat.
3. **The settings popover surfaces no temperature validation message.** The pane's error computed still derives its temperature message from the *new-chat* draft, while its only remaining consumer edits the *settings* draft. Pre-existing 011 behaviour, deliberately left alone.

**Gap: the transcript does not auto-scroll to the newest message**, and it is now conspicuous — before the flex repair the region was capped and rarely the thing that scrolled; now it fills the pane and a streaming turn writes below the fold with no follow. Deliberately out of scope for 023 (new behaviour, not a repair). `frontend.md` already sanctions the mechanism: **one `autorun` in the pane-level mount effect**, never a `useEffect` in the transcript leaf.

**`ChatPaneState` holds no book id, and pane-level predicates must be written accordingly (feature `016`).** The shell remounts the pane per book (`key={bookId}`), so the pane **is** book-scoped — by remount, not by a stored value. A predicate phrased as *"does X's book match the pane's"* therefore has nothing to compare against and cannot be implemented; the correct phrasing for anything the pane must react to is **"is X active at all"**. Feature `016`'s composer read-only rule is written that way for exactly this reason, and the next cross-pane signal should be too. This is the same shape as `ChatPaneState` holding no subject field and no selection field (`frontend-work-drafts.md`): the pane reads module state at the moment it needs it, and mirrors nothing.

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
- **The assistant's internals.** They are no longer undesigned — `assistant-runtime.md` and `assistant-config.md` hold them — but they are not this document's. What remains genuinely undesigned there (context assembly, scoped checks UC-088, token budgets, token-level canvas streaming) is bounded in those files, not here. **The shared-canvas protocol for chapters is no longer on that list** — it shipped with feature `015.chapter-writing-free-mode` and is in `assistant-runtime.md`.
- **The admin moderation view** (FEAT-011, Stage 6) — an Admin SPA surface, not one of these entries.
