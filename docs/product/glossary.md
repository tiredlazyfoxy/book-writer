<!-- product-spec:start -->
# Glossary

- **Admin** — user role that manages the system: users, LLM servers, database.
- **Author** — user role that writes books; owns and co-authors books
  through the book-owner/co-author relationships (ACT-004/ACT-005).
- **First-run bootstrap** — the one-time setup flow on an unconfigured
  instance: create a new database + first admin, or import an existing
  database export.
- **Session** — the authenticated state a user holds after logging in, ended
  by logout or expiry.
- **Disable (vs delete)** — the terminal state for a user account: credentials
  are nulled so it can't log in, but its data and attribution are preserved.
  There is no hard delete of a user account.
- **LLM server (provider)** — a registered connection to an LLM-serving
  endpoint: name, backend type, base URL, API key, enabled models.
- **Backend type** — the kind of LLM server a connection points to: either
  llama-swap or openai. `[confirmed: user]` interview 2026-07-20, "Reference
  mapping"
- **Probe** — a live connection test against a registered LLM server that
  returns the models it currently offers.
- **Enabled models** — the subset of a server's probed models an admin has
  approved for use.
- **Embedding server** — the single LLM server + model designated to produce
  embeddings; only one may be designated at a time.
- **$ENV API-key indirection** — storing an API key as a reference to an
  environment variable rather than the raw value; the raw value is resolved
  only at the point of use and never returned to a caller.
- **Schema drift** — a mismatch between a table's actual structure and its
  expected structure (missing or extra columns).
- **Consistency report** — the per-table status view (ok / drift / missing)
  used to detect and remediate schema drift.
- **Database export / import** — a portable snapshot of the database that can
  be produced (export) and restored (import); import is idempotent —
  re-importing the same export does not duplicate data.
- **Vector index** — the search index for semantic lookup, rebuilt from
  source rows rather than exported/imported directly.
- **Book** — a set of chapters, owned by one author, optionally shared with
  co-authors. Internal structure beyond chapters is `_TBD: deferred to a
  later session, per interview 2026-07-20 "book structure — chapters,
  states, sketches"._`
- **Book owner** — the author who created a book or received it by
  transfer; the only one who orders chapters and opens/closes/reopens them.
  Not an account role — see *owner/co-author vs admin/author* below.
- **Co-author** — an author granted access to someone else's book; not an
  account role — see below.
- **Chapter** — a member of a book's ordered skeleton; states below.
- **Chapter states (planned / open / closed)** — *planned*: sketch only, not
  yet written. *open*: being written; at most one per book. *closed*:
  written, not editable, reopenable by the owner.
- **Sketch** — the idea/outline for a planned (not-yet-written) chapter;
  editable by any member, in parallel, distinct from the chapter's written
  content.
- **Block** — the unit of chapter writing; what it contains (format, length,
  structure) is `_TBD: confirmed deferral, per interview 2026-07-20
  "writing — blocks & concurrency"; see FEAT-009._` Distinct from a sketch,
  which precedes writing.
- **Collaboration mode** — a book-level property, set by the owner at
  creation and changeable any time: *free* or *proposal*.
- **Free mode** — a co-author's blocks land in the open chapter on save.
- **Proposal mode** — a co-author's blocks are held as proposals until the
  owner applies them.
- **Proposal (proposed block)** — a block submitted in proposal mode,
  pending the owner's review; the owner may apply some and not others.
- **Private book** — visible to its owner and co-authors only.
- **Public book** — read-only to any logged-in user; never anonymous.
- **Archive (book)** — the owner's reversible removal of a book from active
  use; never destroys it. Distinct from quarantine/destroy (admin-only).
- **Quarantine** — an admin action making a book invisible to everyone,
  including its members; a fast, reversible-from-mistake takedown, distinct
  from destroy (which is permanent).
- **Moderation view** — the admin-interface-only read view over any book's
  content, used to find content to quarantine or destroy; grants no
  authoring access.
- **Summary (chapter)** — the condensed narrative of what a chapter
  contained; drafted by the system on chapter close, reviewed and approved
  by the owner.
- **State note** — free text recording a fact that must stay true going
  forward (a change or state of a character or place); not a shorter
  version of the chapter. No entity model — a note is plain text, not
  attached to a character or place record.
- **State-note changeset** — the set of state notes a chapter added,
  modified or deleted; preserved per chapter even as the live set moves on.
- **Continuity data** — a chapter's summary and its state-note changeset,
  together; must be approved before the chapter can close.
- **Stale continuity** — the flag applied to a chapter's summary and
  state-note changeset when the chapter is reopened; the chapter must be
  re-approved before it can close again.
- **Composition chat** — a free-form chat with the LLM used to create,
  recreate and polish the next block before producing it; private to its
  author.
- **Produced block** — a block generated by a composition chat; enters the
  chapter under the book's collaboration mode, the same as a manually
  written block.
- **Variant (chapter)** — a version of a chapter's text. Created when a
  reopened chapter is edited (a fix); the chapter keeps every variant,
  readable by authors.
- **Active variant** — the one variant that is the chapter for every
  purpose (reading, generation context, export); chosen by the owner.
- **Fix** — editing a chapter after reopening it; keeps the chapter's
  prior text as a variant rather than overwriting it.
- **Clone (book)** — a new, fully independent book created from an
  existing one; no link, sync or comparison with its source.
- **Consistency check** — an LLM inspection of a book's chapters,
  summaries and state notes for contradictions; reports to the owner,
  never rewrites anything.
- **Flag** — a chapter annotation carrying a comment; raised by the
  consistency check or by a member, and resolved once dealt with.
- **Flag origin** — whether a flag came from the consistency check or a
  person; the two carry different weight.
- **Resolve (a flag)** — marking a flag dealt with; does not undo whatever
  prompted it.
- **Codex** — a book's reference volume: the set of things the book is
  *about*, as opposed to the prose itself. One per book, shared across
  chapter variants (FEAT-014).
- **Codex entry** — an item in the codex, of kind character, location or
  fact; follows the book's collaboration mode; archived, never deleted.
- **Character (kind)** — a named codex entry for a person.
- **Location (kind)** — a named codex entry for a place.
- **Fact (kind)** — an unnamed codex entry for a lore fact; no timeline, no
  state-note reference.
- **Named entry** — a character or location entry: carries state-note
  reference and is name-addressable, unlike a fact.
- **Edit history (codex)** — an entry's past versions; a member can view
  and restore from it.

**Distinctions** — each pair is confusable, kept separate deliberately:
- *Archive* (owner, reversible, never destroys) vs *quarantine* (admin,
  reversible takedown) vs *destroy* (admin, permanent — the single
  sanctioned exception to archive-only).
- *Private* (members only) vs *public* (read-only to any logged-in user).
- *Free mode* (applies on save) vs *proposal mode* (owner applies later) —
  same block unit, different gate.
- *Sketch* (idea/outline, planned chapters, parallel-editable) vs *block*
  (written content, open chapter only).
- *Owner/co-author* (a relationship to one book) vs *admin/author* (the
  account role from FEAT-003) — one Author account can be owner of some
  books and co-author of others at once; these never collide.
- *Summary* (backward-looking narrative of what a chapter contained) vs
  *state note* (a fact that must stay true going forward) — one condenses
  what happened, the other is what's currently true because of it.
- *State note* (backward fact, tied to a closed chapter's changeset) vs
  *sketch* (forward outline for a not-yet-written chapter) — both feed
  generation; neither replaces the other.
- *Produced block* (what a composition chat generates) vs *proposal* (a
  block pending the owner's review in proposal mode) — a produced block
  becomes a proposal only when the book is in proposal mode; in free mode
  it lands directly, same as any other block.
- *Variant* (one chapter's alternative text, kept within the same book)
  vs *clone* (a whole independent book) — a variant never leaves the
  chapter it belongs to; a clone is a separate book entirely.
- *Fix* (correct this book, keeping the chapter's prior text as a
  variant) vs *clone* (start a separate, fully independent book) —
  fixing stays inside the book; cloning leaves it.
- *Flag* (a note about a problem, from a check or a person) vs
  *proposal* (content pending the owner's application in proposal mode)
  — a flag never carries content to apply; a proposal is content itself.
- *Codex entry* (the stable thing — who a character is) vs *state note*
  (what a chapter changed about the world) — identity vs. change; a
  state note may name the codex entry it is about.
<!-- product-spec:end -->
