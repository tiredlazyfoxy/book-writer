<!-- product-spec:start -->
# Stories — FEAT-022 Side chats

### US-135 — Author starts a side chat in the middle of a conversation
- **Feature:** FEAT-022 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-110
- **Status:** proposed
- **Story:** As an author, I want to start a side chat mid-conversation,
  so that I can handle a side task without losing my place in the main
  task.
- **Acceptance criteria:**
  - **US-135.AC-1** — Given the author starts a side chat, when messages
    follow, then they are visibly set apart as belonging to the side
    chat.
  - **US-135.AC-2** — Given a side chat is already active, when the
    author tries to start another, then start is refused.
  - **US-135.AC-3** — Given the assistant is answering a turn, when the
    author tries to start a side chat, then start is refused until the
    turn ends.
- **Source:** `[confirmed: user]` interview 2026-09-20, "augment round —
  side chats", brief; C2; D1.

### US-136 — The assistant sees the whole conversation while a side chat is active
- **Feature:** FEAT-022 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-115
- **Status:** proposed
- **Story:** As an author, I want the assistant to see the conversation so
  far and the side chat while it's active, so that the side task gets
  full context.
- **Acceptance criteria:**
  - **US-136.AC-1** — Given a side chat is active, when the author sends
    a turn inside it, then a fact stated only in the main conversation
    before the side chat started is available to that turn.
  - **US-136.AC-2** — Given a side chat is active with its own earlier
    messages, when the author sends a further turn inside it, then a
    fact stated only earlier in the side chat is available to that turn.
- **Source:** `[confirmed: user]` interview 2026-09-20, "augment round —
  side chats", brief; default D3. Falsifiability note: tested the way the
  FEAT-021 promises are — a fact stated only in the side chat is
  available to a turn inside it.

### US-137 — Author finishes a side chat and it collapses, readable but closed
- **Feature:** FEAT-022 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-111
- **Status:** proposed
- **Story:** As an author, I want a finished side chat to collapse into
  one readable group, so that it stays out of the way without
  disappearing.
- **Acceptance criteria:**
  - **US-137.AC-1** — Given an active side chat, when the author
    finishes it, then it collapses into one group in the history, in
    place.
  - **US-137.AC-2** — Given a collapsed side-chat group, when the author
    expands it, then its messages are shown.
  - **US-137.AC-3** — Given a finished side chat, when the author tries
    to send a message into it, then no message can be sent.
- **Source:** `[confirmed: user]` interview 2026-09-20, "augment round —
  side chats", brief; C7.

### US-138 — A finished side chat no longer reaches the assistant
- **Feature:** FEAT-022 · **Actor:** ACT-004, ACT-005 · **Realizes:**
  UC-115, UC-111
- **Status:** proposed
- **Story:** As an author, I want a finished side chat excluded from
  later main-line turns, so that the detour doesn't linger in the
  assistant's view.
- **Acceptance criteria:**
  - **US-138.AC-1** — Given a finished side chat, when the author sends
    the next main-line turn, then a fact stated only in that side chat
    is not available to it.
  - **US-138.AC-2** — Given a finished side chat, when the author
    reopens the chat later, then it is still present in the history.
- **Source:** `[confirmed: user]` interview 2026-09-20, "augment round —
  side chats", brief; C5. Consistent with US-095.AC-2.

### US-139 — Author injects a side chat and its messages become ordinary
- **Feature:** FEAT-022 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-112
- **Status:** proposed
- **Story:** As an author, I want to fold a side chat back into the main
  conversation, so that I can keep it in view going forward.
- **Acceptance criteria:**
  - **US-139.AC-1** — Given a side chat, when the author injects it,
    then its messages appear as ordinary main-line messages in their
    original order.
  - **US-139.AC-2** — Given injected messages, when the author sends the
    next main-line turn, then a fact stated only in those messages is
    available to it.
  - **US-139.AC-3** — Given injected messages, when the author looks for
    side-chat actions on them, then none are offered.
- **Source:** `[confirmed: user]` interview 2026-09-20, "augment round —
  side chats", brief; C6.

### US-140 — Author deletes a side chat after confirming; saved work survives
- **Feature:** FEAT-022 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-113
- **Status:** proposed
- **Story:** As an author, I want to permanently remove a side chat I
  don't want kept, so that it isn't left cluttering the history.
- **Acceptance criteria:**
  - **US-140.AC-1** — Given the author asks to delete a side chat, when
    the request is made, then the system asks for confirmation first.
  - **US-140.AC-2** — Given the confirmation, when the author declines
    it, then nothing changes.
  - **US-140.AC-3** — Given the confirmation, when the author confirms,
    then every message of that side chat is removed from the history.
  - **US-140.AC-4** — Given a codex entry or chapter edit saved during
    the side chat, when the side chat is deleted, then it is still
    present afterwards.
- **Source:** `[confirmed: user]` interview 2026-09-20, "augment round —
  side chats", brief; C4; D4.

### US-141 — A side chat survives leaving and returning
- **Feature:** FEAT-022 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-114
- **Status:** proposed
- **Story:** As an author, I want an active side chat to still be active
  when I come back, so that leaving mid-task doesn't lose my place.
- **Acceptance criteria:**
  - **US-141.AC-1** — Given a side chat active when the author leaves
    and returns, when they send their next message, then it lands in
    that side chat.
- **Source:** `[confirmed: user]` interview 2026-09-20, "augment round —
  side chats", default D2.
<!-- product-spec:end -->
