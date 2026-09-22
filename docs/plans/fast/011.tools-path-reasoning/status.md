# Fast feature 011 — tools-path-reasoning

| Status  | Verifier | Date       |
|---------|----------|------------|
| done    | PASS     | 2026-09-17 |

## Files Changed

- `backend/pyproject.toml` — `llm-client` git pin advanced `@v0.1.4` → `@v0.1.5` (DoD-1)
- `backend/app/services/chat_turn.py` — `build_sampling_options` body + docstring: two-arm rule, `enable_thinking` alone crosses to the OpenAI path (DoD-2..DoD-6)

## Skeleton

### Frozen interface (2026-09-17)

This feature adds **no new symbol and changes no signature**. Nothing was stubbed;
no source file was modified by the skeleton pass. The record below freezes the
*existing* contract verbatim so the test-coder can bind to it without reading source.

- `backend/app/services/chat_turn.py` — `build_sampling_options(sampling: ChatSamplingParams, backend_type: str) -> dict[str, object]` — **unchanged** (pre-existing, frozen as-is; only the body and docstring change under this plan). Defined at line 245.

Verbatim signature:

```python
def build_sampling_options(
    sampling: ChatSamplingParams, backend_type: str
) -> dict[str, object]:
```

Import for tests: `from app.services import chat_turn` then `chat_turn.build_sampling_options(...)` (the existing test module already uses this form).

- Caller-compile edits (out of Source-files scope): None. The sole production call site, `backend/app/services/chat_turn.py:934` — `options = build_sampling_options(sampling, server.backend_type)` — is **not changing**; the signature is untouched, so no caller adaptation exists.

### `ChatSamplingParams` — construction reference

`backend/app/models/schemas/chats.py:53` (a Pydantic `BaseModel`). Import:
`from app.models.schemas.chats import ChatSamplingParams`. All ten fields have
defaults, so `ChatSamplingParams()` is valid and any subset may be passed by keyword.

| Field | Type | Default |
|-------|------|---------|
| `temperature` | `float` | `0.8` |
| `top_p` | `float` | `0.95` |
| `top_k` | `int` | `40` |
| `repeat_penalty` | `float` | `1.1` |
| `min_p` | `float` | `0.05` |
| `max_tokens` | `int \| None` | `None` |
| `seed` | `int \| None` | `None` |
| `presence_penalty` | `float` | `0.0` |
| `frequency_penalty` | `float` | `0.0` |
| `enable_thinking` | `bool` | `True` |

The key names in the returned mapping are exactly these field names (the
`"llama-swap"` arm returns `sampling.model_dump()`, i.e. all ten keys).

### Compile gate

The root `CLAUDE.md` declares **no static type-check for the backend**; the backend
gate is `cd backend && .venv/Scripts/python -m pytest`. Since no file was written,
no compile gate was run — there is nothing new to compile. `backend/pyproject.toml`
was deliberately left untouched: the `@v0.1.5` pin bump is the coder's DoD-1 edit,
not an interface concern.

## Tests

### Tests (2026-09-17)

- `backend/tests/services/test_chat_turn.py` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5 — the `llm-client` `@v0.1.5` pin plus the two-arm `build_sampling_options` rule (`llama-swap` full dump preserved; everything else gets `enable_thinking` alone, value taken from the passed params).
- The superseded `test_sampling_options_llama_swap_only__DoD6` (old `openai` → `{}` assertion) was replaced in place by the five new tests; no other test file touched (`test_think_splitter.py` untouched, per DoD-8).
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓ (preservation clause — green at the red gate by design), DoD-5 ✓, DoD-6 [manual/live, no test], DoD-7 [manual/live, no test], DoD-8 [manual/live, verifier regression guard, no test], DoD-9 [manual/live, no test]

## Notes & Issues

- **DoD-7 outstanding — needs the project's reinstall command from the user.** The pin bump alone changes nothing at runtime: `backend/.venv` still holds `llm_client-0.1.4`. No install/sync command is documented in the root `CLAUDE.md` for the backend venv, so none was invented and the venv was not modified. Check after reinstall with `cd backend && .venv/Scripts/python -c "import importlib.metadata as m; print(m.version('llm-client'))"`.
- No backend static type-check is configured (root `CLAUDE.md`); the changed module was syntax-compiled only. Tests were not run — the verifier owns that gate.
- **DoD-7 resolved by the orchestrator (2026-09-17)** — the note above is retained as the coder's record but is no longer outstanding. The reinstall the coder correctly declined to invent was run with the user's chosen tool: `uv pip install --python .venv/Scripts/python.exe --reinstall-package llm-client "llm-client @ git+https://github.com/Iezious/PythonLLMClient.git@v0.1.5"` from `backend/`. `backend/.venv` now reports `llm-client 0.1.5` (commit `7c27d6b`), and the installed `_stream_openai_tools_response` carries both `reasoning_content` and the `in_reasoning` state machine. The command has been added to the root `CLAUDE.md` so the next agent is not blocked the same way.
- **Air-gap incident, adjudicated.** The coder's final `git diff -- backend/` self-review printed the test file into its context after implementation was complete. The verifier assessed this explicitly and found the implementation "written to the spec, not to the tests" — the change keeps the plan-mandated `!= "llama-swap"` branch shape, special-cases no `backend_type` string, and satisfies DoD-3 structurally rather than by a hardcoded value. No evidence the exposure influenced the code. Worth scoping future coder self-review diffs to the plan's Source files.
