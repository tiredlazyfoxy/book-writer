# Authorization — the book-scoped permission model

**Realizes:** FEAT-006, FEAT-007, FEAT-011, FEAT-015, FEAT-017, FEAT-020; UC-021..030, UC-035..037, UC-041, UC-042, UC-043, UC-050, UC-060, UC-061, UC-062, UC-064, UC-068, UC-069..075, UC-095..097

Every book-domain capability is gated on the caller's relationship to **one specific book**. This document defines the roles, the enforcement point, and the capability × role matrix. It assumes the book-domain entities — start at `domain-model.md` (the index), with `domain-book.md` for `Book` / `BookMember` and `domain-chapter.md` for the write path.

Authentication itself — JWT, per-user signing key, bcrypt, the `require_role(admin)` dependency — is unchanged and lives in `backend/auth-ids.md`. This document is only about *authorization within a book*.

## Roles

| Role | Product actor | Where it comes from |
|---|---|---|
| **Owner** | ACT-004 | `Book.owner_id == user.id`. Exactly one, always |
| **Co-author** | ACT-005 | a `BookMember` row for `(book, user)` |
| **Reader** | ACT-006 | **no row at all** — derived from `Book.visibility == public` |
| **Admin** | ACT-001 | `User.role == admin`. Reaches book content **only** through the FEAT-011 moderation view |

**Member** means owner **or** co-author. It is the unit almost every rule below is written in.

**Reader access is derived, not granted.** There is nothing to add and nothing to revoke: flipping `Book.visibility` to `public` makes every logged-in non-member a reader, and flipping it back removes them. Modelling readers as rows would mean maintaining a membership set that mirrors a single boolean, and would leave the two able to disagree.

**Public means read-only to any *logged-in* user, never anonymous** (UC-029, challenge C4). There is no anonymous surface anywhere in the system.

## Enforcement — resolve in a dependency, decide in a service

Two steps, deliberately split:

```
routes/  ──►  Depends(book_access(book_id))  ──►  BookAccess      (who am I, to this book?)
   │                    │
   │                    └── reads db/books + db/book_members
   ▼
services/ ──►  authz.require(access, Capability.X)                 (may I do this?)
   │
   ▼
db/
```

**Step 1 — a FastAPI dependency resolves a typed book-access context.** It answers *identity relative to this book* and nothing else: does the book exist, what is its state, its visibility, its collaboration mode, and what is this caller to it. It lives alongside the existing `require_role` dependency, and reads through `db/` (the `routes → db` edge is already sanctioned in `backend.md`).

```
BookAccess:
    book_id            : int
    user_id            : int
    role               : owner | co_author | reader | admin | none
    book_state         : active | archived | quarantined | destroyed
    visibility         : private | public
    collaboration_mode : free | proposal
```

It is a typed structure, not a dict, per the no-free-dictionaries rule (`backend.md` → "Typing discipline").

**Step 2 — the capability check itself lives in `services/`.** `routes/` is HTTP-only by the enforced layer rule: parse, call a service, return. "May a co-author apply a proposal?" is business logic, and putting it in a route handler would be exactly the violation that rule exists to prevent. A single `services/authz.py` holds the capability table and one `require(access, capability)` entry point, so every service that guards something guards it the same way and the matrix below has one implementation.

**Why not push the whole check into the dependency?** Because a route often needs the access context for more than one decision (load the chapter, then decide whether this caller may write to it), and because a dependency that raises on capability would have to know which capability the route is about — which means encoding business rules in the route's signature. Resolving once and deciding in the service keeps the layer rule intact and makes the check testable without HTTP.

**Why resolve in a dependency rather than in each service?** Because the resolution is request-scoped, identical for every book endpoint, and needs the same DB reads every time. Doing it once per request in one place also means the "book does not exist / caller cannot see it" answer is produced in exactly one place, which is what makes the existence-hiding rule below reliable.

### As delivered — the spine

Feature **`009.books`** (`docs/plans/009.books/`) is the **first implementation** of both halves: the `book_access` dependency that resolves `BookAccess`, and `services/authz.py` holding the `_CAPABILITY_MATRIX` and its single `require(access, capability)` entry point. What it populated is the owner-only lifecycle/settings rows of the matrix below, plus the reader `read_book` rows. Every book-scoped route family shipped since binds to that spine rather than re-deriving a check.

Two parts of the resolver remain deferred to **FEAT-011**: **`admin` role resolution** (nothing resolves a caller to the `admin` role in the book-access sense yet) and the **quarantined / destroyed gates** in "Book state and visibility gates" below. Both are moderation-side, and FEAT-011 is Stage 6.

### No `chapter_access` dependency — deliberately

**There is no chapter-level access resolver, and there is not meant to be one.** The chapter routes nest under `/api/books/{book_id}/chapters/…` **precisely so that `book_access` binds unchanged** to the `{book_id}` path parameter (feature `014.chapter-skeleton`). Each chapter service then verifies `chapter.book_id == access.book_id` itself and raises its own not-found reason for a chapter that does not exist or belongs to another book.

The alternative — a `chapter_access` dependency that resolved a chapter to its book — would put the existence-hiding rule in a **second** place, which is exactly what "resolve once, in one dependency" above exists to prevent: two resolvers means two chances for the `404`-vs-`403` answer to drift. Nesting the route costs one path parameter and keeps the resolver singular.

Recorded because `014`'s brief asked how a chapter resolves to its `book_id`, and the answer — *don't build a resolver, nest the route* — is one every later chapter feature would otherwise ask again.

## Capability × role matrix

`—` = refused. Where a row says *mode*, the book's `collaboration_mode` decides whether a co-author's change applies immediately (free) or is held as a proposal for the owner (proposal).

### Book lifecycle and settings — owner only

| Capability | Owner | Co-author | Reader | Admin |
|---|---|---|---|---|
| Create a book (UC-021) | any author | — | — | — |
| Transfer ownership (UC-024) | ✓ | — | — | — |
| Reassign ownership of a **disabled** owner's book (UC-025) | — | — | — | ✓ |
| Archive a book (UC-023) | ✓ | — | — | — |
| Add / remove a co-author (UC-026, UC-027) | ✓ | — | — | — |
| Set visibility (UC-028) | ✓ | — | — | — |
| Set collaboration mode (UC-042) | ✓ | — | — | — |
| List own books (UC-022) / shared books (UC-030) | ✓ | ✓ | — | — |

### Chapters

| Capability | Owner | Co-author | Reader | Admin |
|---|---|---|---|---|
| Add a chapter (UC-031) | ✓ | ✓ | — | — |
| Edit a planned chapter's sketch (UC-033) | ✓ | ✓ | — | — |
| Remove a planned chapter (UC-034) | ✓ | ✓ | — | — |
| **Set chapter order (UC-032)** | ✓ | — | — | — |
| **Open / close / reopen a chapter (UC-035..037)** | ✓ | — | — | — |
| **Approve continuity at the close gate (UC-048)** | ✓ | — | — | — |
| Write into the open chapter (UC-038) | ✓ | ✓ *(mode)* | — | — |
| Submit proposed changes (UC-040) | n/a | ✓ | — | — |
| **Apply proposals (UC-041)** | ✓ | — | — | — |
| Read chapter text | ✓ | ✓ | ✓ *(public only)* | via moderation view |

#### The chapter skeleton capabilities, as built

Feature `014.chapter-skeleton` added the **four `Capability` members** that back the first four rows above. Until then those rows were a matrix on paper with no enum behind them:

| Capability | Owner | Co-author | Reader | None |
|---|---|---|---|---|
| Add a chapter (UC-031) | ✓ | ✓ | — | — |
| Edit a planned chapter's sketch (UC-033) | ✓ | ✓ | — | — |
| Remove a planned chapter (UC-034) | ✓ | ✓ | — | — |
| **Set chapter order (UC-032)** | ✓ | — | — | — |

**Set chapter order is owner-only, which is what US-033.AC-2 requires**; the other three are `{owner, co_author}`.

**The two read paths reuse the existing `read_book` capability unchanged** rather than minting a chapter-read capability of their own — "Read chapter text" in the table above *is* that row, and a second capability meaning the same thing would be two rules to keep in step.

#### The last two chapter rows get an enum behind them (feature `015.chapter-writing-free-mode`)

Feature `015` added the **two remaining `Capability` members**, so the chapter matrix is now fully backed by code:

| Capability | Owner | Co-author | Reader | None |
|---|---|---|---|---|
| **Open / close / reopen a chapter (UC-035..037)** | ✓ | — | — | — |
| Write into the open chapter (UC-038) | ✓ | ✓ *(mode)* | — | — |

**One member for the one matrix row** on the transitions — the three verbs share a row, so they share a capability, matching the 1:1-with-the-matrix discipline `014` used.

**The `(mode)` qualifier on the write row is layered in `services/chapters.py`, not in the matrix.** This is now the **third** feature to layer a non-role rule on top of the matrix, after `011.chat-panel` and `013.codex`; what this document already called "a pattern rather than a one-off" is now the house shape.

Chapter rules that are **state-machine constraints, not authorization** apply even to the owner. They are all **`409` and not `403`**, because the caller *has* the capability and the **resource is in the wrong state** — pinned here so that a later feature does not "fix" them to `403`:

- a chapter in `closing` **refuses writes**;
- a **reopen is refused while any chapter is `open` or `closing`** (CF1);
- a **non-`planned` chapter refuses a sketch edit and a removal** (feature `014`);
- **reordering is allowed while a chapter is `open`** (feature `014`, closing UC-032's `_TBD:`), because a reorder touches `ordinal` only — it never reads or writes a body, never changes a `state`, and never bumps `version`;
- a **body write to a chapter that is not `open`** (feature `015`);
- a **stale `expected_version`** on a body write (feature `015`);
- **opening a non-`planned` chapter**, **reopening a chapter that is not `closed`**, and **closing a chapter that is not `open`** (feature `015`);
- **opening or reopening while any chapter is `open` or `closing`** (feature `015`) — CF1's rule applied to **both** transitions, by the symmetry the product's UC-035 exception flow states.

Being the owner does not bypass any of them. See `domain-chapter.md`.

Status codes the five new chapter routes produce, mirroring the codex table below:

| Situation | Status |
|---|---|
| No token | **401** |
| Private book with no relationship | **404** — existence hiding, produced by `book_access`, **not re-derived** |
| A chapter that does not exist, or belongs to another book | **404** — the same answer, raised by the service |
| A capability failure, and any reader | **403** |
| A **co-author in a `proposal`-mode book** | **403** — typed reason naming FEAT-010 as unbuilt |
| An **archived** book | **403** — see "Book state and visibility gates" |
| Every state-machine and version refusal above | **409** |
| A malformed body | **422** |

### Members-only material — codex, notes, summaries, flags

**ACT-006 never sees any of it, even on a public book.** UC-029 is explicit: a reader gets the table of contents and chapter text, and nothing else — no codex, notes, flags, book state, settings or chat. US-085 states the codex exclusion as its own criterion.

| Capability | Owner | Co-author | Reader | Admin |
|---|---|---|---|---|
| Browse / search the codex (UC-071) | ✓ | ✓ | — | via moderation view |
| Create / edit / archive a codex entry (UC-069, UC-070, UC-072) | ✓ | ✓ *(mode)* | — | — |
| View / restore entry history (UC-073, UC-074) | ✓ | ✓ *(mode)* | — | — |
| Copy entries from another book (UC-075) | ✓ | ✓ — **and a member of the source book** | — | — |
| View state notes / a chapter changeset (UC-049, UC-051) | ✓ | ✓ | — | via moderation view |
| Edit state notes (UC-050) | ✓ | ✓ *(mode)* | — | — |
| View a chapter summary (UC-089) | ✓ | ✓ | — | via moderation view |
| Raise a flag (UC-067) | ✓ | ✓ | — | — |
| **Resolve a flag (UC-068)** | ✓ | — | — | — |
| **Run a consistency check (UC-064)** | ✓ | — | — | — |

#### The codex capabilities, as built

Feature `013.codex` added **two `Capability` members** and the matrix rows behind them — the first rows of this table with code behind them:

| Capability | Owner | Co-author | Reader | None |
|---|---|---|---|---|
| Browse / search the codex (UC-071) | ✓ | ✓ | — | — |
| Create / edit a codex entry (UC-069, UC-070) | ✓ | ✓ | — | — |

**The `(mode)` qualifier in a co-author cell is not expressible in `_CAPABILITY_MATRIX`.** The matrix maps **capability → role set** and has **no vocabulary for the book's collaboration mode**, so the mode rule lives one layer up, in `services/codex.py` — the same layering feature `011.chat-panel` used for chat row-ownership. That is now a **pattern rather than a one-off**: two features have layered a non-role rule on top of the matrix rather than widening the matrix to carry it. Widening it would mean every capability lookup grew a dimension that almost no capability uses, and the two features that needed one needed *different* extra dimensions (mode, and row ownership).

Status codes the four codex routes produce:

| Situation | Status |
|---|---|
| Non-member of a **private** book (all four routes) | **404** — existence hiding |
| Reader of a **public** book | **403** — the book is legitimately visible, the codex is not |
| Co-author writing in a **`proposal`-mode** book | **403** — typed reason naming FEAT-010 as unbuilt (`domain-codex.md`) |
| Stale `modified_at` on an edit | **409** |
| Kind/name violation, or an edit to an archived entry | **400** |

**Archive (UC-072) is not part of this** — feature `013.codex` added no archive capability and no archive route; it is `017.codex-archive-restore`'s. The matrix row above that pairs archive with create/edit predates the split and should be read as the *design*, not as shipped code.

### Cloning

| Capability | Owner | Co-author | Reader | Admin |
|---|---|---|---|---|
| Clone a **private** book (UC-061) | ✓ | — | — | — |
| Clone a **public** book (UC-062) | ✓ | ✓ | — | — |
| Choose which members carry over (UC-063) | whoever clones | whoever clones | — | — |

**Only the owner may clone a private book** (challenge C21, stated in both FEAT-007 and FEAT-015). A co-author's clone makes them the new book's owner (US-068) — accepted deliberately in product (challenge C23).

Note the resolution recorded as finding R4-2: cloning a public book is a **co-author** capability (ACT-005, a member), not a reader one. ACT-006 has no clone use case, and the members-only codex is therefore never exposed by a clone.

### Chats and per-author prompts — three row-ownership rules

Some rows belong to **one member**, not to a role. The matrix cannot express that: it maps **capability → role set** and has **no notion of "author of this row"**. All three rules below are therefore enforced one layer up — the `book_access` dependency establishes *membership*, and the owning service then scopes the row. **No `Capability` member and no `_CAPABILITY_MATRIX` row was added for any of them.**

One such rule reads as a special case, two read as a pattern; **three make it the house shape**. The next feature that needs one should copy the shape from here rather than inventing a matrix concept for it.

**Chats — `Chat.author_id`.** A chat is **private to its author**, including from the book's owner (US-061.AC-1). No role reaches another user's chat. Only the *saved output* of a chat is shared (US-061.AC-2). Enforcement is a **service-level ownership check in `services/chats.py`, layered over the `book_access` dependency** (feature `011.chat-panel`). A chat belonging to **another author answers `404`, not `403`** — the same existence-hiding reasoning as a private book under "Failure modes" below: a `403` would confirm that the chat exists and whose it is, which is precisely what US-061.AC-1 is protecting.

FEAT-020's admin-only assistant configuration is **consumed inside an author's own chat**, gated by this same ownership rule — exactly as the FEAT-020 section below predicts. The admin shaped how the assistant behaves; the author runs it on their own material.

**Per-author system prompts — `BookAuthorPrompt`** (feature `021.per-author-system-prompt`, `domain-book.md`). **Every member owns exactly one prompt per book and may read and write only their own.** Nobody — **including the owner** — reads or writes another author's. The `book_access` dependency establishes membership, then the service **scopes every read and write to `access.user_id`**; there is no route shape in which a caller can name someone else's row.

The route pair `GET` / `PUT /api/books/{book_id}/system-prompt` produces:

| Situation | Status |
|---|---|
| No token | **401** |
| Private book the caller has no relationship to | **404** — produced by `resolve_book_access`, **not re-derived** in the service |
| Logged-in **non-member** of a book they can see | **403** |
| Member acting on their **own** prompt | **200** |

Producing the `404` in the resolver rather than in the service is what keeps existence hiding to one implementation, per "Enforcement" above.

**Per-chapter prompts — `ChapterAuthorPrompt`** (feature `014.chapter-skeleton`, `domain-chapter.md`). The same rule, one level down. **Every member owns exactly one prompt per chapter and may read and write only their own**; nobody — **including the book's owner** — reads or writes another author's. The `book_access` dependency establishes membership against the `{book_id}` the route nests under, the service **scopes every read and write to `access.user_id`**, and it **separately verifies `chapter.book_id == access.book_id`** — the two checks answer different questions and neither substitutes for the other.

The route pair `GET` / `PUT /api/books/{book_id}/chapters/{chapter_id}/system-prompt` produces:

| Situation | Status |
|---|---|
| No token | **401** |
| Private book the caller has no relationship to | **404** — produced by `resolve_book_access`, **not re-derived** in the service |
| Chapter that does not exist, or belongs to another book | **404** — the same existence-hiding answer, raised by the service |
| Logged-in **non-member** of a book they can see | **403** |
| Member acting on their **own** prompt | **200**, including when no row exists yet |

**The chapter's state machine does not gate it.** A prompt is readable and writable on a chapter in `planned`, `open`, `closing` *or* `closed`. The state machine governs **chapter content**; this is the author's instruction to their own assistant, and closing a chapter does not close the author's ability to say how they want to be helped with it.

**Collaboration mode does not apply to a prompt** — either level. A prompt is an author's instruction to **their own assistant**, never book content, so there is nothing for an owner to review and no proposal state to hold — unlike a codex entry or a chapter block, whose text lands in the book. This is why both rules are row ownership and not *(mode)*-qualified capabilities.

## The admin boundary

**An admin never participates in a book through the authoring interface** — in any collaboration mode, at any visibility, on any book, including one they could otherwise reach. FEAT-011 states it and this design enforces it structurally rather than by convention: the book-domain services check `BookAccess.role` against the matrix above, and `admin` is **not** a member role in that matrix. An admin calling an authoring endpoint is refused exactly as a stranger is.

The one place an admin reaches book content is the **FEAT-011 moderation read view** (UC-043): read-only, whole-book, including the codex, on any book regardless of visibility, plus quarantine (UC-044) and destroy (UC-045). That surface is a separate route tree behind the existing `require_role(admin)` dependency, and it does not share endpoints with the authoring API.

**Why structural rather than "admins can do anything":** the product rule is not a courtesy, it is the point of the role split — an admin is a platform operator, not a co-author, and an admin who could write into a book would make authorship attribution (US-040.AC-2) unreliable. A single "admin bypasses all checks" branch would silently undo that everywhere at once.

UC-025 (reassigning a disabled owner's book) is an admin capability over the book's *ownership record*, not over its content, and lives on the moderation/admin side for the same reason.

## Global assistant configuration (FEAT-020) — admin only

**The FEAT-020 assistant configuration — modes, sub-agents, the tool selections and the mode↔sub-agent links — is admin-only, system-global, and never enters the book-access model.** It sits behind the existing `require_role(admin)` dependency, the **same configuration class as LLM servers** (FEAT-004): a platform-wide setting, not a per-book one. It is **not** a `BookAccess` capability and appears in no row of the matrix above — there is no book to resolve a role against.

**Authors never view or configure it**, in any collaboration mode, at any visibility. This is the **same admin-interface-only pattern as FEAT-011's moderation view**, and it is **not a breach of "an admin never participates in a book"** (above): configuring how the assistant behaves is **global assistant config, not book participation**. The admin is not writing into, moderating, or reading any specific book by editing a mode's prompt or creating a sub-agent — they are configuring a platform capability that authors then use inside their own books. Attribution (US-040.AC-2) is untouched, because the admin never becomes an author of any book's content.

The runtime *consumption* of this config (the assistant composing prompts, gating tools, delegating to sub-agents) happens **inside an author's own chat**, gated by the ordinary chat ownership rule (`Chat.author_id`, above) — the author runs the assistant on their own material; the admin only shaped how it behaves. Full config model: `assistant-config.md`; the runtime that consumes it: `assistant-runtime.md`.

**Built as written** (feature `012.assistant-config-editor`): the admin editor implements exactly the rule above — `require_role(admin)`, no `BookAccess` capability, no matrix row, authors never reach it — **with no divergence and no new failure mode**. Stated explicitly so that the absence of an authorization entry for FEAT-020 reads as a match rather than as an oversight.

## Book state and visibility gates

The state and visibility fields gate access **before** the matrix is consulted:

| `Book.state` | Members | Reader (public) | Admin |
|---|---|---|---|
| `active` | matrix applies | read-only if public | moderation view |
| `archived` | matrix applies to **reads**; **every write is refused** — see below | read-only if public | moderation view |
| `quarantined` | **content hidden**; owner is shown the removal notice (UC-046) | hidden | moderation view |
| `destroyed` | **content hidden**; owner is shown the removal notice (UC-046) | hidden | moderation view |

Quarantine makes a book invisible to *everyone including its members* (UC-044) — the owner does not get a partial view, they get the notice instead of the content (UC-046 exception flow).

### An archived book refuses writes — settled by feature `015.chapter-writing-free-mode`

This was carried as an open question through feature `009.books`. It is now decided and implemented: **every chapter body save and every chapter state transition (open / close / reopen) is refused when `BookAccess.book_state` is `archived`. Reads still work.**

**The status is `403`, with its own typed reason — not `409`.** This document places the book-state gate **before** the matrix, alongside visibility and quarantine, and defines `403` as "a book the caller can legitimately see, but a capability they lack". Under archive **no member holds the write capability**, which is an *access* answer, not a resource-state answer. (Contrast the state-machine refusals under "Chapters", which are `409` precisely because the caller does hold the capability.)

**The product basis:** UC-023 says archive preserves content and is reversible. Refusing writes is what makes "preserved" mean something.

**No `Capability` member and no `_CAPABILITY_MATRIX` row was added for it.** The gate is a service-level check over `BookAccess.book_state` — the same layering the `(mode)` qualifier uses, and the same reason: the matrix maps capability → role set and has no vocabulary for book state.

**The assistant is refused by the same rule in the other vocabulary**, reading `ToolContext.access.book_state` and returning a tool string rather than a status (`assistant-runtime.md` → "The shared-canvas write for chapters").

The deferral this replaces named `010` / `014` as "the write features, which are the first to have something to refuse". That naming was wrong and is corrected here: **`014` writes no book *content*** — a skeleton row and a per-author prompt — and **`015` is the first feature that writes into a book's text.**

## Failure modes

Failure behaviour is part of the design, not an afterthought:

- **No valid token → `401`.** There is no anonymous access to anything book-shaped.
- **A private book the caller has no relationship to → `404`, not `403`.** A `403` confirms the book exists, which turns the id space into an enumeration oracle for private books; `404` does not. This is chosen deliberately and applies only to the *existence-hiding* case.
- **A book the caller can legitimately see, but a capability they lack → `403`.** The caller already knows the book exists, so there is nothing to hide, and a `403` tells them the truth: they are looking at the right thing and are not allowed to do that to it.
- **Quarantined or destroyed → the removal notice**, not a bare refusal, for the owner (UC-046). This is a distinct response shape, not a status code alone.
- **A stale `base_version` on a chapter write → `409`**, independent of authorization. See `domain-chapter.md` → "Concurrency".

The `401` / `404` / `403` split is the same taxonomy the existing admin routes use (`backend/features.md` → LLM server connections, Database consistency & management), extended with the existence-hiding rule.

## Not settled by this pass

Recorded rather than guessed:

- **The moderation view's route surface and DTOs** — FEAT-011 is Stage 6 and its architecture is out of scope here. This document fixes only that the surface is separate, admin-only, read-only, and reaches the codex.
- **Proposal review for notes and codex entries.** FEAT-010's own `_TBD:` says only block proposals have a use case today; this matrix marks note and codex edits *(mode)* without designing the review surface for them. **Codex has since taken an interim position rather than waiting**: a co-author's write in a proposal-mode book is **refused with `403`** rather than held, because there is nothing to hold it in (see the codex subsection above and `domain-codex.md`). That is a decision about the *gap*, not a design of the review surface — the surface is still open.
