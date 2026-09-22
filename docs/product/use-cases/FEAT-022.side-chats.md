<!-- product-spec:start -->
# Use Cases — FEAT-022 Side chats

### UC-110 — Start a side chat
- **Feature:** FEAT-022 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A composition chat is active; no side chat is
  currently active in it.
- **Main flow:**
  1. Author starts a side chat from within the composition chat.
  2. System marks a side chat active for this composition chat.
  3. From here on, the author's messages and the assistant's answers
     belong to the side chat and are visibly set apart from the main
     line.
- **Alternate flow:** The main conversation has no messages yet → start
  is allowed; the side chat simply starts at the top.
- **Exception flow:** A side chat is already active → start is
  unavailable (one level, C2).
- **Exception flow:** The assistant is answering a turn → start is
  unavailable until the turn ends (D1).
- **Postconditions:** The composition chat has exactly one active side
  chat; subsequent messages belong to it.
- **Source:** `[confirmed: user]` interview 2026-09-20, "augment round —
  side chats", brief; C2; D1.

### UC-111 — Finish a side chat
- **Feature:** FEAT-022 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A side chat is active.
- **Main flow:**
  1. Author finishes the active side chat.
  2. System collapses it into one group in the history, in place.
  3. The group can be expanded to read its messages and collapsed again.
- **Exception flow:** The assistant is answering a turn → finish is
  unavailable until the turn ends (D1).
- **Postconditions:** The finished side chat is not resumable — a new
  topic means a new side chat (C7); its messages no longer reach the
  assistant in later main-line turns (UC-115); nothing from it is
  carried into the main line — a stated assumption, not evidenced (CS3).
- **Source:** `[confirmed: user]` interview 2026-09-20, "augment round —
  side chats", brief; C5; C7; D1.

### UC-112 — Inject a side chat into the main conversation
- **Feature:** FEAT-022 · **Actor:** ACT-004, ACT-005
- **Preconditions:** An active or a finished side chat exists in the
  composition chat.
- **Main flow:**
  1. Author injects the side chat.
  2. If it was active, system ends it and merges its messages into the
     main line, in place.
  3. If it was finished, system expands it back into the main line, in
     place.
  4. The side chat's messages become ordinary main-line messages,
     keeping their order.
- **Exception flow:** The assistant is answering a turn → inject is
  unavailable until the turn ends.
- **Postconditions:** The injected messages reach the assistant from the
  next turn on; they offer no side-chat actions and cannot be
  re-grouped — one-way (C6).
- **Source:** `[confirmed: user]` interview 2026-09-20, "augment round —
  side chats", brief; C6.

### UC-113 — Delete a side chat
- **Feature:** FEAT-022 · **Actor:** ACT-004, ACT-005
- **Preconditions:** An active or a finished side chat exists in the
  composition chat (D8).
- **Main flow:**
  1. Author asks to delete the side chat.
  2. System asks for confirmation.
  3. Author confirms.
  4. System removes every message of the side chat from the history
     permanently; none of it reaches the assistant again.
- **Alternate flow:** Author declines the confirmation → nothing
  changes.
- **Exception flow:** The assistant is answering a turn → delete is
  unavailable until the turn ends.
- **Postconditions:** Anything the author saved during the side chat (a
  codex entry, a chapter edit, a memo) survives untouched (D4).
- **Source:** `[confirmed: user]` interview 2026-09-20, "augment round —
  side chats", brief; C4; D4; D8.

### UC-114 — Leave and return with a side chat active
- **Feature:** FEAT-022 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A side chat is active in a composition chat.
- **Main flow:**
  1. Author leaves the chat (switches chat, navigates away) while the
     side chat is active.
  2. Author returns to the composition chat.
  3. System shows the side chat still active.
  4. Author's next message lands in the side chat.
- **Postconditions:** Nothing is auto-finished by leaving.
- **Source:** `[confirmed: user]` interview 2026-09-20, "augment round —
  side chats", default D2.

### UC-115 — What the assistant is told while and after a side chat
- **Feature:** FEAT-022 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A composition chat exists, with or without a side
  chat in its history.
- **Main flow:**
  1. While a side chat is active, the assistant is told the main
     conversation up to the start point and the side chat.
  2. After the side chat finishes, later main-line turns are told the
     main conversation without that side chat.
  3. After the side chat is injected, later turns are told it again as
     part of the main line.
  4. After the side chat is deleted, it is never told to the assistant
     again.
- **Postconditions:** Inside a side chat, the assistant's mode, tools
  and canvas writes are unchanged from the main line (D3) — a side chat
  changes what the assistant is told about the conversation, nothing
  else. No statement here about how the transcript is assembled, stored
  or marked (CS1) — see `vision.md`.
- **Source:** `[confirmed: user]` interview 2026-09-20, "augment round —
  side chats", brief; C5; D3.
<!-- product-spec:end -->
