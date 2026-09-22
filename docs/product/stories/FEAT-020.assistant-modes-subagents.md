<!-- product-spec:start -->
# Stories — FEAT-020 Assistant modes & sub-agents

### US-110 — Admin sets a mode's optional system prompt
- **Feature:** FEAT-020 · **Actor:** ACT-001 · **Realizes:** UC-095
- **Status:** delivered
- **Story:** As an admin, I want to set an optional system prompt on a
  working mode, so that the assistant carries standing instructions
  whenever it runs in that mode.
- **Acceptance criteria:**
  - **US-110.AC-1** — Given an admin writes and saves a mode's system
    prompt, when the save completes, then the prompt is stored on the
    mode.
  - **US-110.AC-2** — Given a non-admin, when they attempt to set a
    mode's system prompt, then the action is refused.
  - **US-110.AC-3** — Given a mode with a saved system prompt, when the
    assistant runs in that mode, then the prompt is applied.
  - **US-110.AC-4** — Given a mode with an empty system prompt, when the
    assistant runs in that mode, then nothing is added on its behalf.
- **Source:** `[confirmed: user]` interview 2026-07-24, "FEAT-020 —
  assistant modes & sub-agents (augment round 8)".

### US-111 — Admin sets which tools a mode may use
- **Feature:** FEAT-020 · **Actor:** ACT-001 · **Realizes:** UC-095
- **Status:** delivered
- **Story:** As an admin, I want to choose which tools are available to
  the assistant in a given mode, so that its capabilities match what
  that mode is for.
- **Acceptance criteria:**
  - **US-111.AC-1** — Given an admin selects a set of tools for a mode
    and saves, when the save completes, then that tool set is stored on
    the mode.
  - **US-111.AC-2** — Given a tool not selected for a mode, when the
    assistant runs in that mode, then that tool is unavailable to it.
- **Source:** `[confirmed: user]` interview 2026-07-24, "FEAT-020 —
  assistant modes & sub-agents (augment round 8)".

### US-112 — Admin sets which sub-agents a mode may delegate to
- **Feature:** FEAT-020 · **Actor:** ACT-001 · **Realizes:** UC-095
- **Status:** delivered
- **Story:** As an admin, I want to choose which sub-agents a mode can
  delegate to, so that the assistant hands off scoped work only where
  I've allowed it.
- **Acceptance criteria:**
  - **US-112.AC-1** — Given an admin selects sub-agents for a mode and
    saves, when the save completes, then those sub-agents are stored as
    accessible from that mode.
  - **US-112.AC-2** — Given a mode with accessible sub-agents set, when
    an admin opens one of those sub-agents, then the same link is shown
    there and is editable from that view too.
  - **US-112.AC-3** — Given a mode's set of accessible sub-agents, when
    the assistant runs in that mode, then it may delegate only to
    sub-agents in that set.
- **Source:** `[confirmed: user]` interview 2026-07-24, "FEAT-020 —
  assistant modes & sub-agents (augment round 8)".

### US-113 — Admin creates a sub-agent
- **Feature:** FEAT-020 · **Actor:** ACT-001 · **Realizes:** UC-096
- **Status:** delivered
- **Story:** As an admin, I want to create a sub-agent with a name,
  prompt, tools, accessible modes and model, so that I have a reusable
  delegated worker for scoped tasks.
- **Acceptance criteria:**
  - **US-113.AC-1** — Given an admin submits a unique name, prompt, tool
    selection and mode selection, when they save, then the sub-agent is
    created with those values.
  - **US-113.AC-2** — Given a newly created sub-agent, when an admin
    opens one of its named modes, then the sub-agent appears as
    accessible from it.
  - **US-113.AC-3** — Given a name already used by another sub-agent,
    when an admin attempts to save with it, then the action is refused.
  - **US-113.AC-4** — Given a non-admin, when they attempt to create a
    sub-agent, then the action is refused.
  - **US-113.AC-5** — Given an admin creating a sub-agent assigns a
    specific model (from those the configured LLM servers offer), when
    they save, then that model is stored on the sub-agent.
  - **US-113.AC-6** — Given an admin creates a sub-agent without
    assigning a model, when they save, then the sub-agent's model is
    recorded as re-use-the-main-chat's-model (the default).
- **Source:** `[confirmed: user]` interview 2026-07-24, "FEAT-020 —
  assistant modes & sub-agents (augment round 8)"; interview 2026-07-24,
  "FEAT-020 — sub-agent model assignment (augment round 9)".

### US-114 — Admin edits or disables a sub-agent
- **Feature:** FEAT-020 · **Actor:** ACT-001 · **Realizes:** UC-097
- **Status:** delivered
- **Story:** As an admin, I want to edit a sub-agent's fields — name,
  prompt, tools, accessible modes, model — or disable it, so that I can
  correct its configuration or retire it while keeping the option to
  bring it back.
- **Acceptance criteria:**
  - **US-114.AC-1** — Given an admin edits a sub-agent's name, prompt,
    tools or accessible modes and saves, when the save completes, then
    the changes are stored.
  - **US-114.AC-2** — Given a sub-agent referenced by one or more modes,
    when an admin disables it, then it is detached from every mode that
    referenced it and can no longer be invoked.
  - **US-114.AC-3** — Given a disabled sub-agent, when an admin
    re-enables it, then it stays unattached from every mode until a
    mode selects it again.
  - **US-114.AC-4** — Given an admin changes a sub-agent's model
    assignment (to a specific model, or back to inheriting the main
    chat's), when they save, then the new choice is stored.
- **Source:** `[confirmed: user]` interview 2026-07-24, "FEAT-020 —
  assistant modes & sub-agents (augment round 8)"; interview 2026-07-24,
  "FEAT-020 — sub-agent model assignment (augment round 9)".
<!-- product-spec:end -->
