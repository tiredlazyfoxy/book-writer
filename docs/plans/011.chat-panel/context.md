# 011.chat-panel — feature context

Feature-wide context. Step-specific facts live in each `<SSS>.context.md`; nothing is repeated
between the two files. The feature definition is `brief.md` (read-only).

## Goal

Make the chat pane live. Backend: chat CRUD private to its author, a per-chat `(server, model)` and
sampling set, the `TOOL_REGISTRY` scaffold with web search as its first tool, `base → mode → book →
chapter` prompt composition, and a streaming turn endpoint that drives the `llm` client's
`chat_with_tools` loop and splits `<think>` reasoning out of the token stream. Frontend: the chat
pane replacing 010's placeholder slot — list / pick / new / archive / settings, the conversation
view, live streaming with a collapsible Thinking region, and error + retry.

## Scope decisions (user-confirmed — do not reopen)

1. **Web search is the Google Custom Search JSON API over `httpx`, not an MCP client.** The brief
   says "google-search MCP"; this project's product wording calls tools "MCPs" generically, and
   `assistant-config.md` defines tools as plain backend functions in `TOOL_REGISTRY`. **No MCP
   dependency, no sidecar process.**
2. **The main chat's model is chosen by the author, per chat.** This resolves FEAT-013's open
   `_TBD:` on main-chat model selection (`domain-chat.md`, `assistant-config.md` → "Model
   resolution"). Recorded for the architect in `outcome.md`.
3. **SSE token streaming ships now**, rather than a plain POST returning the completed reply.
4. **Sampling params are a llama.cpp-only concern.** The whole set is stored; **only `temperature`
   is surfaced in the UI**; the rest are reviewed later.
5. **Storage is one `sampling_params` TEXT column holding JSON**, gated by a typed Pydantic
   `ChatSamplingParams` — not nine columns. Reason: the user has stated the param set will be
   revised, and a JSON column makes a revision a Pydantic edit with **zero schema migration**, where
   nine columns would route every revision through FEAT-005's drift-and-sync tooling.
   `LlmServer.enabled_models` (JSON `list[str]` in TEXT) is the precedent. It is **not** a free
   dictionary — the Pydantic model gates every read and every write.
6. **Recommended sampling defaults** (unless the user later says otherwise):

   | Param | Default | Param | Default |
   |---|---|---|---|
   | `temperature` | `0.8` | `min_p` | `0.05` |
   | `top_p` | `0.95` | `max_tokens` | unset |
   | `top_k` | `40` | `seed` | unset |
   | `repeat_penalty` | `1.1` | `presence_penalty` | `0.0` |
   | `enable_thinking` | carried (allowlisted for llama-swap) | `frequency_penalty` | `0.0` |

7. **Thinking is obtained from server-side inline tags.** The deployment assumption is that
   llama.cpp runs with reasoning inlined into `content` (`--reasoning-format none`) so `<think>` /
   `</think>` flow through the tools path as ordinary content and this feature splits them itself.
   See "Deployment requirement" below.
8. **Thinking is persisted** on `ChatMessage.reasoning` and renders **collapsed by default** when a
   chat is reopened.
9. **Mode-tool gating stays deferred to `013.codex`.** No mode-bearing subject exists in this
   feature, so the runtime always runs with a **null mode**, and a null mode means the **whole**
   `TOOL_REGISTRY` is allowed (today: just `web_search`). This is the seam `013` replaces with real
   `mode_tool` gating.
10. **Context assembly is OUT** (US-057, UC-078, UC-084/085/086). No chapter or codex content exists
    to assemble; only the named system prompts are composed. Sub-agent delegation, mode
    determination and sub-agent model resolution are also out — deferred to `013.codex` per the
    brief.

### Deliberately deferred (say so, don't build it)

| Deferred | Owner | Why |
|---|---|---|
| Context / content assembly (US-057, UC-078, UC-084/085/086) | `013.codex` and later | No chapter or codex content exists to assemble |
| Shared-canvas writes into chapters/codex (UC-055, US-059, US-103) | `013.codex` / chapter features | No editable subject and no write protocol yet |
| Scoped consistency checks (UC-088, US-102) | `016.chapter-close-continuity` | Needs the material the check runs over |
| Mode determination, `mode_tool` gating, sub-agent delegation, sub-agent model resolution | `013.codex` | First feature with a mode-bearing subject |
| Sampling params other than `temperature` in the UI | later review | User decision 4 — stored and round-tripped, not surfaced |
| Token budgeting / truncation | the deferred assistant session | Undesigned anywhere |

## Deployment requirement (record it, don't code around it)

**Thinking is only visible if the llama.cpp server inlines reasoning into `content`** — i.e. runs
with `--reasoning-format none`. The reason is in the dependency: `llm-client` v0.1.4's
tool-calling stream path never reads a separate `reasoning_content` field, so reasoning delivered
out-of-band is discarded inside the library and reaches neither `on_delta`, the return value, nor
the trace. The verified library detail is in `003.context.md`; the consequence for operators is
recorded here and in `outcome.md`. A server that does **not** inline tags simply produces no
`thinking` frames — the feature degrades to content-only, it does not break.

## Hard dependency — `010.working-page`

Steps **001–003 (backend) can run immediately**; they touch nothing under `frontend/`.

Steps **004–005 (frontend) are blocked** until `010.working-page` has shipped its **step 002**
(`WorkspaceShell`, `WorkNavigator`, `ChatPaneSlot.tsx`, the route table) and its **step 004**
(`src/work/restoreBuffer.ts`, the module tier the active-chat pointer joins, and the `/chats`
route). The gate is the step table in `docs/plans/010.working-page/status.md` reading `done` for
both rows — not any snapshot of the working tree.

> **Snapshot discrepancy, recorded not resolved.** The harvest handed to this plan reports
> `src/work/` as 010 step 001's throwing skeleton with steps 002–004 unbuilt; the on-disk
> `docs/plans/010.working-page/status.md` now marks steps 001 and 002 `done`/PASS (2026-07-25) and
> lists `ChatPaneSlot.tsx` / `WorkspaceShell.tsx` under Files Changed. The harvest is simply older
> than the status file. Nothing in this plan depends on which is current — the dependency is stated
> against the status table, and 004/005 bind to the shipped shape of 010's files, which the skeleton
> agent reads directly.

## Architecture sources

- `docs/architecture/assistant-config.md` — the primary design source for steps 002/003: `ToolDef` +
  module-level `TOOL_REGISTRY`, the `base → mode → book → chapter` composition and its ordering
  argument, tool gating, the `chat_with_tools`-now seam, model resolution.
- `docs/architecture/domain-chat.md` — the `Chat` / `ChatMessage` entities, the "no subject FK"
  absence, and the privacy rule as an ownership rule on `author_id`.
- `docs/architecture/authorization.md` — `BookAccess`, the dependency/service split, and the
  `401 / 404 / 403` taxonomy including the existence-hiding rule this feature reuses for chats.
- `docs/architecture/backend.md` — layer separation, typing discipline, namespace imports, the
  LLM-client rule, the test harness.
- `docs/architecture/frontend-workspace.md` — the chat pane's slot, "the chat id is not in the URL",
  the active-chat pointer beside the restore buffer, `streamPost()` over `EventSource`.
- `docs/architecture/frontend.md` — the enforced MobX / Mantine / `api/` rules steps 004–005 obey.

## Cross-cutting backend constraints (steps 001–003)

- **Four-layer separation is enforced.** `routes/` is HTTP only; `services/` holds logic and may
  never touch a session, `select()` or `session.add()`; `db/` is session-free, one module per
  entity; `models/` is tables + `models/schemas/` DTOs with no logic. Namespace imports throughout
  (`from app.db import chats` → `await chats.get_by_id(...)`).
- **Route shape.** A router owns its own `/api/...` prefix and is mounted bare in `main.py`
  (`app.include_router(chats.router)`). Endpoints take `access: authz.BookAccess =
  Depends(authz.book_access)`, payload param first when there is a body, and map
  `authz.BookAuthorizationError` → 403 plus their service's typed error → a status map.
  **Static path segments must be declared before `/{param}` routes** — load-bearing, documented in
  `routes/books.py`.
- **Every chat route is nested under `/api/books/{book_id}/…`**, so `Depends(authz.book_access)`
  resolves membership for free and the 404-for-a-book-you-cannot-see rule is inherited unchanged.
- **The chat privacy rule** (US-061.AC-1): book membership **and** `Chat.author_id == current user`.
  No owner, no co-author, no admin reaches another author's chat. It is enforced as a **service-level
  ownership check in `services/chats.py` on top of `book_access`**, *not* as a new `Capability`:
  `_CAPABILITY_MATRIX` maps capability → set of roles and has no notion of "author of this row", so
  a row-ownership rule cannot be expressed in it. `authorization.md` already states the rule as
  "an ownership rule on `Chat.author_id`, not a permission row". A chat belonging to another author
  answers **404, not 403** — a 403 would confirm the chat exists, which is exactly what US-061.AC-1
  forbids.
- **DTO conventions.** `CreateXRequest` / `XResponse` / `XListResponse { items: [...] }` in
  `models/schemas/`; **every id is `str` in DTOs** (snowflakes exceed JS safe-integer range); DTOs
  are hand-built by a service mapper, never dumped from the ORM; new rows need no explicit id
  (`Field(default_factory=generate_id, primary_key=True)` via `app/ids.py`).
- **Import/export is not optional.** Any column added to a table is added to its `to_dict` /
  `from_dict` pair in the **same change** (root `CLAUDE.md`). No table is added by this feature, so
  `TABLE_REGISTRY` **order is unchanged**.
- **`ChatMessage.role` is a free string, deliberately** — this feature writes `"user"` and
  `"assistant"` and adds no enum.

## The `llm` client v0.1.4 — verified constraints every backend step obeys

Pinned `git+https://github.com/Iezious/PythonLLMClient.git@v0.1.4`, imported as `llm`.

- **`chat_with_tools(...)` is a client *method*** (not a module function):
  `messages` plus keyword-only `tools_definitions`, `tools`, `system`, `max_loops`, `options`,
  `stream`, `on_delta`, `response_format`; returns the **final assistant string only**.
- **Pre-flight:** every name in `tools_definitions` must have a key in `tools`, or it raises
  `ValueError`. The two maps are built together, always.
- **Tool callables** may be sync or async. Arguments are JSON-decoded and applied as `func(**kwargs)`
  and validated against `inspect.signature(func).parameters`, so **a tool callable must accept
  exactly the JSON-schema field names as keyword parameters**. There is no per-request context
  argument: anything a tool needs (book id, user, session) must be bound by a closure or
  `functools.partial` default.
- **A tool that raises aborts the whole loop** (wrapped as `RuntimeError`); the error is *not* fed
  back to the model. Exhausting `max_loops` also raises `RuntimeError`.
- **`pydantic_to_openai_tool(name, description, schema)`** is a sync module function returning
  `{"type":"function","function":{...,"parameters": schema.model_json_schema()}}`.
- **Options are filtered against a hardcoded allowlist** (`_merge_options_base`); unknown keys are
  **silently dropped**. For both `llama-swap` and `openai` the allowlist is exactly `temperature`,
  `top_p`, `max_tokens`, `presence_penalty`, `frequency_penalty`, `seed`, `enable_thinking`,
  `reasoning_effort`. **`top_k`, `repeat_penalty`, `min_p` and `stop` reach neither backend.** They
  are stored per decision 5/6 and become live the moment the dependency is patched — **no schema and
  no API change is needed when that happens**. Recorded in `outcome.md`.
- The allowlist **always injects** `temperature=1.0`, `top_p=1.0`, `presence_penalty=0.0`,
  `frequency_penalty=0.0` even when the caller passes nothing, so "unset = server default" is
  impossible. `None` values are stripped (passing `None` removes a key, it does not send null).
  There is **no `extra_body` / `**kwargs` escape hatch**; `default_options` runs the same filter.
- **`get_llm_client()` is bypassed on purpose** — it wants `server_type="llamaswap"` (no hyphen),
  which does not match the stored `"llama-swap"`, and its `"openai"` branch drops `bearer_token`.
  The repo constructs `OpenAIAPIClient` / `LlamaSwapAPIClient` directly; keep doing that.
- `LLMClient` has `__aenter__` / `__aexit__` closing its internal `aiohttp.ClientSession` and **no
  standalone `close()`**. Connection failures are **not** wrapped in `LLMError` — raw
  `aiohttp.ClientError` subclasses propagate.
- **Ollama is not supported by this repo** (`llama-swap` and `openai` only); write no code that
  pretends otherwise.

## The SSE frame vocabulary (step 003 emits it, step 005 consumes it)

Four frame names, and they are chosen to match what `frontend/src/api/sse.ts:streamPost()` already
special-cases:

| Frame | Payload | Meaning |
|---|---|---|
| `thinking` | a text chunk | reasoning text, routed by the think splitter |
| `delta` | a text chunk | assistant content text |
| `done` | the persisted assistant message DTO | the turn completed and was stored |
| `error` | a message | the turn failed; the user message stays stored, retry is offered |

`streamPost` handles `error` (→ `onError`) and `done` (→ `onDone`) itself; everything else is
routed to `onEvent`. This is the **first concrete piece of the deferred FEAT-013 event protocol**
and is deliberately narrow — the shared-canvas write protocol is still undesigned (`outcome.md`).

## Cross-cutting frontend constraints (steps 004–005)

- **`observer` on every component**, no exceptions. State is observable data + pure `get` computeds;
  every effectful operation is an external `(state, args, signal)` function using `runInAction`;
  every loadable is an async trio (`x` / `xStatus: "idle"|"loading"|"ready"|"error"` / `xError`).
- **No custom `useX` hooks**, no `useCallback` / `useMemo` / `useReducer`. `useState` only to own a
  stable state instance; `useEffect` only at the page/shell mount with empty deps.
- **No React context**, no Mantine `useForm`, no `@mantine/hooks`. Slices are passed explicitly down
  the tree as props (`frontend.md` → Components).
- **All HTTP lives in `src/api/`**; `signal?: AbortSignal` is always the trailing argument; list
  envelopes are unwrapped in the api module, not modelled in the type. DTOs are hand-written
  `.d.ts` in `src/types/`, wire-exact `snake_case`, **ids typed `string`**, no `any`, no runtime
  validation.
- **The chat id is never in the URL.** The pane resolves its active chat from a device-local
  per-book pointer, falling back to the most recent chat by timestamp
  (`frontend-workspace.md` → "The active-chat pointer lives in the same module tier").
- **The Chats navigator entry does not render into the content pane** — a picked chat opens in the
  chat pane (US-105.AC-3). The list itself lives in the chat pane too, per US-095.AC-1 / UC-081
  step 1 ("the chat pane's list"). `frontend-workspace.md`'s route-map row for
  `/work/:bookId/chats` reads as though the list renders in the content pane; that tension is
  resolved in product's favour here and recorded in `outcome.md`.

## Testing facts shared by every step

**Backend (001–003)** — `backend/tests/{db,services,routes,routes/admin}/` plus flat
`test_data_domain_*.py`; `asyncio_mode="auto"` so async tests need no decorator. `conftest.py`
provides `_reset_db_ready` (autouse), `db` (temp SQLite) and `http_client` (sets
`BOOKWRITER_DB_PATH`, clears `get_settings.cache_clear()`, ASGITransport, runs the lifespan).
**Auth in route tests is real**: seed a user row and mint a real JWT via
`auth.create_access_token(user)`, header `Authorization: Bearer <t>`. Assertions validate the
response through the DTO (`SomeResponse.model_validate(body)`), and cases are named
`test_..._DoD1_US061_AC1`. **No network in any test** — the HTTP boundary and the LLM client are
mocked.

**Frontend (004–005)** — `frontend/vitest.config.ts` is jsdom with **`globals: false`**, so every
spec imports `describe/it/expect/vi` from `"vitest"`; `restoreMocks` / `clearMocks` true.
`frontend/tests/setup.ts` adds jest-dom, stubs `matchMedia` / `ResizeObserver` / `scrollIntoView`,
and in `afterEach` runs `cleanup()` + `localStorage.clear()`.
`frontend/tests/support/render.tsx` exports `renderWithProviders(ui, { route? })` wrapping in
`<MantineProvider theme={theme} env="test">` (the `env="test"` disables portals and transitions and
is load-bearing) and, with `route`, in `<MemoryRouter>`; routes passed in are **basename-stripped**.
Specs **mock the `api/` module, never `fetch`**, module-factory form enumerating every export the
subject imports, then `vi.mocked(...).mockResolvedValue(...)`. There is **no `ReadableStream`
fixture, no fake-timer setup and no streaming precedent** in the repo — step 005 introduces the
first (see `005.context.md`).

## Build and test gates (root `CLAUDE.md`)

- **Backend steps 001–003:** `cd backend && .venv/Scripts/python -m pytest`. There is **no separate
  backend typecheck** — do not invent one.
- **Frontend steps 004–005:** `cd frontend && npm run build` (= `tsc && vite build`),
  `cd frontend && npm test`, `cd frontend && npm run test:types`.
  `frontend/tsconfig.json` has `include: ["src"]`, so a broken spec can never break the bundle;
  `npm run test:types` is the only program covering `tests/`.

## Step sizing — a user decision

Every step here is at or slightly above the 50–200-line band (roughly 340 / 250 / 280 / 280 / 280
lines of source change). **This is the user's explicit call**, made to avoid spending pipeline runs
on steps too small to justify them — the same kind of sizing decision `010.working-page` recorded
for its own step 004. **Do not re-split any step.** Each one is a single coherent contract:
schema + CRUD + privacy (001), the two pure halves of the assistant scaffold (002), the streaming
turn and the splitter it exists for (003), the pane's management surface (004), the conversation and
its stream (005).

## Steps

| Step | File | Layer |
|---|---|---|
| 001 | `001.chat-crud-model-sampling.md` | backend |
| 002 | `002.tool-registry-web-search-prompts.md` | backend |
| 003 | `003.streaming-turn-endpoint.md` | backend |
| 004 | `004.chat-pane-list-and-settings.md` | frontend (blocked on 010) |
| 005 | `005.conversation-view-streaming.md` | frontend (blocked on 010) |

## Product ids

Delivered here: **UC-053 / US-056** (start a chat, private, subject-independent), **UC-081 /
US-095** (list, pick, continue), **UC-082 / US-096** (archive and restore), **US-061.AC-1** (privacy
from every other role), **UC-054 / US-058** (iterate with the LLM), **UC-056 / US-060** (error,
retry, conversation preserved), **UC-087 / US-101** (web search), **US-105.AC-3** (a picked chat
opens in the chat pane). Partially: **US-061.AC-2** (only saved output is shared — vacuously true,
there is no save path yet). Deferred with an owner named above: US-057, US-059, US-089, US-098,
US-099, US-100, US-102, US-103.
