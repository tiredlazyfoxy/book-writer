# Fast feature 011 — tools-path-reasoning — context

## What this feature is

Assistant *thinking* was specified to stream into the chat pane inside a collapsible block, and it never appears. Investigation established that **every layer BookWriter owns already works**: `ThinkSplitter` splits the tags, the backend emits `thinking` SSE frames, `chatPaneState` buffers them, `ThinkingBlock.tsx` renders the collapsible region, and `ChatMessage.reasoning` persists it. The defect was one layer down, inside the `llm-client` dependency.

That dependency has been fixed and released upstream. This feature makes BookWriter **consume** the fix. It is a dependency bump plus one small behavioural correction in the options mapping — nothing in the streaming, splitting, framing or persistence path changes.

## The upstream fix — `llm-client v0.1.5`

- Tag `v0.1.5` on `github.com/Iezious/PythonLLMClient` (commit `7c27d6b`), the successor to the currently pinned `v0.1.4`.
- `_stream_openai_tools_response` now reads `reasoning_content` from the delta and streams it through `on_delta` **wrapped in `<think>` / `</think>`**, driven by a per-round `in_reasoning` state machine.
- Reasoning is **streamed only** and deliberately **not** included in the parser's returned content string, so the tool loop's message history stays clean.
- The return signature `tuple[str, list[dict]]` is **unchanged**. No call-site adaptation is needed anywhere in BookWriter.

**Consequence for `ThinkSplitter`: none.** v0.1.5 emits the tags *inline into the `on_delta` text stream* — byte-for-byte the shape the splitter was already built to consume (it was written for `--reasoning-format none`, which inlines the same tags into `content`). The splitter is correct as it stands.

## Files involved

| File | Role in this feature |
|------|----------------------|
| `backend/pyproject.toml` | line 16 pins `"llm-client @ git+https://github.com/Iezious/PythonLLMClient.git@v0.1.4"` — the pin to bump |
| `backend/app/services/chat_turn.py` | `build_sampling_options` (lines 245–261) — the options gate to correct |
| `backend/tests/services/test_chat_turn.py` | holds `test_sampling_options_llama_swap_only__DoD6` (line 438), whose `openai` half becomes wrong |

There is **no lock file in the repository** recording this dependency — confirmed: no `uv.lock`, no `requirements.lock`, no `poetry.lock`. The pin in `pyproject.toml` is the only recorded version, and the dependency must be **reinstalled into `backend/.venv`** for the bump to take effect. The venv currently holds `llm_client-0.1.4`.

## `build_sampling_options` as it stands

`backend/app/services/chat_turn.py:245-261`. Takes a `ChatSamplingParams` and a `backend_type` string, returns the `options` mapping passed to `chat_with_tools`. Today it returns `{}` for any `backend_type != "llama-swap"` and `sampling.model_dump()` otherwise — so an `openai` server receives `enable_thinking` **never**.

- Sole production call site: `chat_turn.py:934` — `options = build_sampling_options(sampling, server.backend_type)`, where `sampling` comes from `chats_service._parse_sampling(chat.sampling_params)` (line 933) and `server` is the `LlmServer` on `TurnContext.server`. The result flows into the `chat_with_tools(..., options=options, stream=True, on_delta=on_delta)` call at lines 977–995.
- The **signature does not change** — only the body and the docstring.

## `ChatSamplingParams`

`backend/app/models/schemas/chats.py:53-74`. Ten fields with defaults: `temperature: float = 0.8`, `top_p: float = 0.95`, `top_k: int = 40`, `repeat_penalty: float = 1.1`, `min_p: float = 0.05`, `max_tokens: int | None = None`, `seed: int | None = None`, `presence_penalty: float = 0.0`, `frequency_penalty: float = 0.0`, **`enable_thinking: bool = True`**.

## `backend_type` — the two accepted values

`backend_type` is a bare `str` on `LlmServer` (`backend/app/models/llm_server.py:47`), validated at the service level against `_VALID_BACKEND_TYPES: set[str] = {"llama-swap", "openai"}` (`backend/app/services/llm_servers.py:44`). Those are the **only two values the system accepts**; the write edge rejects anything else, so no third value can reach `build_sampling_options` from a stored row.

## Decision history this feature touches

- **Feature `011.chat-panel`, decision 4 / DoD-6** established the blanket gate: sampling params go to `llama-swap` servers only. The reasoning — llama.cpp-specific params (`top_k`, `repeat_penalty`, `min_p`) do not belong on an OpenAI endpoint — **still holds and is preserved**. This feature reverses it **narrowly**, for `enable_thinking` alone, because that is the one param in the set the OpenAI path genuinely supports (the `llm` library maps it to `reasoning_effort` for OpenAI models).
- **Feature `024.chat-agent-loop`, decision D3** (`docs/plans/024.chat-agent-loop/plan.md:353-358`, Risk entry at `:404-407`) considered patching the `llm` dependency (~10 LoC) and **rejected** it, accepting the limitation as `[manual/live]` and "not claimed as delivered". This feature **reverses D3** — the patch happened after all, upstream.

## Architecture statements this feature invalidates

- `docs/architecture/backend/features.md` opens with **"Deployment requirement — llama.cpp must run with `--reasoning-format none`"** (`**Realizes:** FEAT-013`, operational constraint). It states the reasoning is discarded *inside the library* and that "there is no place in BookWriter's code where it could be recovered." **v0.1.5 makes that statement false.**
- The same requirement is mirrored at `docs/architecture/backend.md:104`, `docs/architecture/system-overview.md:166` and `docs/architecture/quick-reference.md:107`.
- `docs/architecture/backend.md:98` additionally pins the tag verbatim: "keep the git URL and `@v0.1.4` tag verbatim."

All four (five, counting the verbatim pin) are recorded in `outcome.md` for the architect to apply at finalization. **This feature writes no doc changes itself.**

- The seven-frame SSE vocabulary in `docs/architecture/assistant-runtime.md` is **unchanged** by this feature.

## Product ids — caution

**No `FEAT`/`UC`/`US`/`AC` in `docs/product/` mandates streamed collapsible thinking.** It entered the system through `011.chat-panel`'s `context.md` decisions 7/8, not through a requirement. FEAT-013 is the owning feature and the deployment requirement is recorded under it as an *operational constraint*. **Do not invent or cite a UC/US id for the thinking display.** The missing acceptance criterion is surfaced in `outcome.md` as a `/product-spec` follow-up and nothing more.

## Build & test commands

From the root `CLAUDE.md` — do not invent others:

- Backend tests: `cd backend && .venv/Scripts/python -m pytest`
- Always invoke Python as `.venv/Scripts/python`; never `python` from PATH.
- No backend static type-check is configured. No linter is configured.
