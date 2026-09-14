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
  - **US-086.AC-3** — Given a **fact** entry open in the content pane,
    when the author asks the assistant to write its name, then the write
    is refused with a reason the author can see.
  - **US-086.AC-4** — Given a **fact** entry open in the content pane,
    when the author asks the assistant to write its name, then the entry
    is unchanged — a fact has no name (US-078.AC-2); its body carries its
    content.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4: "i
  can ask LLM to generate the cahracter or rewrite/edit the character, or
  location or some lore fact."; interview 2026-07-23, "Augment round 5",
  "the working page — two-pane, chat + content": "assistant fills it."
  AC-3 and AC-4: `[confirmed: user]` interview 2026-08-10, "finalization —
  plans 023 + 024" — the behaviour was reported as a defect
  (`docs/plans/024.chat-agent-loop/feedback.md`, F2) and **confirmed as
  the requirement**; US-078.AC-2 stands unchanged and the refusal is
  specified here rather than left as an unwritten consequence. Challenge
  C-f2324-7.

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

### US-121 — Author asks the assistant to create a codex entry outright
- **Feature:** FEAT-018 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-076
- **Status:** delivered
- **Story:** As an author, I want to ask the assistant for a new codex
  entry and get one, so that I can build the book's lore without opening
  a blank entry first.
- **Acceptance criteria:**
  - **US-121.AC-1** — Given the author directly asks the assistant to
    create a codex entry of a given kind, when the assistant creates it,
    then the entry exists in the book's codex with no further save step
    by the author.
  - **US-121.AC-2** — Given no codex entry is open in the content pane,
    when the author asks the assistant to create one, then it is created
    — an open entry is not a precondition of creation.
  - **US-121.AC-3** — Given the author has not asked for an entry to be
    created, when the assistant identifies material that could warrant
    one, then no codex entry is created.
- **Note:** AC-3 is enforced by the mode's seeded prompt guidance, not
  structurally — an administrator who rewrites the prompt can weaken it.
  Recorded rather than hidden, the same class of statement as FEAT-020's
  "accepted with its risk stated".
- **Source:** `[confirmed: user]` interview 2026-09-14, "augment round —
  the assistant on a lore list"; challenge C1.
<!-- product-spec:end -->
