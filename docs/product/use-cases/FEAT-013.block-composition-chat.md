<!-- product-spec:start -->
# Use Cases — FEAT-013 AI authoring assistant

(File retains its original slug, `block-composition-chat`, per the
merge-fence filename-stability rule — the feature was renamed, not
renumbered.)

### UC-053 — Start a composition chat
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Author is a member of the book.
- **Main flow:**
  1. Author starts a new chat.
  2. System starts the chat, private to the author; independent of any
     chapter, codex entry or content-pane subject — the pairing is
     spatial, not a data binding.
  3. Author enters a free-form prompt.
- **Exception flow:** No chapter is open in the book → the chat still
  starts, with a reduced baseline (the chapter-mode continuity fields have
  nothing to attach to). Resolves prior open item T15.
- **Postconditions:** A composition chat exists, visible only to its
  author; it persists until archived (UC-082), not until "ended" — the
  author may leave it at any time (UC-057) without losing it.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "block composition chat": "The author starts and ends chats freely — not
  bound to a block or a chapter."; interview 2026-07-23, "Augment round 5",
  "the working page — two-pane, chat + content": "Is the chat bound to the
  content? No — independent... this is what resolves seam S1 / TBD T16."

### UC-054 — Iterate with the LLM on the next block
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A composition chat exists; the mode-dependent hybrid
  baseline is available to it (US-057) — chapter mode or codex-entry mode,
  matching whatever the content pane currently holds.
- **Main flow:**
  1. Author sends a free-form prompt, optionally with a text selection as
     a focused source (UC-084).
  2. System sends the prompt, with the mode-dependent baseline (and any
     selection), to the LLM.
  3. Author may ask the assistant to pull additional sources — another
     chapter (UC-085), the book by meaning (UC-086), the web (UC-087) —
     or run a scoped check (UC-088).
  4. LLM responds within the chat.
  5. Author reviews the response and sends another prompt to refine, or
     directs the assistant to write into the open artifact (UC-055).
- **Exception flow:** No LLM server is enabled (FEAT-004) → composing is
  refused. `[inferred]` — basis: FEAT-013 depends on FEAT-004 for an
  enabled model (spec-plan dependency edge); the interview does not state
  the refusal behavior directly.
- **Postconditions:** Chat holds the exchanged messages; author may
  iterate further or direct the assistant to write into the open artifact.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "block composition chat": "the chat with LLM where all artifacts are
  added to the context and then author chats and is
  creating/recreating/polishing the next block."; interview 2026-07-23,
  "Augment round 5", "context model — hybrid push/pull".

### UC-055 — Produce a block from a composition chat
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A composition chat is active; the book's open chapter
  is the subject in the content pane (a read-only, closed chapter refuses
  this use case).
- **Main flow:**
  1. Author directs the assistant to write a block into the open chapter.
  2. Assistant writes the block directly onto the shared canvas, in the
     content pane, as a draft.
  3. Author may hand-edit the draft before saving.
  4. Author saves: in free mode, system adds the block to the chapter
     directly (FEAT-009); in proposal mode, system holds it as a proposal
     (FEAT-010).
- **Exception flow:** Content-pane subject is a read-only (closed) chapter
  → the write is refused. The chapter open at chat start has since closed
  → `_TBD: exact handling (refuse, retarget, or hold) is not stated in the
  interview._`
- **Postconditions:** Draft exists on the shared canvas until saved; once
  saved, the block exists per the book's collaboration mode; editing it
  further is FEAT-009, not this feature. **Revised, round 5:** the former
  "produce → hand-off" step no longer applies — the assistant writes
  directly into the open chapter, not into an intermediate output slot.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "block composition chat": "When it's ready LLM produces the block, author
  can edit it manually." / "In proposal mode... a co-author's generated
  block become? A proposal."; interview 2026-07-23, "Augment round 5", "the
  working page — two-pane, chat + content": "Agentic shared-canvas, not a
  'produce' hand-off... writes into whichever artifact is open in the
  content pane." / "When is content committed? Draft until saved."

### UC-056 — Composition request fails
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Author has sent a prompt or a produce request in an
  active chat.
- **Main flow:**
  1. Author sends a prompt or requests block production.
  2. LLM is unreachable, or returns nothing.
  3. System shows an error with a retry action.
  4. Conversation is preserved.
- **Postconditions:** Chat history unchanged aside from the error; author
  may retry the same request.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "block composition chat": "Error shown, retry offered, conversation
  preserved so nothing is retyped."

### UC-057 — Leave a composition chat
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A composition chat exists, belonging to the author.
- **Main flow:**
  1. Author leaves the chat (switches to another chat, or navigates away).
  2. System keeps the chat and its history; it stays listed for the
     author to resume at any time (UC-081).
- **Postconditions:** Chat is not ended or destroyed — it persists;
  leaving without writing anything into an artifact is allowed. Chat
  remains visible only to its author (US-061). **Renamed, round 5** — was
  "End a composition chat"; ending is replaced by leaving (this use case)
  and, separately, archiving (UC-082).
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "block composition chat": "The author starts and ends chats freely — not
  bound to a block or a chapter."; interview 2026-07-23, "Augment round 5",
  "the working page — two-pane, chat + content": "chats stay private to
  their author and per book... FEAT-013 'end a chat' becomes archive a
  chat (reversible); chats are persistent, not ephemeral."

### UC-078 — Composition chat draws on the codex
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005
- **Preconditions:** An active composition chat (UC-053); the book has a
  codex (FEAT-017).
- **Main flow:**
  1. Author sends a prompt in the chat.
  2. System makes codex entries relevant to the prompt available to the
     chat, alongside the always-present context baseline (US-057).
  3. LLM responds using that context.
- **Postconditions:** Chat's response can draw on codex entries.
  `_TBD: what makes an entry "relevant" enough to reach the chat — no
  measurable criterion offered; see challenge C27._`
- **Source:** `[confirmed: user]` `docs/.cache/product/interview.md`,
  "## challenges (2026-07-20, round 4)", challenge C26. How the chat
  reaches those entries is `/architect`'s.

### UC-081 — Manage and continue stored chats
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Author is a member of the book.
- **Main flow:**
  1. Author opens the chat pane's list of their stored chats for the book.
  2. System shows their non-archived chats.
  3. Author picks a chat.
  4. System reopens it with its full prior history, ready to continue.
- **Postconditions:** Selected chat is active in the chat pane; the
  author's other stored chats remain available to switch to.
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 5",
  "the working page — two-pane, chat + content": "Like Claude's chat
  manager — chats are stored, continuable, started fresh, and the user
  picks/archives them; the picker lives inside the chat pane."

### UC-082 — Archive a chat
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A stored chat belonging to the author exists.
- **Main flow:**
  1. Author selects a chat to archive.
  2. System removes it from the active chat list.
  3. Chat's history is retained, not destroyed.
- **Postconditions:** Chat no longer appears in the active picker;
  restorable by its author (mechanism not further specified).
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 5",
  "the working page — two-pane, chat + content": "FEAT-013 'end a chat'
  becomes archive a chat (reversible); chats are persistent, not
  ephemeral."

### UC-083 — Load a chapter or codex entry into the content pane (read-only unless it is the open chapter)
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Author is a member of the book; at least one chapter
  or codex entry exists.
- **Main flow:**
  1. Author selects a chapter or codex entry to load into the content
     pane.
  2. System loads it as the content-pane subject, replacing whatever was
     there.
  3. If the subject is a chapter that is not the book's currently open
     chapter, it loads read-only.
  4. If the subject is the book's open chapter, or a codex entry, it loads
     editable per the applicable collaboration-mode rules (FEAT-009,
     FEAT-017).
- **Postconditions:** The content-pane subject is independent of whichever
  chat is active — no data binding between the two (resolves seam S1).
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 5",
  "the working page — two-pane, chat + content": "Which chapters can
  occupy the content pane? Any chapter — read-only unless it is the open
  one. You can show a closed chapter to chat about it." / "Is the chat
  bound to the content? No — independent."
- **Note (round 6):** The content pane also holds navigator **lists**
  (Characters / Locations / Facts / Chapters / Book state / Chats), not
  only single items — lists and items are reached via the navigator
  (UC-090); a picked list item loads here under the read-only rules above,
  unchanged. The restore buffer (UC-092) applies to whichever editable
  subject is currently loaded here.

### UC-084 — Give the assistant a text selection as focused source
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A composition chat is active; the content pane holds
  a subject (chapter or codex entry).
- **Main flow:**
  1. Author selects a range of text in the content pane.
  2. Author sends a prompt while that selection is active.
  3. System narrows the assistant's pushed source to the selection rather
     than the full baseline field it came from.
  4. LLM responds using the selection as its focused source.
- **Postconditions:** Assistant's response is grounded in the selection,
  not the whole artifact.
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 5",
  "the working page — two-pane, chat + content": "The assistant reads the
  focused content (or a selection — a narrowed source, NEW requirement)."

### UC-085 — Assistant pulls another chapter into context on request
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A composition chat is active; another chapter besides
  the always-pushed baseline exists in the book.
- **Main flow:**
  1. Author asks the assistant to read a named chapter (e.g., "read
     chapter 8").
  2. System retrieves that chapter's full text for the request.
  3. LLM's response draws on that text.
- **Postconditions:** The pulled chapter's text is available for that
  exchange; it is not part of the always-pushed baseline.
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 5",
  "context model — hybrid push/pull": "Pulled on request: Full chapter
  bodies ('read chapter 8')..."

### UC-086 — Assistant searches the book's material by meaning
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A composition chat is active.
- **Main flow:**
  1. Author asks a question that needs material from the book without
     naming a specific chapter.
  2. System finds material relevant to the question by meaning, not exact
     match.
  3. LLM's response draws on the material found.
- **Postconditions:** Relevant material reaches the assistant without the
  author hand-picking it.
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 5",
  "context model — hybrid push/pull": "the book's own material by
  meaning-search."

### UC-087 — Assistant consults the web
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A composition chat is active.
- **Main flow:**
  1. Author asks a question that needs information from outside the book.
  2. Assistant consults the web on request.
  3. LLM's response draws on what it found.
- **Postconditions:** Web-sourced material reaches the chat when asked; it
  is not pushed automatically.
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 5",
  "context model — hybrid push/pull": "Web search — IN (new scope). The
  authoring assistant may draw on the web."

### UC-088 — Assistant runs a scoped consistency check in chat
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A composition chat is active.
- **Main flow:**
  1. Author asks a targeted consistency question (e.g., "does this block
     contradict chapter 8?").
  2. System runs a scoped check against the material named.
  3. Assistant returns a focused result — the finding, not the raw
     material it consulted.
- **Postconditions:** Chat holds a concise answer; the underlying chapters
  or notes consulted are not dumped into the conversation. This check is a
  conversational cousin to FEAT-016's mandatory close-time check, not a
  replacement for it. `_TBD: whether this in-chat finding can be promoted
  to a FEAT-016 flag — deferred to FEAT-016's rewrite._`
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 5",
  "context model — hybrid push/pull" / "boundaries recorded": "Yes —
  scoped, on-demand checks... that return a focused result without
  dumping the raw chapters into the conversation."

### UC-090 — Browse the book's material from the working-page navigator
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Author is a member of the book; the working page is
  open.
- **Main flow:**
  1. Author opens a navigator entry — **Characters / Locations / Facts /
     Chapters / Book state / Chats**.
  2. System renders that entry in the content pane as a list (or, for Book
     state, its landing view, UC-091).
  3. Author picks an item.
  4. System loads the item into the content pane, per UC-083's read-only
     rules.
  5. If the entry is **Chats**, the picked chat opens in the chat pane
     (UC-081), not the content pane.
- **Postconditions:** Content pane holds the selected list or item; chats
  route to the chat pane; the navigator choice does not bind the active
  chat (independence, seam S1).
- **Note:** The codex entries split three ways (Characters / Locations /
  Facts) is the round-4 fixed taxonomy, not a new entity.
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 6",
  "the working-page navigator": "Browse the book's material by kind. Final
  entries: Characters, Locations, Facts, Chapters, Book state, Chats." /
  "In the content pane — the pane holds either a list... or a single
  item." / "A chat opens in the chat pane, not the content pane."

### UC-092 — Resume unsaved content-pane edits after navigating away
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005
- **Preconditions:** The content pane holds an editable subject with
  unsaved edits.
- **Main flow:**
  1. Author edits an item without saving.
  2. Author navigates to another item or list.
  3. System retains the unsaved edits in device-local browser storage,
     private to the author.
  4. Author returns to the item, including after a full reload.
  5. System restores the unsaved edits. Each item keeps its own buffer.
- **Exception flow:** `_TBD: (CF-r6)` the saved server artifact changed
  under the buffer while it was unsaved (a co-author saved a newer
  version, cf. US-041) — conflict/staleness handling is unspecified;
  routed to `/architect`.
- **Postconditions:** Unsaved edits survive navigation and reload; they
  are no substitute for saving and are invisible to co-authors; lost if
  browser data is cleared. Storage tech is `/architect`'s.
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 6",
  "the restore buffer — unsaved per-item edits": "Device-local browser
  storage, private to the author, unsaved. Survives a full reload / next
  day... invisible to co-authors. Each item keeps its own buffer." Except
  the exception flow, tagged `_TBD:` per challenge C-r6-3.
<!-- product-spec:end -->
