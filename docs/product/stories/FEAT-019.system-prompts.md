<!-- product-spec:start -->
# Stories — FEAT-019 Book & chapter system prompts

### US-108 — Owner sets the book's system prompt, applied to every chat in the book
- **Feature:** FEAT-019 · **Actor:** ACT-004 · **Realizes:** UC-093
- **Status:** proposed
- **Story:** As a book owner, I want to set a standing system prompt for
  the book, so that the assistant writes in the book's voice without me
  retyping instructions into every chat.
- **Acceptance criteria:**
  - **US-108.AC-1** — Given the owner writes and saves a book system
    prompt, when the save completes, then it is stored on the book.
  - **US-108.AC-2** — Given a co-author (not the owner), when they attempt
    to edit the book's system prompt, then the action is refused.
  - **US-108.AC-3** — Given a book system prompt that contradicts the
    book's content, when the consistency check runs, then it raises no
    warning citing the prompt.
- **Source:** `[confirmed: user]` interview 2026-07-24, "augment round 7":
  "book system prompt (will be applied to all chats)"; "Does the FEAT-016
  consistency check inspect the system prompts as content? No."

### US-109 — Member sets a chapter's system prompt, narrowing the book's
- **Feature:** FEAT-019 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-094
- **Status:** proposed
- **Story:** As a book member, I want to set an optional system prompt on
  a chapter, so that I can narrow how the assistant writes this chapter
  without losing the book's standing voice.
- **Acceptance criteria:**
  - **US-109.AC-1** — Given a member (owner or co-author) writes and
    saves a chapter system prompt, when the save completes, then it is
    stored on that chapter.
  - **US-109.AC-2** — Given a chapter with both a book and a chapter
    system prompt, when the assistant is used on that chapter, then both
    apply, with the chapter's narrowing the book's rather than replacing
    it.
  - **US-109.AC-3** — Given a chapter with no system prompt set, when the
    assistant is used on that chapter, then only the book's system prompt
    applies.
- **Source:** `[confirmed: user]` interview 2026-07-24, "augment round 7":
  "Chapter prompt = any member... narrows the book's rather than
  replacing it — the book-wide voice always applies."
<!-- product-spec:end -->
