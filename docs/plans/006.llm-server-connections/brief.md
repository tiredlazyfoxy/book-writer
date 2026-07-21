# 006.llm-server-connections — LLM server connections
<!-- roadmap:start -->
- **Stage:** 1.foundation · **Track:** multi-step · **Size:** M/L
- **Delivers:** FEAT-004, UC-010, UC-011, UC-012, UC-013, UC-014, US-010, US-011, US-012, US-013, US-014, US-021
- **Depends on:** `005.user-management`

## Definition
Admin registers, tests, and manages LLM server connections; probes and
enables specific models; designates one embedding server + model. API keys
use `$ENV_VAR` indirection and are never returned raw.

## Scope
**In:** register/edit/delete LLM server; test-connection + model probe;
enable models; embedding server+model designation; `$ENV` indirection +
secret masking; admin SPA settings pages; `llm-client` wiring.
**Out:** using models for generation (domain stages); DB consistency (007).

## Open questions for the planner
- Provider types at launch (OpenAI-compatible + llama-swap only)?
- Is the embedding designation what wires LanceDB (relates to 001's sidecar question)?
- Size may split — flag to planner.
<!-- roadmap:end -->
