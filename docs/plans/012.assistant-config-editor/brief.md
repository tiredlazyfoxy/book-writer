# 012.assistant-config-editor — Assistant configuration (admin)
<!-- roadmap:start -->
- **Stage:** 3.workspace · **Track:** multi-step · **Size:** L
- **Delivers:** FEAT-020, UC-095, UC-096, UC-097, US-110, US-111, US-112,
  US-113, US-114
- **Depends on:** `008.data-domain`

## Definition
Admin-only screen in the admin SPA to configure the assistant. Edit each of
the five fixed modes' system prompts and select which tools and sub-agents
each mode may use. Create, edit and disable (never delete) sub-agents, each
with its own system prompt, an optional model assignment (a specific
configured server+model, or inherit the main chat's model), and its own tool
selection. Wire modes and sub-agents together from either the mode view or the
sub-agent view — one link, two editors.

## Scope
**In:** five mode prompt editors; per-mode tool selection (`mode_tool`);
per-mode sub-agent selection (`mode_subagent`, mode side); sub-agent CRUD +
disable + model assignment (both-null-or-both-set; half-set refused) + tool
selection (`subagent_tool`) + mode selection (`mode_subagent`, sub-agent
side); `require_role(admin)`; the `services/assistant_config.py` CRUD with
name-unique + model-pair-invariant checks.
**Out:** the runtime that consumes this config (`013.codex`); the tool
implementations (registry is code; tools land with their owning features);
the author-facing book system prompt (`fast/003.book-system-prompt`) and
chapter system prompt (`014.chapter-skeleton`); main-chat model selection
(deferred FEAT-013).

## Open questions for the planner
- Candidate split — mode configuration vs. sub-agent management (they share
  the `mode_subagent` link edited from both views, which argues for one
  feature; planner decides).
- Whether a mode's tools default on or off before the admin configures it
  (product-open `_TBD:` in `assistant-config.md`).
- Where the five modes are seeded — here vs. `008`.
<!-- roadmap:end -->
