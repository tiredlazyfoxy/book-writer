<!-- product-spec:start -->
# Stories — FEAT-019 Per-author system prompts

### US-108 — Owner sets the book's system prompt, applied to every chat in the book
- **Feature:** FEAT-019 · **Actor:** ACT-004 · **Realizes:** UC-093
- **Status:** withdrawn
- **Reason:** AC-2 asserts the opposite of what shipped: it refuses a
  co-author from editing the book prompt, but under per-author a
  co-author edits their own and is not refused.
- **Superseded by:** US-115
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
  consistency check inspect the system prompts as content? No." Withdrawn:
  `[confirmed: user]` interview 2026-07-30, "finalization — 021 + 014 +
  015".

### US-109 — Member sets a chapter's system prompt, narrowing the book's
- **Feature:** FEAT-019 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-094
- **Status:** withdrawn
- **Reason:** AC-2 and AC-3 both reference "the book's prompt" as a base
  layer to narrow or fall back to. There is no base layer.
- **Superseded by:** US-116
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
  replacing it — the book-wide voice always applies." Withdrawn:
  `[confirmed: user]` interview 2026-07-30, "finalization — 021 + 014 +
  015".

### US-115 — Member sets their own book system prompt, applied to their own chats in that book
- **Feature:** FEAT-019 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-098
- **Status:** delivered
- **Story:** As a book member, I want to set my own standing system
  prompt for the book, so that the assistant writes in my voice across my
  own chats without retyping instructions into every one.
- **Acceptance criteria:**
  - **US-115.AC-1** — Given a member writes and saves their own book
    system prompt, when the save completes, then it is stored against
    that member and that book.
  - **US-115.AC-2** — Given a co-author (not the owner) writes and saves
    their own book system prompt, when the save completes, then it is
    accepted, not refused.
  - **US-115.AC-3** — Given one member's book system prompt, when another
    member — including the book's owner — looks for it or has the
    assistant applied, then that other member's prompt is neither
    visible nor applied to them.
  - **US-115.AC-4** — Given a member with an absent or empty book system
    prompt, when the assistant is used on their behalf, then it
    contributes nothing extra and the assistant still works.
- **Note:** AC-2 is the exact inversion of withdrawn US-108.AC-2 — under
  per-author ownership a co-author's own prompt is accepted, not refused;
  this is why US-108 could not be amended in place.
- **Source:** Per-author substance `[confirmed: user]` interview 2026-07-30,
  "challenges (2026-07-30)", C4 ("Under per-author ownership... whose
  prompts?"); id replacement `[confirmed: user]` interview 2026-07-30,
  "finalization — 021 + 014 + 015" (tombstone-and-mint decision). Title
  per `docs/.cache/product/spec-plan.finalization.md` §B. Replaces
  withdrawn US-108. Delivered: `docs/plans/021.per-author-system-prompt/`
  (2026-07-30).

### US-116 — Member sets their own chapter system prompt, layered under their own book prompt
- **Feature:** FEAT-019 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-099
- **Status:** delivered
- **Story:** As a book member, I want to set my own chapter system
  prompt, so that it layers under my own book prompt for that chapter
  without a shared base layer.
- **Acceptance criteria:**
  - **US-116.AC-1** — Given a member writes and saves a chapter system
    prompt, when the save completes, then it is stored against that
    member and that chapter.
  - **US-116.AC-2** — Given a chapter where the same member has set both
    a book prompt and a chapter prompt, when the assistant is used on
    that chapter, then both apply, book first then chapter.
  - **US-116.AC-3** — Given a member with no chapter prompt set on that
    chapter, when the assistant is used on that chapter, then only that
    member's own book prompt applies.
  - **US-116.AC-4** — Given a chapter in any state (`planned`, `open`,
    `closing`, `closed`), when a member reads or writes their own chapter
    prompt, then the action is allowed regardless of the chapter's state.
- **Note:** AC-3 replaces withdrawn US-109.AC-3, which fell back to "the
  book's" prompt as a shared base layer that no longer exists.
- **Source:** Per-author substance `[confirmed: user]` interview 2026-07-30,
  "challenges (2026-07-30)", C4 ("Under per-author ownership... whose
  prompts?"); id replacement `[confirmed: user]` interview 2026-07-30,
  "finalization — 021 + 014 + 015" (tombstone-and-mint decision). Title
  per `docs/.cache/product/spec-plan.finalization.md` §B. Replaces
  withdrawn US-109. Delivered: `docs/plans/014.chapter-skeleton/` and
  `docs/plans/015.chapter-writing-free-mode/` (2026-07-30).
<!-- product-spec:end -->
