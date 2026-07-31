<!-- product-spec:start -->
# Quick Reference

Dense id registry — the **sole canonical id registry** for
`docs/product/`. `features.md` keeps the spine (FEAT blocks only) and
`relationships.md` holds feature relationships; neither holds registry
tables. This file is exempt from the line budget.

## Actors

| id | name | one-liner |
|---|---|---|
| ACT-001 | Administrator | Sets up and operates the platform; moderates book content. |
| ACT-002 | Author | A book-writing account; owns and co-authors books. |
| ACT-003 | First-run operator | Bootstraps an unconfigured instance. |
| ACT-004 | Book owner | The author who created a book (or received it by transfer). |
| ACT-005 | Co-author | An author granted access to someone else's book. |
| ACT-006 | Reader | A logged-in user reading a public book they aren't a member of. |

## Features

| id | name | priority | status |
|---|---|---|---|
| FEAT-001 | First-run bootstrap | must | proposed |
| FEAT-002 | Authentication & session | must | proposed |
| FEAT-003 | User management | must | proposed |
| FEAT-004 | LLM server connections | must | proposed |
| FEAT-005 | Database consistency & management | must | proposed |
| FEAT-006 | Book lifecycle & ownership | must | proposed |
| FEAT-007 | Membership & visibility | must | proposed |
| FEAT-008 | Chapter skeleton & sketches | must | delivered |
| FEAT-009 | Chapter writing | must | partially delivered |
| FEAT-010 | Proposal mode | should | proposed |
| FEAT-011 | Content moderation | must | proposed |
| FEAT-012 | Chapter summaries & state notes | must | partially delivered |
| FEAT-013 | AI authoring assistant | must | partially delivered |
| FEAT-014 | Chapter variants & fixes | must | proposed |
| FEAT-015 | Book cloning | must | proposed |
| FEAT-016 | Consistency check & chapter flags | must | partially delivered |
| FEAT-017 | Codex | must | proposed |
| FEAT-018 | Codex authoring from the composition chat | should | proposed |
| FEAT-019 | Per-author system prompts | must | delivered |
| FEAT-020 | Assistant modes & sub-agents | must | proposed |

## Use cases

| id | title | feature | actor | status |
|---|---|---|---|---|
| UC-001 | Create DB + first admin | FEAT-001 | ACT-003 | proposed |
| UC-002 | Import DB to bootstrap | FEAT-001 | ACT-003 | proposed |
| UC-003 | Log in | FEAT-002 | ACT-001, ACT-002 | proposed |
| UC-004 | Log out / session expiry | FEAT-002 | ACT-001, ACT-002 | proposed |
| UC-005 | List users | FEAT-003 | ACT-001 | proposed |
| UC-006 | Create user | FEAT-003 | ACT-001 | proposed |
| UC-007 | Reset user password | FEAT-003 | ACT-001 | proposed |
| UC-008 | Change user role | FEAT-003 | ACT-001 | proposed |
| UC-009 | Disable user | FEAT-003 | ACT-001 | proposed |
| UC-010 | Register LLM server | FEAT-004 | ACT-001 | proposed |
| UC-011 | Test connection / probe models | FEAT-004 | ACT-001 | proposed |
| UC-012 | Enable models | FEAT-004 | ACT-001 | proposed |
| UC-013 | Edit / delete LLM server | FEAT-004 | ACT-001 | proposed |
| UC-014 | Designate embedding server + model | FEAT-004 | ACT-001 | proposed |
| UC-015 | View consistency report | FEAT-005 | ACT-001 | proposed |
| UC-016 | Create missing table | FEAT-005 | ACT-001 | proposed |
| UC-017 | Sync table schema | FEAT-005 | ACT-001 | proposed |
| UC-018 | Export database | FEAT-005 | ACT-001 | proposed |
| UC-019 | Import database (admin) | FEAT-005 | ACT-001 | proposed |
| UC-020 | Rebuild vector index | FEAT-005 | ACT-001 | proposed |
| UC-021 | Create a book | FEAT-006 | ACT-002 | proposed |
| UC-022 | List my books | FEAT-006 | ACT-004 | proposed |
| UC-023 | Archive a book | FEAT-006 | ACT-004 | proposed |
| UC-024 | Transfer ownership | FEAT-006 | ACT-004 | proposed |
| UC-025 | Admin reassigns ownership of a book whose owner is disabled | FEAT-006 | ACT-001 | proposed |
| UC-026 | Add a co-author | FEAT-007 | ACT-004 | proposed |
| UC-027 | Remove a co-author | FEAT-007 | ACT-004 | proposed |
| UC-028 | Set book visibility (private / public) | FEAT-007 | ACT-004 | proposed |
| UC-029 | Read a public book | FEAT-007 | ACT-006 | proposed |
| UC-030 | List books shared with me | FEAT-007 | ACT-005 | proposed |
| UC-031 | Add a chapter | FEAT-008 | ACT-004, ACT-005 | delivered |
| UC-032 | Reorder chapters | FEAT-008 | ACT-004 | delivered |
| UC-033 | Edit a chapter sketch | FEAT-008 | ACT-004, ACT-005 | delivered |
| UC-034 | Remove a planned chapter | FEAT-008 | ACT-004, ACT-005 | delivered |
| UC-035 | Open a chapter for writing | FEAT-009 | ACT-004 | delivered |
| UC-036 | Close the open chapter | FEAT-009 | ACT-004 | partially delivered |
| UC-037 | Reopen a closed chapter | FEAT-009 | ACT-004 | delivered |
| UC-038 | Add an edit to the open chapter (free mode) | FEAT-009 | ACT-004, ACT-005 | delivered |
| UC-039 | Save an edit to a chapter whose body changed underneath | FEAT-009 | ACT-004, ACT-005 | delivered |
| UC-040 | Submit proposed edits | FEAT-010 | ACT-005 | proposed |
| UC-041 | Owner reviews and applies proposals | FEAT-010 | ACT-004 | proposed |
| UC-042 | Change the book's collaboration mode | FEAT-010 | ACT-004 | proposed |
| UC-043 | Admin opens a book in the moderation view | FEAT-011 | ACT-001 | proposed |
| UC-044 | Quarantine a book | FEAT-011 | ACT-001 | proposed |
| UC-045 | Destroy a quarantined book | FEAT-011 | ACT-001 | proposed |
| UC-046 | Owner sees a removal notice | FEAT-011 | ACT-004 | proposed |
| UC-047 | System drafts a chapter's summary and state-note changes on close | FEAT-012 | ACT-004 | deferred |
| UC-048 | Owner reviews and approves a chapter's continuity data | FEAT-012 | ACT-004 | deferred |
| UC-049 | View the book's current state notes | FEAT-012 | ACT-004, ACT-005 | delivered |
| UC-050 | Edit state notes | FEAT-012 | ACT-004, ACT-005 | partially delivered |
| UC-051 | View a chapter's state-note changeset | FEAT-012 | ACT-004, ACT-005 | delivered |
| UC-052 | Reopening a chapter flags its continuity data stale | FEAT-012 | ACT-004 | delivered |
| UC-053 | Start a composition chat | FEAT-013 | ACT-004, ACT-005 | proposed |
| UC-054 | Iterate with the LLM on the next edit | FEAT-013 | ACT-004, ACT-005 | proposed |
| UC-055 | Produce an edit from a composition chat | FEAT-013 | ACT-004, ACT-005 | proposed |
| UC-056 | Composition request fails | FEAT-013 | ACT-004, ACT-005 | proposed |
| UC-057 | Leave a composition chat | FEAT-013 | ACT-004, ACT-005 | proposed |
| UC-058 | Edit a reopened chapter, creating a variant | FEAT-014 | ACT-004, ACT-005 | proposed |
| UC-059 | View and compare a chapter's variants | FEAT-014 | ACT-004, ACT-005 | proposed |
| UC-060 | Apply a variant to the chapter | FEAT-014 | ACT-004 | proposed |
| UC-061 | Owner clones a book | FEAT-015 | ACT-004 | proposed |
| UC-062 | Co-author clones a public book | FEAT-015 | ACT-005 | proposed |
| UC-063 | Choose which members carry over to a clone | FEAT-015 | ACT-004, ACT-005 | proposed |
| UC-064 | Run a consistency check on demand | FEAT-016 | ACT-004 | deferred |
| UC-065 | Run the consistency check when closing a fixed chapter | FEAT-016 | ACT-004 | deferred |
| UC-066 | Apply flags from consistency findings | FEAT-016 | ACT-004 | deferred |
| UC-067 | Member raises a flag on a chapter | FEAT-016 | ACT-004, ACT-005 | delivered |
| UC-068 | Resolve a flag | FEAT-016 | ACT-004 | delivered |
| UC-069 | Create a codex entry | FEAT-017 | ACT-004, ACT-005 | proposed |
| UC-070 | Edit a codex entry | FEAT-017 | ACT-004, ACT-005 | proposed |
| UC-071 | Browse and search the codex | FEAT-017 | ACT-004, ACT-005 | proposed |
| UC-072 | Archive a codex entry | FEAT-017 | ACT-004, ACT-005 | proposed |
| UC-073 | View an entry's edit history | FEAT-017 | ACT-004, ACT-005 | proposed |
| UC-074 | Restore an entry to an earlier version | FEAT-017 | ACT-004, ACT-005 | proposed |
| UC-075 | Copy codex entries from another book | FEAT-017 | ACT-004, ACT-005 | proposed |
| UC-076 | Generate a codex entry from a composition chat | FEAT-018 | ACT-004, ACT-005 | proposed |
| UC-077 | Rewrite an existing codex entry from a composition chat | FEAT-018 | ACT-004, ACT-005 | proposed |
| UC-078 | Composition chat draws on the codex | FEAT-013 | ACT-004, ACT-005 | proposed |
| UC-079 | State note references a named codex entry | FEAT-012 | ACT-004, ACT-005 | proposed |
| UC-080 | Consistency check warns about content with no codex entry behind it | FEAT-016 | ACT-004 | deferred |
| UC-081 | Manage and continue stored chats | FEAT-013 | ACT-004, ACT-005 | proposed |
| UC-082 | Archive a chat | FEAT-013 | ACT-004, ACT-005 | proposed |
| UC-083 | Load a chapter or codex entry into the content pane (read-only unless it is the open chapter) | FEAT-013 | ACT-004, ACT-005 | proposed |
| UC-084 | Give the assistant a text selection as focused source | FEAT-013 | ACT-004, ACT-005 | proposed |
| UC-085 | Assistant pulls another chapter into context on request | FEAT-013 | ACT-004, ACT-005 | proposed |
| UC-086 | Assistant searches the book's material by meaning | FEAT-013 | ACT-004, ACT-005 | proposed |
| UC-087 | Assistant consults the web | FEAT-013 | ACT-004, ACT-005 | proposed |
| UC-088 | Assistant runs a scoped consistency check in chat | FEAT-013 | ACT-004, ACT-005 | proposed |
| UC-089 | View a chapter's summary | FEAT-012 | ACT-004, ACT-005 | delivered |
| UC-090 | Browse the book's material from the working-page navigator | FEAT-013 | ACT-004, ACT-005 | proposed |
| UC-091 | View Book state — the working-SPA landing view | FEAT-012 | ACT-004, ACT-005 | partially delivered |
| UC-092 | Resume unsaved content-pane edits after navigating away | FEAT-013 | ACT-004, ACT-005 | proposed |
| UC-093 | Set the book's system prompt | FEAT-019 | ACT-004 | withdrawn (→ UC-098) |
| UC-094 | Set a chapter's system prompt | FEAT-019 | ACT-004, ACT-005 | withdrawn (→ UC-099) |
| UC-095 | Configure a working mode | FEAT-020 | ACT-001 | proposed |
| UC-096 | Create a sub-agent | FEAT-020 | ACT-001 | proposed |
| UC-097 | Edit or disable a sub-agent | FEAT-020 | ACT-001 | proposed |
| UC-098 | Set my own book system prompt | FEAT-019 | ACT-004, ACT-005 | delivered |
| UC-099 | Set my own chapter system prompt | FEAT-019 | ACT-004, ACT-005 | delivered |

## Stories

| id | title | feature | status |
|---|---|---|---|
| US-001 | First-run: create DB + admin | FEAT-001 | proposed |
| US-002 | First-run: import DB | FEAT-001 | proposed |
| US-003 | Log in | FEAT-002 | proposed |
| US-004 | Log out / session expiry | FEAT-002 | proposed |
| US-005 | Admin lists users | FEAT-003 | proposed |
| US-006 | Admin creates user | FEAT-003 | proposed |
| US-007 | Admin resets password | FEAT-003 | proposed |
| US-008 | Admin changes role | FEAT-003 | proposed |
| US-009 | Admin disables user | FEAT-003 | proposed |
| US-010 | Register LLM server | FEAT-004 | proposed |
| US-011 | Test connection / probe models | FEAT-004 | proposed |
| US-012 | Enable models | FEAT-004 | proposed |
| US-013 | Edit / delete LLM server | FEAT-004 | proposed |
| US-014 | Designate embedding server | FEAT-004 | proposed |
| US-015 | View consistency report | FEAT-005 | proposed |
| US-016 | Create missing table | FEAT-005 | proposed |
| US-017 | Sync table schema | FEAT-005 | proposed |
| US-018 | Export database | FEAT-005 | proposed |
| US-019 | Import database (admin) | FEAT-005 | proposed |
| US-020 | Rebuild vector index | FEAT-005 | proposed |
| US-021 | API-key $ENV indirection & secret masking | FEAT-004 | proposed |
| US-022 | Author creates a book and becomes its owner | FEAT-006 | proposed |
| US-023 | Author sees the books they own | FEAT-006 | proposed |
| US-024 | Owner archives a book | FEAT-006 | proposed |
| US-025 | Owner transfers a book to a co-author | FEAT-006 | proposed |
| US-026 | Admin restores ownership of an orphaned book | FEAT-006 | proposed |
| US-027 | Owner adds a co-author | FEAT-007 | proposed |
| US-028 | Owner removes a co-author, content and attribution survive | FEAT-007 | proposed |
| US-029 | Owner switches a book between private and public | FEAT-007 | proposed |
| US-030 | Logged-in reader opens a public book read-only | FEAT-007 | proposed |
| US-031 | Co-author sees books shared with them | FEAT-007 | proposed |
| US-032 | Member adds a chapter to the skeleton | FEAT-008 | delivered |
| US-033 | Owner reorders chapters | FEAT-008 | delivered |
| US-034 | Member edits the sketch of a planned chapter | FEAT-008 | delivered |
| US-035 | Member removes a planned chapter | FEAT-008 | delivered |
| US-036 | Owner opens a chapter for writing | FEAT-009 | delivered |
| US-037 | Only one chapter can be open at a time | FEAT-009 | delivered |
| US-038 | Owner closes the open chapter | FEAT-009 | delivered |
| US-039 | Owner reopens a closed chapter | FEAT-009 | delivered |
| US-040 | Co-author adds an edit in free mode | FEAT-009 | delivered |
| US-041 | A save against a changed chapter body warns the author | FEAT-009 | delivered |
| US-042 | Co-author submits proposed edits | FEAT-010 | proposed |
| US-043 | Owner applies proposals selectively | FEAT-010 | proposed |
| US-044 | Owner changes the collaboration mode | FEAT-010 | proposed |
| US-045 | Admin reads a book in the moderation view only | FEAT-011 | proposed |
| US-046 | Admin quarantines a book | FEAT-011 | proposed |
| US-047 | Admin destroys a quarantined book | FEAT-011 | proposed |
| US-048 | Owner is told their book was removed and why | FEAT-011 | proposed |
| US-049 | Continuity data is drafted when a chapter closes | FEAT-012 | deferred |
| US-050 | Owner approves a chapter's summary and state-note changes | FEAT-012 | deferred |
| US-051 | A chapter cannot close without approved continuity data | FEAT-012 | deferred |
| US-052 | Member views the book's current state notes | FEAT-012 | delivered |
| US-053 | Member edits state notes according to the collaboration mode | FEAT-012 | partially delivered |
| US-054 | Member views what a chapter changed in the state notes | FEAT-012 | delivered |
| US-055 | Reopening a chapter marks its continuity data stale | FEAT-012 | partially delivered |
| US-056 | Author starts chats freely; chats persist until archived | FEAT-013 | proposed |
| US-057 | The mode-dependent baseline is available to a composition chat | FEAT-013 | proposed |
| US-058 | Author iterates with the LLM to refine the next edit | FEAT-013 | proposed |
| US-059 | The assistant's shared-canvas write follows the book's collaboration mode at save | FEAT-013 | delivered |
| US-060 | A failed composition shows an error, offers retry, preserves the conversation | FEAT-013 | proposed |
| US-061 | A composition chat is visible only to its author, even once persisted | FEAT-013 | proposed |
| US-062 | Editing a closed chapter creates a new variant | FEAT-014 | proposed |
| US-063 | Member views and compares a chapter's variants | FEAT-014 | proposed |
| US-064 | Owner applies a variant to the chapter | FEAT-014 | proposed |
| US-065 | Applying a variant runs the chapter's consistency check | FEAT-014 | proposed |
| US-066 | Owner clones a book | FEAT-015 | proposed |
| US-067 | A clone is fully independent of its source | FEAT-015 | proposed |
| US-068 | Co-author clones a public book and becomes its owner | FEAT-015 | proposed |
| US-069 | Only the owner may clone a private book | FEAT-015 | proposed |
| US-070 | The cloner chooses which members carry over | FEAT-015 | proposed |
| US-071 | A clone carries content, continuity, mode and visibility | FEAT-015 | proposed |
| US-072 | Owner runs a consistency check on demand | FEAT-016 | deferred |
| US-073 | Closing a fixed chapter runs the consistency check | FEAT-016 | deferred |
| US-074 | Owner responds to consistency findings by re-fixing or applying flags | FEAT-016 | partially delivered |
| US-075 | Member raises a flag with a comment | FEAT-016 | delivered |
| US-076 | A flag records whether it came from a check or a person | FEAT-016 | delivered |
| US-077 | Owner resolves a flag | FEAT-016 | delivered |
| US-078 | Member creates a codex entry of a given kind | FEAT-017 | proposed |
| US-079 | Codex entries follow the book's collaboration mode | FEAT-017 | proposed |
| US-080 | Member browses and searches the codex | FEAT-017 | proposed |
| US-081 | Member archives a codex entry rather than deleting it | FEAT-017 | proposed |
| US-082 | Member views an entry's edit history | FEAT-017 | proposed |
| US-083 | Member restores an entry to an earlier version | FEAT-017 | proposed |
| US-084 | Member copies codex entries from another book they belong to | FEAT-017 | proposed |
| US-085 | The codex is invisible to readers and non-members | FEAT-017 | proposed |
| US-086 | Author has the assistant fill a codex entry on the shared canvas | FEAT-018 | proposed |
| US-087 | Author has the assistant rewrite an existing entry on the shared canvas | FEAT-018 | proposed |
| US-088 | A chat-authored entry is saved only on explicit request | FEAT-018 | proposed |
| US-089 | A composition chat can draw on the book's codex | FEAT-013 | proposed |
| US-090 | A state note names the codex entry it is about | FEAT-012 | proposed |
| US-091 | The check warns when a chapter references something absent from the codex | FEAT-016 | deferred |
| US-092 | An archived codex entry does not silently break existing state notes | FEAT-016 | deferred |
| US-093 | The moderation view includes the codex | FEAT-011 | proposed |
| US-094 | A clone carries the source book's codex | FEAT-015 | proposed |
| US-095 | Chats persist and are managed (list, pick, continue) | FEAT-013 | proposed |
| US-096 | Archive a chat instead of ending it | FEAT-013 | proposed |
| US-097 | The content pane shows any chapter, read-only unless it is the open one | FEAT-013 | delivered |
| US-098 | The author hands the assistant a text selection as focused source | FEAT-013 | delivered |
| US-099 | The assistant reads another chapter on request | FEAT-013 | proposed |
| US-100 | The assistant searches the book's material by meaning | FEAT-013 | proposed |
| US-101 | The assistant may consult the web | FEAT-013 | proposed |
| US-102 | The assistant runs a scoped consistency check in chat and returns a focused result | FEAT-013 | proposed |
| US-103 | The assistant writes into the open artifact; nothing persists until saved | FEAT-013 | delivered |
| US-104 | A member views a chapter's summary | FEAT-012 | delivered |
| US-105 | Author browses the book's material by kind from the working page | FEAT-013 | proposed |
| US-106 | Book state is the working-SPA landing view and shows the book at a glance | FEAT-012 | partially delivered |
| US-107 | Unsaved content-pane edits are retained and restored | FEAT-013 | delivered |
| US-108 | Owner sets the book's system prompt, applied to every chat in the book | FEAT-019 | withdrawn (→ US-115) |
| US-109 | Member sets a chapter's system prompt, narrowing the book's | FEAT-019 | withdrawn (→ US-116) |
| US-110 | Admin sets a mode's optional system prompt | FEAT-020 | proposed |
| US-111 | Admin sets which tools a mode may use | FEAT-020 | proposed |
| US-112 | Admin sets which sub-agents a mode may delegate to | FEAT-020 | proposed |
| US-113 | Admin creates a sub-agent | FEAT-020 | proposed |
| US-114 | Admin edits or disables a sub-agent | FEAT-020 | proposed |
| US-115 | Member sets their own book system prompt, applied to their own chats in that book | FEAT-019 | delivered |
| US-116 | Member sets their own chapter system prompt, layered under their own book prompt | FEAT-019 | delivered |
| US-117 | Author undoes the assistant's last write to the open artifact | FEAT-013 | delivered |
<!-- product-spec:end -->
