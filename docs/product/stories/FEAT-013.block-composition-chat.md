<!-- product-spec:start -->
# Stories — FEAT-013 Block composition chat

### US-056 — Author starts and ends composition chats freely
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:**
  UC-053, UC-057
- **Status:** proposed
- **Story:** As an author, I want to start and end composition chats at
  will, so that I'm not forced to finish or bind a chat to one block or
  chapter.
- **Acceptance criteria:**
  - **US-056.AC-1** — Given the author is a member of the book, when they
    start a new composition chat, then a chat is created, private to them.
  - **US-056.AC-2** — Given an open composition chat, when the author ends
    it, then the chat is closed without requiring a block to have been
    produced.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "block composition chat": "The author starts and ends chats freely — not
  bound to a block or a chapter."

### US-057 — The four continuity artifacts are available to a composition chat
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-054
- **Status:** proposed
- **Story:** As an author, I want my composition chat to have access to
  prior-chapter summaries, current state notes, the open chapter's full
  text, and upcoming sketches, so that generated content stays consistent
  without needing the full book present.
- **Acceptance criteria:**
  - **US-057.AC-1** — Given an active composition chat, when the author
    sends a prompt, then summaries of all prior chapters are available to
    the chat.
  - **US-057.AC-2** — Given an active composition chat, when the author
    sends a prompt, then the current state notes are available to the chat.
  - **US-057.AC-3** — Given an active composition chat, when the author
    sends a prompt, then the full text of the open chapter is available to
    the chat.
  - **US-057.AC-4** — Given an active composition chat, when the author
    sends a prompt, then the sketches of upcoming chapters are available to
    the chat.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "generation context": "All four — summaries of all prior chapters,
  current state notes, full text of the open chapter, sketches of upcoming
  chapters."; challenge C11.

### US-058 — Author iterates with the LLM to refine the next block
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-054
- **Status:** proposed
- **Story:** As an author, I want to send free-form prompts and get
  responses inside the chat, so that I can create, recreate and polish the
  next block before producing it.
- **Acceptance criteria:**
  - **US-058.AC-1** — Given an active composition chat, when the author
    sends a free-form prompt, then the LLM's response appears in the chat.
  - **US-058.AC-2** — Given a response in the chat, when the author sends
    another prompt, then the chat continues with the prior exchange
    retained.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "block composition chat": "author chats and is
  creating/recreating/polishing the next block."

### US-059 — A produced block follows the book's collaboration mode
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-055
- **Status:** proposed
- **Story:** As an author, I want a block produced by the chat to enter the
  chapter the same way a manually written block would, so that
  collaboration rules stay consistent regardless of how a block was made.
- **Acceptance criteria:**
  - **US-059.AC-1** — Given the book is in free mode, when the author
    produces a block from the chat, then the block is added to the open
    chapter directly.
  - **US-059.AC-2** — Given the book is in proposal mode, when a co-author
    produces a block from the chat, then the block is held as a proposal
    until the owner applies it.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "block composition chat": "In proposal mode... a co-author's generated
  block become? A proposal."

### US-060 — A failed composition shows an error, offers retry, preserves the conversation
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-056
- **Status:** proposed
- **Story:** As an author, I want a clear error and a retry option when the
  LLM fails, so that I don't lose my conversation or retype it.
- **Acceptance criteria:**
  - **US-060.AC-1** — Given the author sends a prompt or requests block
    production, when the LLM is unreachable or returns nothing, then an
    error is shown with a retry action.
  - **US-060.AC-2** — Given a failed request, when the error is shown, then
    the conversation up to that point is preserved.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "block composition chat": "Error shown, retry offered, conversation
  preserved so nothing is retyped."

### US-061 — A composition chat is visible only to its author
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-057
- **Status:** proposed
- **Story:** As an author, I want my composition chat kept private, so that
  only my produced blocks are shared with others.
- **Acceptance criteria:**
  - **US-061.AC-1** — Given a composition chat belonging to one author,
    when another member of the book, including the owner, views the book,
    then that chat is not visible to them.
  - **US-061.AC-2** — Given a block produced from a private chat, when it
    is added or proposed, then only the block is shared, not the chat that
    produced it.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "block composition chat": "Private to their author... Only the produced
  block is shared."

### US-089 — A composition chat can draw on the book's codex
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-078
- **Status:** proposed
- **Story:** As an author, I want my composition chat to draw on the book's
  codex, so that generated content stays consistent with established lore.
- **Acceptance criteria:**
  - **US-089.AC-1** — Given a book with codex entries, when the author sends
    a prompt in a composition chat, then the book's codex is available to
    the chat.
  - `_TBD: which entries count as "relevant" enough to reach the chat — no
    measurable criterion offered; see challenge C27._`
- **Source:** `[confirmed: user]` `docs/.cache/product/interview.md`,
  "## challenges (2026-07-20, round 4)", challenge C26.
<!-- product-spec:end -->
