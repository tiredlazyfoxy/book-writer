<!-- product-spec:start -->
# Use Cases — FEAT-019 Per-author system prompts

### UC-093 — Set the book's system prompt
- **Feature:** FEAT-019 · **Actor:** ACT-004
- **Status:** withdrawn
- **Reason:** The book system prompt is no longer an owner-only book-wide
  setting. Plan `021` made it **per-author**: every member owns one and
  reads only their own. This use case's owner-only precondition and its
  co-author refusal both invert.
- **Superseded by:** UC-098
- **Preconditions:** Author is the owner of the book.
- **Main flow:**
  1. Owner opens the book's system prompt.
  2. Owner edits the free-text prompt.
  3. Owner saves.
  4. System applies the prompt to every chat in the book from then on.
- **Exception flow:** A co-author attempts to set the book's system
  prompt → refused.
- **Postconditions:** The prompt is stored on the book; existing chats and
  new chats alike use it. `_TBD: whether a change to the book's system
  prompt affects chats already in progress or only new ones — not
  stated._`
- **Source:** `[confirmed: user]` interview 2026-07-24, "augment round 7 —
  enforcing the architecture pass onto the spec": "book system prompt
  (will be applied to all chats)"; "Book prompt = owner only... the same
  class as collaboration mode (UC-042) and visibility (UC-028), both
  owner-only." Withdrawn: `[confirmed: user]` interview 2026-07-30,
  "finalization — 021 + 014 + 015".

### UC-094 — Set a chapter's system prompt
- **Feature:** FEAT-019 · **Actor:** ACT-004, ACT-005
- **Status:** withdrawn
- **Reason:** The chapter prompt no longer narrows a book-wide prompt —
  plan `021` removed that layer, and plan `014` made the chapter prompt
  per-author too. Main-flow step 4 references a base layer that does not
  exist.
- **Superseded by:** UC-099
- **Preconditions:** Author is a member of the book; the chapter exists.
- **Main flow:**
  1. Member opens the chapter's system prompt (optional, may be empty).
  2. Member edits the free-text prompt.
  3. Member saves.
  4. System applies the chapter's prompt alongside the book's — it
     narrows the book's prompt rather than replacing it.
- **Postconditions:** The prompt is stored on the chapter. `_TBD: whether
  chapter system prompts follow the book's collaboration mode
  (free/proposal) as state notes and codex entries do — not stated._`
- **Source:** `[confirmed: user]` interview 2026-07-24, "augment round 7":
  "Chapter prompt = any member... sits beside the sketch (UC-033), which
  any member edits."; "The chapter system prompt is optional and narrows
  the book's rather than replacing it — the book-wide voice always
  applies." Withdrawn: `[confirmed: user]` interview 2026-07-30,
  "finalization — 021 + 014 + 015".

### UC-098 — Set my own book system prompt
- **Feature:** FEAT-019 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Author is a member of the book.
- **Main flow:**
  1. Member opens their own book system prompt.
  2. Member edits the free-text prompt.
  3. Member saves.
  4. System applies the prompt to that member's own chats in that book —
     nothing else's.
- **Exception flow:** Member has no prompt yet → an empty prompt is valid
  and contributes nothing.
- **Postconditions:** The prompt is stored against `(book, member)`; no
  other member's prompt is affected or visible, including the owner's.
- **Source:** Per-author substance `[confirmed: user]` interview 2026-07-30,
  "challenges (2026-07-30)", C4 ("Under per-author ownership... whose
  prompts?"); id replacement `[confirmed: user]` interview 2026-07-30,
  "finalization — 021 + 014 + 015" (tombstone-and-mint decision). Title
  per `docs/.cache/product/spec-plan.finalization.md` §B. Replaces
  withdrawn UC-093. Delivered by `docs/plans/021.per-author-system-prompt/`
  (2026-07-30).

### UC-099 — Set my own chapter system prompt
- **Feature:** FEAT-019 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Author is a member of the book; the chapter exists.
- **Main flow:**
  1. Member opens their own chapter system prompt (optional, may be
     empty).
  2. Member edits the free-text prompt.
  3. Member saves.
  4. System applies it after that member's own book prompt, to that
     member's own chats on that chapter.
- **Exception flow:** Member has no chapter prompt yet → empty is valid
  and contributes nothing; only that member's own book prompt applies.
- **Postconditions:** The prompt is stored against `(chapter, member)`;
  readable and writable in every chapter state (`planned`, `open`,
  `closing`, `closed`).
- **Source:** Per-author substance `[confirmed: user]` interview 2026-07-30,
  "challenges (2026-07-30)", C4 ("Under per-author ownership... whose
  prompts?"); id replacement `[confirmed: user]` interview 2026-07-30,
  "finalization — 021 + 014 + 015" (tombstone-and-mint decision). Title
  per `docs/.cache/product/spec-plan.finalization.md` §B. Replaces
  withdrawn UC-094. Delivered by `docs/plans/014.chapter-skeleton/` and
  `docs/plans/015.chapter-writing-free-mode/` (2026-07-30).
<!-- product-spec:end -->
