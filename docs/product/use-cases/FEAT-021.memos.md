<!-- product-spec:start -->
# Use Cases — FEAT-021 Memos

### UC-103 — Create a memo
- **Feature:** FEAT-021 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Author is a member of the book.
- **Main flow:**
  1. Author opens the book's **Memos** navigator entry.
  2. System renders the author's own memos as a list, private to them.
  3. Author creates a new memo.
  4. System appends it last in the list and focuses it immediately, active.
- **Postconditions:** A new, empty, active memo exists at the end of the
  author's list, ready to be written in.
- **Source:** `[confirmed: user]` interview 2026-09-15, "augment round —
  memos", collected brief: "There is NO 'memo' page — just a list...
  Where does a new memo go? Last in the list, and immediately focused."

### UC-104 — Edit a memo in place
- **Feature:** FEAT-021 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A memo belonging to the author exists in the list.
- **Main flow:**
  1. Author opens a memo's body in the list.
  2. Author types into it.
  3. Author moves focus away from the memo.
  4. System saves the memo's body.
- **Postconditions:** The memo's body persists as last edited; no explicit
  save action exists or is required.
- **Source:** `[confirmed: user]` interview 2026-09-15, "augment round —
  memos", collected brief: "In place, saved immediately on focus lost."

### UC-105 — Reorder memos
- **Feature:** FEAT-021 · **Actor:** ACT-004, ACT-005
- **Preconditions:** The author's memo list has two or more memos.
- **Main flow:**
  1. Author drags a memo to a new position, or uses an arrow control on
     one.
  2. System reorders the list to match.
- **Postconditions:** The list's new order is the order the assistant
  receives the author's active memos in (UC-109); where that block sits
  relative to chapter text, summaries or state notes is not stated here.
- **Source:** `[confirmed: user]` interview 2026-09-15, "augment round —
  memos", collected brief: "Reorderable by drag-and-drop and by
  arrows."; challenge CP3.

### UC-106 — Switch a memo off and on
- **Feature:** FEAT-021 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A memo belonging to the author exists in the list,
  active or inactive.
- **Main flow:**
  1. Author toggles a memo's active/inactive icon in its header.
  2. If the memo was active, system marks it inactive: it stays in the
     list, visibly off, and is left out of context.
  3. If the memo was inactive, system marks it active: it is included in
     context again.
- **Alternate flow:** Author deactivates their last remaining active
  memo → allowed; the author simply has no active memo until they switch
  one on again.
- **Postconditions:** Each memo's active/inactive state is independent of
  every other memo's; there is no book-level memos-off switch.
- **Source:** `[confirmed: user]` interview 2026-09-15, "augment round —
  memos", challenges C2, C9.

### UC-107 — Archive and restore a memo
- **Feature:** FEAT-021 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A memo belonging to the author exists.
- **Main flow:**
  1. Author archives a memo from its header.
  2. System removes it from the working list; it is out of context.
  3. Author opens their archived memos.
  4. Author restores one.
  5. System returns it to the working list.
- **Postconditions:** No memo is ever hard-deleted; an archived memo
  remains recoverable indefinitely.
- **Source:** `[confirmed: user]` interview 2026-09-15, "augment round —
  memos", challenge C7 — follows FEAT-017's codex archive pattern (UC-072).

### UC-108 — Assistant creates a memo on request
- **Feature:** FEAT-021 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A composition chat is active for the author; the
  current mode is granted the create-memo tool (FEAT-020).
- **Main flow:**
  1. Author directly asks the assistant to create a memo.
  2. Assistant calls the create-memo tool with the memo's content.
  3. System creates the memo, active, last in the author's list.
- **Alternate flow:** The author asks with no memos list open → the memo
  is still created; an open list is not a precondition.
- **Exception flow:** The current mode is not granted the create-memo
  tool (FEAT-020) → the request is refused, visibly (UC-102).
- **Postconditions:** A new active memo exists at the end of the
  author's list, exactly as UC-103 would produce.
- **Source:** `[confirmed: user]` interview 2026-09-15, "augment round —
  memos", collected brief: "by the AI via a 'create memo' tool to be
  added."; round-1 challenge C3 (US-121.AC-3 precedent).

### UC-109 — Active memos reach every assistant run
- **Feature:** FEAT-021 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Author has at least one active memo.
- **Main flow:**
  1. Author sends a turn to the assistant, in any of FEAT-020's five
     modes, or the assistant delegates to a sub-agent.
  2. System includes every one of the author's active memos in that
     run's context, in the author's set order.
  3. Inactive and archived memos are excluded.
- **Postconditions:** The assistant's context always carries the
  author's current active memos, in their order, regardless of mode or
  sub-agent delegation. There is no get-memos tool — nothing to fetch,
  because every active memo is already present.
- **Source:** `[confirmed: user]` interview 2026-09-15, "augment round —
  memos", collected brief; challenge C6.
<!-- product-spec:end -->
