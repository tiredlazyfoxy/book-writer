<!-- product-spec:start -->
# Use Cases — FEAT-013 Block composition chat

### UC-053 — Start a composition chat
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Author is a member of the book.
- **Main flow:**
  1. Author opens a new composition chat.
  2. System starts the chat, private to the author.
  3. Author enters a free-form prompt.
- **Exception flow:** No chapter is open in the book →
  `_TBD: whether starting is refused or allowed with a reduced context set
  is not stated in the interview._`
- **Postconditions:** A composition chat exists, visible only to its
  author; the author may end it at any time (UC-057).
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "block composition chat": "The author starts and ends chats freely — not
  bound to a block or a chapter."

### UC-054 — Iterate with the LLM on the next block
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A composition chat exists; the four continuity
  artifacts are available to it (US-057).
- **Main flow:**
  1. Author sends a free-form prompt in the chat.
  2. System sends the prompt, with the available artifacts, to the LLM.
  3. LLM responds within the chat.
  4. Author reviews the response and sends another prompt to refine, or
     proceeds to produce a block (UC-055).
- **Exception flow:** No LLM server is enabled (FEAT-004) → composing is
  refused. `[inferred]` — basis: FEAT-013 depends on FEAT-004 for an
  enabled model (spec-plan dependency edge); the interview does not state
  the refusal behavior directly.
- **Postconditions:** Chat holds the exchanged messages; author may
  iterate further or produce a block.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "block composition chat": "the chat with LLM where all artifacts are
  added to the context and then author chats and is
  creating/recreating/polishing the next block."

### UC-055 — Produce a block from a composition chat
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A composition chat has reached a state the author
  considers ready.
- **Main flow:**
  1. Author requests the chat produce the block.
  2. LLM produces the block.
  3. In free mode: system adds the block to the open chapter directly
     (FEAT-009).
  4. In proposal mode: system holds the block as a proposal (FEAT-010).
- **Exception flow:** The chapter open at chat start has since closed →
  `_TBD: exact handling (refuse, retarget, or hold) is not stated in the
  interview._`
- **Postconditions:** Block exists per the book's collaboration mode;
  editing it further is FEAT-009, not this feature.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "block composition chat": "When it's ready LLM produces the block, author
  can edit it manually." / "In proposal mode... a co-author's generated
  block become? A proposal."

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

### UC-057 — End a composition chat
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A composition chat exists, belonging to the author.
- **Main flow:**
  1. Author ends the chat.
  2. System closes the chat.
- **Postconditions:** Chat is ended; ending without producing a block is
  allowed. Chat remains visible only to its author (US-061).
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "block composition chat": "The author starts and ends chats freely — not
  bound to a block or a chapter."

### UC-078 — Composition chat draws on the codex
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005
- **Preconditions:** An active composition chat (UC-053); the book has a
  codex (FEAT-017).
- **Main flow:**
  1. Author sends a prompt in the chat.
  2. System makes codex entries relevant to the prompt available to the
     chat, alongside the four continuity artifacts (US-057).
  3. LLM responds using that context.
- **Postconditions:** Chat's response can draw on codex entries.
  `_TBD: what makes an entry "relevant" enough to reach the chat — no
  measurable criterion offered; see challenge C27._`
- **Source:** `[confirmed: user]` `docs/.cache/product/interview.md`,
  "## challenges (2026-07-20, round 4)", challenge C26. How the chat
  reaches those entries is `/architect`'s.
<!-- product-spec:end -->
