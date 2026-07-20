<!-- product-spec:start -->
# Use Cases — FEAT-018 Codex authoring from the composition chat

### UC-076 — Generate a codex entry from a composition chat
- **Feature:** FEAT-018 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A composition chat exists (FEAT-013).
- **Main flow:**
  1. Author asks the chat to generate a codex entry of a given kind.
  2. LLM produces a draft entry, shown in the chat.
  3. Author requests the entry be saved.
  4. System adds the entry to the codex per the book's collaboration mode
     (FEAT-017).
- **Exception flow:** LLM is unreachable or returns nothing → same as UC-056
  (composition request fails); not respecced here.
- **Postconditions:** A draft entry exists in the chat until explicitly
  saved; nothing is added to the codex before the save request.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4:
  "when I'm chatting and write the block - i can ask LLM to generate the
  cahracter or rewrite/edit the character, or location or some lore fact.";
  "Shown in the chat first, saved only on explicit request. Mirrors UC-055."

### UC-077 — Rewrite an existing codex entry from a composition chat
- **Feature:** FEAT-018 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A composition chat exists; a codex entry exists to
  rewrite.
- **Main flow:**
  1. Author asks the chat to rewrite an existing codex entry.
  2. LLM produces a rewritten draft, shown in the chat.
  3. Author requests the rewrite be saved.
  4. System applies the rewrite to the entry per the book's collaboration
     mode (FEAT-017).
- **Exception flow:** LLM is unreachable or returns nothing → same as UC-056;
  not respecced here.
- **Postconditions:** A rewritten draft exists in the chat until explicitly
  saved; the entry is unchanged before the save request.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4:
  "or rewrite/edit the character, or location or some lore fact."; "Does
  editing an existing entry from the chat take the same path? Yes — same
  review-then-save."
<!-- product-spec:end -->
