# 009.books — Book lifecycle, membership & visibility
<!-- roadmap:start -->
- **Stage:** 3.workspace · **Track:** multi-step · **Size:** L
- **Delivers:** FEAT-006, FEAT-007
- **Depends on:** `008.data-domain`

## Definition
An author creates a book and becomes its owner, sees the books they own and
those shared with them (the bookshelf), and manages a book from its
edit/settings page: archive, transfer ownership, add/remove co-authors, and
switch visibility between private and public. Delivers the Shell surfaces
for book lifecycle and membership.

## Scope
**In:** UC-021..030 — create/list/archive/transfer book; add/remove
co-author; set visibility; read-a-public-book access; shared-with-me list.
Backend services/routes + book-scoped authorization; bookshelf + book
settings SPA surfaces.
**Out:** the working page (`010.working-page`); chapters/codex/chat; book
cloning (FEAT-015, later); moderation (FEAT-011, later); admin ownership
reassignment of a disabled owner's book (UC-025) unless trivially included.

## Open questions for the planner
- Whether an archived book refuses writes — the one open gap in
  `domain-model.md` (`authorization.md` "Not settled"); resolve during
  planning.
<!-- roadmap:end -->
