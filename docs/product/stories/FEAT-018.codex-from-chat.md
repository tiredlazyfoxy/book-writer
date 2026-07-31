<!-- product-spec:start -->
# Stories — FEAT-018 Codex authoring from the composition chat

### US-086 — Author has the assistant fill a codex entry on the shared canvas
- **Feature:** FEAT-018 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-076
- **Status:** delivered
- **Story:** As an author, I want to open a blank codex entry and have the
  assistant fill it, so that I don't have to write lore by hand.
- **Acceptance criteria:**
  - **US-086.AC-1** — Given a blank codex entry open in the content pane,
    when the author asks the chat to generate it, then the assistant
    writes a draft directly into the entry.
  - **US-086.AC-2** — Given a draft written into the entry, when the
    author has not saved, then the codex is unchanged.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4: "i
  can ask LLM to generate the cahracter or rewrite/edit the character, or
  location or some lore fact."; interview 2026-07-23, "Augment round 5",
  "the working page — two-pane, chat + content": "assistant fills it."

### US-087 — Author has the assistant rewrite an existing entry on the shared canvas
- **Feature:** FEAT-018 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-077
- **Status:** delivered
- **Story:** As an author, I want to open an existing codex entry and have
  the assistant rewrite it in place, so that I can revise lore without
  leaving the working page.
- **Acceptance criteria:**
  - **US-087.AC-1** — Given an existing codex entry open in the content
    pane, when the author asks the chat to rewrite it, then the assistant
    writes the rewritten draft directly into the entry.
  - **US-087.AC-2** — Given a rewritten draft in the entry, when the
    author has not saved, then the entry is unchanged.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4:
  "rewrite/edit the character, or location or some lore fact."; "same
  review-then-save."; interview 2026-07-23, "Augment round 5", "the
  working page — two-pane, chat + content".

### US-088 — A chat-authored entry is saved only on explicit request
- **Feature:** FEAT-018 · **Actor:** ACT-004, ACT-005 · **Realizes:**
  UC-076, UC-077
- **Status:** delivered
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
  UC-055." **Reaffirmed, round 5** — this is now the specific case of
  FEAT-013's general shared-canvas draft-until-saved rule (US-103):
  interview 2026-07-23, "Augment round 5", "the working page — two-pane,
  chat + content".
<!-- product-spec:end -->
