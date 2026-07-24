<!-- product-spec:start -->
# Use Cases — FEAT-019 Book & chapter system prompts

### UC-093 — Set the book's system prompt
- **Feature:** FEAT-019 · **Actor:** ACT-004
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
  owner-only."

### UC-094 — Set a chapter's system prompt
- **Feature:** FEAT-019 · **Actor:** ACT-004, ACT-005
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
  applies."
<!-- product-spec:end -->
