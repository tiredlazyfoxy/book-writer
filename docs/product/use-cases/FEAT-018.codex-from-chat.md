<!-- product-spec:start -->
# Use Cases — FEAT-018 Codex authoring from the composition chat

### UC-076 — Generate a codex entry from a composition chat
- **Feature:** FEAT-018 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A composition chat exists (FEAT-013); a codex entry
  of the desired kind is open (or opened blank) in the content pane.
- **Main flow:**
  1. Author opens a blank codex entry of a given kind in the content pane
     and asks the chat to generate it.
  2. Assistant writes the draft directly into the open entry, on the
     shared canvas.
  3. Author may hand-edit the draft before saving.
  4. Author saves. System adds the entry to the codex per the book's
     collaboration mode (FEAT-017).
- **Exception flow:** LLM is unreachable or returns nothing → same as UC-056
  (composition request fails); not respecced here. Author asks the
  assistant to write a **name** into a **fact** entry → the write is
  refused and the entry is unchanged; a fact has no name (US-078.AC-2),
  and the body is where its content goes. The refusal reaches the author
  in the conversation (UC-102) rather than passing silently.
  `[confirmed: user]` interview 2026-08-10, "finalization — plans 023 +
  024"; challenge C-f2324-7.
- **Postconditions:** Draft exists on the shared canvas until explicitly
  saved; nothing is added to the codex before the save request. **Revised,
  round 5:** the draft lands directly in the open entry in the content
  pane, not shown as a separate chat message first.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4:
  "when I'm chatting and write the block - i can ask LLM to generate the
  cahracter or rewrite/edit the character, or location or some lore fact.";
  "Shown in the chat first, saved only on explicit request. Mirrors UC-055.";
  interview 2026-07-23, "Augment round 5", "the working page — two-pane,
  chat + content": "author opens a blank character in the pane → 'write
  character' → assistant fills it."

### UC-077 — Rewrite an existing codex entry from a composition chat
- **Feature:** FEAT-018 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A composition chat exists; an existing codex entry is
  open in the content pane.
- **Main flow:**
  1. Author opens an existing codex entry in the content pane and asks the
     chat to rewrite it.
  2. Assistant writes the rewritten draft directly into the open entry, on
     the shared canvas.
  3. Author may hand-edit the draft before saving.
  4. Author saves. System applies the rewrite to the entry per the book's
     collaboration mode (FEAT-017).
- **Exception flow:** LLM is unreachable or returns nothing → same as UC-056;
  not respecced here.
- **Postconditions:** Rewritten draft exists on the shared canvas until
  explicitly saved; the entry is unchanged before the save request.
  **Revised, round 5:** the draft lands directly in the open entry in the
  content pane, not shown as a separate chat message first.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4:
  "or rewrite/edit the character, or location or some lore fact."; "Does
  editing an existing entry from the chat take the same path? Yes — same
  review-then-save."; interview 2026-07-23, "Augment round 5", "the
  working page — two-pane, chat + content".
<!-- product-spec:end -->
