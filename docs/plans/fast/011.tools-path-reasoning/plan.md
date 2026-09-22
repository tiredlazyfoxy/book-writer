# Fast feature 011 — tools-path-reasoning

## Goal

Consume the `llm-client v0.1.5` fix that streams `reasoning_content` through `on_delta` wrapped in `<think>` / `</think>`: bump the dependency pin, and let an `openai`-backend server receive `enable_thinking` — the one sampling param the OpenAI path genuinely supports — so assistant thinking reaches the already-working chat-pane path.

## Source files

- `backend/pyproject.toml` — the `llm-client` git pin on line 16: `@v0.1.4` → `@v0.1.5`. No other dependency, no other line.
- `backend/app/services/chat_turn.py` — `build_sampling_options` (lines 245–261): body and docstring only.

Nothing else in `backend/app/` is in scope. In particular `ThinkSplitter`, the frame emission, `on_delta` and the `chat_with_tools` call site at lines 977–995 are untouched.

## Test files

- `backend/tests/services/test_chat_turn.py` — the existing `test_sampling_options_llama_swap_only__DoD6` (line 438) asserts `openai` → `{}`; that half becomes wrong under this change and must be reworked or replaced. The file already imports `ChatSamplingParams` and the `chat_turn` module, and has a section comment for these tests at lines 431–433.

`backend/tests/services/test_think_splitter.py` is **not** in this list and must not be touched — see Out of scope.

## Interface intent

### `build_sampling_options` (`backend/app/services/chat_turn.py`) — changed behaviour, unchanged signature

Same name, same two parameters (a `ChatSamplingParams` and the server's `backend_type` string), same return type (a mapping of option name to value). **Do not change the signature**; only the body and the docstring change.

The function decides which sampling options are forwarded to `chat_with_tools` for a turn, and it now has exactly two arms:

- **`"llama-swap"`** — unchanged from today: the **full** dump of the sampling params, every field, including the llama.cpp-specific `top_k` / `repeat_penalty` / `min_p`. Byte-for-byte the behaviour that shipped.
- **anything else (in practice `"openai"`)** — a mapping carrying **`enable_thinking` and nothing else**, its value taken from the passed sampling object rather than hardcoded. The key name is exactly the `ChatSamplingParams` field name.

Only `"llama-swap"` and `"openai"` can reach this function from a stored row (the service write edge validates against that pair), so the "anything else" arm exists to keep the function total and to mirror the existing `!= "llama-swap"` shape — everything that is not llama-swap is treated as an OpenAI-compatible endpoint. Do not add a third arm or raise on an unknown value.

**Docstring.** The current docstring states the old blanket rule ("an `openai` server gets **none** (an empty mapping) — user decision 4 / DoD-6") and is now wrong. Rewrite it to state the two-arm rule and to record *why* the reversal is narrow: the llama.cpp-specific params still do not belong on an OpenAI endpoint (feature `011.chat-panel` decision 4 / DoD-6 stands for them), and `enable_thinking` crosses alone because it is the one param in the set the OpenAI path supports — the `llm` library maps it to `reasoning_effort` for OpenAI models. Name this plan (`fast/011.tools-path-reasoning`) as the reversal's origin.

### `backend/pyproject.toml` — the pin

The `llm-client` entry keeps its exact form — same git URL, same `@`-tag syntax, same position in the dependency list — with the tag advanced to `v0.1.5`. Nothing else in the file changes: no new dependency, no version-range rewrite, no dev-extra change.

The dependency must then be **reinstalled into `backend/.venv`** for the bump to have any effect; there is no lock file to regenerate. If no install command is documented for this project, hand back rather than inventing one.

## Definition of done

1. **DoD-1** `[test]` — `backend/pyproject.toml` pins the `llm-client` dependency at tag `v0.1.5`: the dependency list contains the `github.com/Iezious/PythonLLMClient` git requirement ending `@v0.1.5`, and contains no reference to `@v0.1.4`.
2. **DoD-2** `[test]` — `build_sampling_options` called with `backend_type="openai"` returns a mapping whose **key set is exactly `{"enable_thinking"}`** — no `temperature`, no `top_p`, no `top_k`, no `repeat_penalty`, no `min_p`, and not empty.
3. **DoD-3** `[test]` — that returned `enable_thinking` value **reflects the passed sampling object**, not a constant: it is `True` when the sampling params carry `enable_thinking=True` and `False` when they carry `enable_thinking=False`.
4. **DoD-4** `[test]` — `build_sampling_options` called with `backend_type="llama-swap"` is **unchanged**: it returns the full sampling dump, carrying every `ChatSamplingParams` field — including `temperature`, `top_p`, `top_k`, `repeat_penalty`, `min_p` and `enable_thinking` — with the values from the passed object.
5. **DoD-5** `[test]` — a `backend_type` value that is neither `"llama-swap"` nor `"openai"` takes the OpenAI-compatible arm: the result's key set is exactly `{"enable_thinking"}`. The function neither raises nor returns an empty mapping.
6. **DoD-6** `[manual/live]` — `build_sampling_options`' docstring no longer claims an `openai` server gets no options; it states the two-arm rule, preserves the llama.cpp-param reasoning from feature `011.chat-panel` decision 4 / DoD-6, and records `enable_thinking` as the single deliberate exception. Verifier reads the docstring.
7. **DoD-7** `[manual/live]` — the `llm-client` distribution installed in `backend/.venv` reports version `0.1.5` (it currently holds `llm_client-0.1.4`). Checkable as a one-liner: `importlib.metadata.version("llm-client")` under `.venv/Scripts/python`. Without this reinstall the pin bump changes nothing at runtime.
8. **DoD-8** `[manual/live]` — **regression guard, checked by the verifier on the verify run, not a test obligation.** The backend suite (`cd backend && .venv/Scripts/python -m pytest`) is green; `backend/tests/services/test_think_splitter.py` is unmodified; and no test file outside `backend/tests/services/test_chat_turn.py` appears in the diff.
9. **DoD-9** `[manual/live]` — end-to-end against a live reasoning-capable server: an assistant turn streams `thinking` frames and the chat pane shows the collapsible thinking block, from an `openai`-backend server sending out-of-band `reasoning_content`. Depends on a real model server; cannot be asserted in CI.

## Out of scope

- **`ThinkSplitter` — no change whatsoever.** This is the most likely wrong turn. v0.1.5 emits `<think>` / `</think>` *inline into the `on_delta` text stream*, which is byte-for-byte the shape the splitter was already built to consume (it was written for `--reasoning-format none`, which inlines the same tags into `content`). The splitter, its module constants, and `backend/tests/services/test_think_splitter.py` are all **correct as they stand**. Do not add tag-awareness, do not de-duplicate tags, do not "handle the new case", do not add a second code path.
- **Any frontend change.** The whole frontend path — `chatPaneState` buffering, `ThinkingBlock.tsx`, the SSE reader — already works and is verified to work.
- **Any change to the SSE frame vocabulary**, the `thinking` frame payload, `ChatMessage.reasoning`, or persistence.
- **The `chat_with_tools` call site** at `chat_turn.py:977-995`, `on_delta`, and the sampling parse at line 933 — the upstream return signature `tuple[str, list[dict]]` is unchanged, so no call-site adaptation exists to make.
- **Any edit to `docs/architecture/`.** The four invalidated deployment-requirement statements and the verbatim `@v0.1.4` pin are recorded in `outcome.md` for the architect to apply at finalization.
- **Any edit to `docs/product/`.** The missing acceptance criterion for streamed collapsible thinking is a `/product-spec` follow-up noted in `outcome.md`; do not invent or cite a UC/US id for it.
- **The `llm-client` repository itself** — already fixed, tagged and pushed as `v0.1.5`.
- Widening any *other* sampling param to the OpenAI path. `enable_thinking` crosses alone.
