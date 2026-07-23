# Authorization — the book-scoped permission model

**Realizes:** FEAT-006, FEAT-007, FEAT-011, FEAT-015, FEAT-017; UC-021..030, UC-035..037, UC-041, UC-042, UC-043, UC-050, UC-060, UC-061, UC-062, UC-064, UC-068, UC-069..075

Every book-domain capability is gated on the caller's relationship to **one specific book**. This document defines the roles, the enforcement point, and the capability × role matrix. It assumes the book-domain entities — start at `domain-model.md` (the index), with `domain-book.md` for `Book` / `BookMember` and `domain-chapter.md` for the write path.

Authentication itself — JWT, per-user signing key, bcrypt, the `require_role(admin)` dependency — is unchanged and lives in `backend.md`. This document is only about *authorization within a book*.

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

Two chapter rules are **state-machine constraints, not authorization**, and apply even to the owner: a chapter in `closing` refuses writes, and a **reopen is refused while any chapter is `open` or `closing`** (CF1). Being the owner does not bypass either. See `domain-chapter.md`.

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

### Cloning

| Capability | Owner | Co-author | Reader | Admin |
|---|---|---|---|---|
| Clone a **private** book (UC-061) | ✓ | — | — | — |
| Clone a **public** book (UC-062) | ✓ | ✓ | — | — |
| Choose which members carry over (UC-063) | whoever clones | whoever clones | — | — |

**Only the owner may clone a private book** (challenge C21, stated in both FEAT-007 and FEAT-015). A co-author's clone makes them the new book's owner (US-068) — accepted deliberately in product (challenge C23).

Note the resolution recorded as finding R4-2: cloning a public book is a **co-author** capability (ACT-005, a member), not a reader one. ACT-006 has no clone use case, and the members-only codex is therefore never exposed by a clone.

### Chats

A chat is **private to its author**, including from the owner (US-061.AC-1). No role reaches another user's chat — this is not a matrix row but an ownership rule on `Chat.author_id`, enforced on every chat read and write. Only the *saved output* of a chat is shared (US-061.AC-2).

## The admin boundary

**An admin never participates in a book through the authoring interface** — in any collaboration mode, at any visibility, on any book, including one they could otherwise reach. FEAT-011 states it and this design enforces it structurally rather than by convention: the book-domain services check `BookAccess.role` against the matrix above, and `admin` is **not** a member role in that matrix. An admin calling an authoring endpoint is refused exactly as a stranger is.

The one place an admin reaches book content is the **FEAT-011 moderation read view** (UC-043): read-only, whole-book, including the codex, on any book regardless of visibility, plus quarantine (UC-044) and destroy (UC-045). That surface is a separate route tree behind the existing `require_role(admin)` dependency, and it does not share endpoints with the authoring API.

**Why structural rather than "admins can do anything":** the product rule is not a courtesy, it is the point of the role split — an admin is a platform operator, not a co-author, and an admin who could write into a book would make authorship attribution (US-040.AC-2) unreliable. A single "admin bypasses all checks" branch would silently undo that everywhere at once.

UC-025 (reassigning a disabled owner's book) is an admin capability over the book's *ownership record*, not over its content, and lives on the moderation/admin side for the same reason.

## Book state and visibility gates

The state and visibility fields gate access **before** the matrix is consulted:

| `Book.state` | Members | Reader (public) | Admin |
|---|---|---|---|
| `active` | matrix applies | read-only if public | moderation view |
| `archived` | matrix applies (see open question below) | read-only if public | moderation view |
| `quarantined` | **content hidden**; owner is shown the removal notice (UC-046) | hidden | moderation view |
| `destroyed` | **content hidden**; owner is shown the removal notice (UC-046) | hidden | moderation view |

Quarantine makes a book invisible to *everyone including its members* (UC-044) — the owner does not get a partial view, they get the notice instead of the content (UC-046 exception flow).

## Failure modes

Failure behaviour is part of the design, not an afterthought:

- **No valid token → `401`.** There is no anonymous access to anything book-shaped.
- **A private book the caller has no relationship to → `404`, not `403`.** A `403` confirms the book exists, which turns the id space into an enumeration oracle for private books; `404` does not. This is chosen deliberately and applies only to the *existence-hiding* case.
- **A book the caller can legitimately see, but a capability they lack → `403`.** The caller already knows the book exists, so there is nothing to hide, and a `403` tells them the truth: they are looking at the right thing and are not allowed to do that to it.
- **Quarantined or destroyed → the removal notice**, not a bare refusal, for the owner (UC-046). This is a distinct response shape, not a status code alone.
- **A stale `base_version` on a chapter write → `409`**, independent of authorization. See `domain-chapter.md` → "Concurrency".

The `401` / `404` / `403` split is the same taxonomy the existing admin routes use (`backend.md` → LLM server connections, Database consistency), extended with the existence-hiding rule.

## Not settled by this pass

Recorded rather than guessed:

- **Whether an archived book refuses writes.** UC-023 says content and history are preserved and archive is reversible; nothing states whether a member may keep writing into an archived book. The matrix above is written for `active`; the archived row inherits it pending a decision.
- **The moderation view's route surface and DTOs** — FEAT-011 is Stage 6 and its architecture is out of scope here. This document fixes only that the surface is separate, admin-only, read-only, and reaches the codex.
- **Who may edit the book- and chapter-level system prompts.** No product requirement covers them at all — see `domain-model.md` → "Product divergences", item 3.
- **Proposal review for notes and codex entries.** FEAT-010's own `_TBD:` says only block proposals have a use case today; this matrix marks note and codex edits *(mode)* without designing the review surface for them.
