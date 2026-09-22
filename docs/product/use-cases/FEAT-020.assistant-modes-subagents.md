<!-- product-spec:start -->
# Use Cases — FEAT-020 Assistant modes & sub-agents

### UC-095 — Configure a working mode
- **Feature:** FEAT-020 · **Actor:** ACT-001
- **Preconditions:** Admin authenticated; the mode is one of the fixed
  system set of five.
- **Main flow:**
  1. Admin opens a mode.
  2. Admin sets or clears its system prompt.
  3. Admin selects its available tools.
  4. Admin selects its accessible sub-agents.
  5. Admin saves.
- **Exception flow:** A non-admin attempts to configure a mode →
  refused.
- **Postconditions:** The mode's configuration is stored and used by the
  assistant the next time it runs in that mode.
- **Source:** `[confirmed: user]` interview 2026-07-24, "FEAT-020 —
  assistant modes & sub-agents (augment round 8)".

### UC-096 — Create a sub-agent
- **Feature:** FEAT-020 · **Actor:** ACT-001
- **Preconditions:** Admin authenticated.
- **Main flow:**
  1. Admin creates a new sub-agent.
  2. Admin gives it a unique name.
  3. Admin sets its system prompt.
  4. Admin selects its available tools.
  5. Admin selects which modes may invoke it.
  6. Admin assigns a model, or leaves it to inherit the main chat's model.
  7. Admin saves.
- **Exception flow:** A duplicate or blank name → refused.
- **Postconditions:** The sub-agent exists and becomes selectable from
  the modes it was given access to.
- **Source:** `[confirmed: user]` interview 2026-07-24, "FEAT-020 —
  assistant modes & sub-agents (augment round 8)"; interview 2026-07-24,
  "FEAT-020 — sub-agent model assignment (augment round 9)".

### UC-097 — Edit or disable a sub-agent
- **Feature:** FEAT-020 · **Actor:** ACT-001
- **Preconditions:** Admin authenticated; the sub-agent exists.
- **Main flow:**
  1. Admin opens an existing sub-agent.
  2. Admin edits its name, prompt, tools, accessible modes, or model.
  3. Admin saves.
- **Alternate flow — Disable:** Admin disables the sub-agent instead of
  editing it. The sub-agent is detached from every mode that referenced
  it and can no longer be invoked. No hard delete.
- **Exception flow:** Admin attempts to save a blank or duplicate name →
  refused (same rule as UC-096).
- **Postconditions:** Edits are stored; disabling is reversible
  (re-enable), and a re-enabled sub-agent stays unattached from every
  mode until modes select it again.
- **Source:** `[confirmed: user]` interview 2026-07-24, "FEAT-020 —
  assistant modes & sub-agents (augment round 8)"; interview 2026-07-24,
  "FEAT-020 — sub-agent model assignment (augment round 9)".
<!-- product-spec:end -->
