<!-- product-spec:start -->
# Stories — FEAT-018 Codex authoring from the composition chat

### US-086 — Author generates a codex entry from the composition chat
- **Feature:** FEAT-018 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-076
- **Status:** proposed
- **Story:** As an author, I want to ask the composition chat to generate a
  codex entry, so that I don't have to write lore by hand.
- **Acceptance criteria:**
  - **US-086.AC-1** — Given an active composition chat, when the author
    asks it to generate an entry, then a draft entry appears in the chat.
  - **US-086.AC-2** — Given a draft entry in the chat, when the author has
    not requested it be saved, then the codex is unchanged.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4: "i
  can ask LLM to generate the cahracter or rewrite/edit the character, or
  location or some lore fact."

### US-087 — Author rewrites an existing entry from the chat
- **Feature:** FEAT-018 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-077
- **Status:** proposed
- **Story:** As an author, I want to ask the composition chat to rewrite an
  existing codex entry, so that I can revise lore without leaving the chat.
- **Acceptance criteria:**
  - **US-087.AC-1** — Given an active composition chat and an existing
    entry, when the author asks it to rewrite that entry, then a rewritten
    draft appears in the chat.
  - **US-087.AC-2** — Given a rewritten draft in the chat, when the author
    has not requested it be saved, then the entry is unchanged.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4:
  "rewrite/edit the character, or location or some lore fact."; "same
  review-then-save."

### US-088 — A chat-authored entry is saved only on explicit request
- **Feature:** FEAT-018 · **Actor:** ACT-004, ACT-005 · **Realizes:**
  UC-076, UC-077
- **Status:** proposed
- **Story:** As an author, I want a chat-generated or chat-rewritten entry
  to require my explicit save, so that nothing lands in the codex without
  my approval.
- **Acceptance criteria:**
  - **US-088.AC-1** — Given a drafted or rewritten entry shown in the chat,
    when the author requests it be saved, then the entry is added to or
    updated in the codex per the book's collaboration mode.
  - **US-088.AC-2** — Given a drafted or rewritten entry shown in the chat,
    when the author ends the chat without requesting a save, then the codex
    remains unchanged.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4:
  "Shown in the chat first, saved only on explicit request. Mirrors
  UC-055."
<!-- product-spec:end -->
