# 011.chat-panel — outcome

Intended documentation changes once this feature ships, grouped by target file, for the architect to
apply at finalization. The planner writes this section; the coder appends `## Observations` below.

## `docs/architecture/domain-chat.md`

1. **Section:** Chat (the field table).
   **Change:** record the three added columns — `llm_server_id` (nullable FK → `LlmServer.id`),
   `model_name` (nullable), the pair moving together exactly as `SubAgent`'s does, and
   `sampling_params` (non-nullable TEXT holding a JSON object gated by a Pydantic
   `ChatSamplingParams`). Add `reasoning` (nullable) to the `ChatMessage` table.
   **Reason:** the entity map is drawn whole; these are the first columns the assistant runtime added
   to it and they must not be re-derived later.

2. **Section:** "Assistant subsystem — one slice now designed, the rest deferred" → *Still deferred*.
   **Change:** **the main-chat model selection `_TBD:` is RESOLVED — the model is chosen by the
   author, per chat**, stored as the `(llm_server_id, model_name)` pair above and picked from the
   active servers' `enabled_models`. Move it out of the deferred list and record it as decision
   history. The same `_TBD:` is referenced in `assistant-config.md` → "Model resolution" and "Out of
   scope" and in `docs/product/` FEAT-013; all three should stop calling it open.
   **Reason:** the brief named it as an open product `_TBD:` for the planner to resolve; it is now
   resolved by a user decision, not by inference.

3. **Section:** "Privacy is an ownership rule on `author_id`, not a permission row".
   **Change:** name the enforcement point — a service-level ownership check in `services/chats.py`
   layered on top of the `book_access` dependency — and record that a chat belonging to another
   author answers **404, not 403**, so existence is never confirmed. State explicitly that no
   `Capability` was added and `_CAPABILITY_MATRIX` is unchanged, because the matrix maps
   capability → role and has no notion of "author of this row".
   **Reason:** the rule was stated as a principle with no enforcement point; the 404-vs-403 choice is
   a decision later chat-touching features must copy.

4. **Section:** the deferred-boundary paragraph.
   **Change:** record that **context assembly is still deferred** and that this feature composes only
   the named system prompts — it ships the chat surface and one turn, not US-057 / UC-078 /
   UC-084/085/086.
   **Reason:** shipping a working chat pane invites the reading that the context model shipped with
   it.

## `docs/architecture/assistant-config.md`

5. **Section:** Tool registry — code-defined, not a table.
   **Change:** `TOOL_REGISTRY` now exists in code at `backend/app/services/tools.py` as a
   module-level literal list of frozen `ToolDef` dataclasses, with `web_search` as its **first and
   only** entry, plus the definition/callable-map builder over `pydantic_to_openai_tool`. Record the
   frozen-dataclass choice (over a 4-tuple) and that the catalogue is still never exported.
   **Reason:** the design named the shape; the realization pins the module and the record type.

6. **Section:** Tool gating.
   **Change:** record the interim rule this feature runs under — **a null mode allows the whole
   `TOOL_REGISTRY`** — because no mode-bearing subject exists yet, and name `013.codex` as the
   feature that replaces the null-mode branch with real `mode_tool` gating. The skip-and-log rule for
   an unknown selected name is implemented as designed.
   **Reason:** a deliberate temporary widening of an allowlist must be documented as a seam, not
   discovered later as a hole.

7. **Section:** System-prompt composition — the named prompts only.
   **Change:** record that composition is realized as a **pure function** in
   `backend/app/services/prompt_composition.py` taking four optional layers, with the base layer as a
   module constant; and that at this feature only **base and book** are ever non-empty (mode is
   always null, and `Chapter.system_prompt` has no chapter subject to come from yet).
   **Reason:** the composer's four positions exist but only two are exercised; the doc should say
   which, so later features know they are filling designed slots.

8. **Section:** The tool / function-call protocol — built on `chat_with_tools`.
   **Change:** confirm the seam is realized as designed — `chat_with_tools` is called from one place
   (`services/chat_turn.py`), and the config model, registry, gating and composition are all
   independent of it, so swapping in a manual `chat`-in-a-loop driver when the shared-canvas SSE
   protocol arrives is an interior change. Record `max_loops`'s concrete bound.
   **Reason:** the brief's second open question asks explicitly for this seam to be recorded once it
   is real.

9. **Section:** Model resolution (and a new note beside it).
   **Change:** record two verified `llm-client` v0.1.4 constraints that shape every future sampling
   decision:
   (a) **options are filtered against a hardcoded allowlist** — `temperature`, `top_p`, `max_tokens`,
   `presence_penalty`, `frequency_penalty`, `seed`, `enable_thinking`, `reasoning_effort` — so
   **`top_k`, `repeat_penalty` and `min_p` are persisted by this feature but cannot reach either
   backend**; they go live with no schema or API change if the dependency is patched;
   (b) the allowlist **always injects** `temperature=1.0` / `top_p=1.0` / `presence_penalty=0.0` /
   `frequency_penalty=0.0`, so "unset means server default" is not expressible, and there is no
   `extra_body` escape hatch.
   Also record that **sampling emission is backend-conditional**: params are sent only to a
   `llama-swap` server; an `openai` server gets none.
   **Reason:** these are dependency facts that silently change behaviour and would otherwise be
   re-discovered by whoever next touches sampling.

10. **Section:** Model resolution → "Reuse the existing construction path".
    **Change:** record that `services/llm_servers.py` grew a **model-bound** construction path beside
    `_create_client` (which hardcodes `model=""` for `list_models()` and is a documented test seam),
    that clients are entered as async context managers because `LLMClient` has `__aenter__` /
    `__aexit__` and **no standalone `close()`** — and that the **pre-existing `list_models` path still
    leaks its `aiohttp.ClientSession`**, deliberately out of scope here and worth its own fix.
    **Reason:** a known resource leak in shipped code should be recorded once, not rediscovered.

## `docs/architecture/backend.md` (index) and `backend/features.md`

11. **Section:** LLM client (backend.md) — plus an as-shipped record in `backend/features.md`.
    **Change:** record the **deployment requirement**: thinking is visible only when the llama.cpp
    server inlines reasoning into `content` (`--reasoning-format none`), because
    `chat_with_tools(stream=True)` routes through `_stream_openai_tools_response`, which reads only
    `delta["tool_calls"]` and `delta["content"]` and **never** `reasoning_content` — reasoning sent
    out-of-band is discarded inside the library and reaches neither `on_delta`, the return value, nor
    the trace. The reasoning-aware parser exists but is reachable only from plain `chat()`, which has
    no tool loop. Record the consequence: BookWriter splits `<think>` / `</think>` itself in
    `services/chat_turn.py`, and a server without the flag degrades to content-only.
    **Reason:** an operational requirement that is invisible in code and produces a silent feature
    loss when unmet.

12. **Section:** decision history (backend.md).
    **Change:** add an entry for this feature: the first slice of the FEAT-013 assistant runtime —
    per-chat model + sampling, `TOOL_REGISTRY` with web search, prompt composition, and the first SSE
    endpoint in the repo — with the `chat_with_tools`-now seam and the null-mode tool widening named
    as the two deliberate temporary shapes.
    **Reason:** the decision-history section is where reversible shortcuts are supposed to be visible.

## `docs/architecture/backend/persistence.md`

13. **Section:** DB import/export (codecs, `TABLE_REGISTRY`).
    **Change:** record that the `chats` and `chat_messages` codecs carry the new columns
    (`llm_server_id` string-or-null, `model_name`, `sampling_params`, `reasoning`) and that
    **`TABLE_REGISTRY` order is unchanged** — no table was added.
    **Reason:** the same-change codec rule was honoured and the registry's stability should be
    explicit.

14. **Section:** DB import/export, or the storage conventions nearby.
    **Change:** record **JSON-in-TEXT gated by a Pydantic model** as a sanctioned pattern with its
    reasoning: `Chat.sampling_params` follows `LlmServer.enabled_models`, and it was chosen over nine
    typed columns because the param set is expected to be revised — a JSON column makes a revision a
    Pydantic edit with zero schema migration, where columns would route every revision through
    FEAT-005's drift-and-sync tooling. It is **not** a free dictionary: the Pydantic model gates every
    read and write.
    **Reason:** the no-free-dictionaries rule makes this look like a violation unless the gate and the
    reasoning are recorded.

15. **Section:** Config / secrets.
    **Change:** record the two new settings — the Google Custom Search **api-key reference** and
    **search-engine id** — following the `Field(default=..., validation_alias="BOOKWRITER_...")`
    convention and holding **`$ENV_VAR` pointers** resolved through `services/secrets.py`. Record
    also that web search is a **direct `httpx` call to the Google Custom Search JSON API, not an MCP
    client**: the product's "MCP" wording is generic, and `assistant-config.md` defines tools as plain
    backend functions.
    **Reason:** the brief said "google-search MCP"; the shipped shape must not be read as a missing
    MCP integration.

## `docs/architecture/authorization.md`

16. **Section:** Chats.
    **Change:** point the paragraph at the enforcement point (`services/chats.py`'s ownership check
    over the `book_access` dependency) and record the **404-not-403** answer for another author's
    chat, tying it to the existing existence-hiding rule under "Failure modes". Note that FEAT-020's
    admin-only config is consumed inside an author's own chat exactly as the doc already predicts.
    **Reason:** the doc states the rule but names no enforcement point and no status code.

## `docs/architecture/frontend-workspace.md`

17. **Section:** The working page / the chat-pane slot.
    **Change:** the slot is no longer empty — record the pane's parts (`src/work/components/chat/`:
    the pane, the list, the settings panel, the message list, the thinking block, the composer, and
    `chatPaneState.ts`) and that 010's `ChatPaneSlot` placeholder is gone.
    **Reason:** the doc's "stays empty until Stage 5" is now historical.

18. **Section:** Route map (working page) — the `/work/:bookId/chats` row.
    **Change:** resolve the tension in the doc's own text. The row reads as though the chat **list**
    renders in the content pane, while the navigator section says Chats "does not render into the
    content pane"; product settles it (US-095.AC-1 and UC-081 step 1 both say "the chat pane's
    list"). As shipped: the list lives in the **chat pane**, the **Chats navigator entry is a control
    over pane state rather than a router link** (using the `paneTarget: "chat"` discriminator 010
    already froze), and `/work/:bookId/chats` survives only as a **redirect** so the documented deep
    link neither 404s nor renders a chat surface in the content pane.
    **Reason:** two sentences of the same document disagree; the resolution and its product basis
    should be recorded rather than left to the next reader.

19. **Section:** "The active-chat pointer lives in the same module tier".
    **Change:** name the module — `src/work/activeChat.ts`, plain functions beside
    `restoreBuffer.ts`, `localStorage`, one id per book, never in the URL and never on the server,
    falling back to most-recent-by-timestamp — and record that it is realized as designed.
    **Reason:** the sanction is easier to keep attached to a named file than to a concept.

20. **Section:** Conventions this page does not break → the `streamPost()` line.
    **Change:** record the repo's **first `streamPost()` call site** and two seams it exposed:
    (a) `streamPost` bypasses `client.ts`'s 401 silent refresh, so `client.ts` now exports a reusable
    refresh entry point that the turn stream awaits before opening; (b) `streamPost` **owns and
    returns its own `AbortController` and takes no `signal`**, which does not match the
    `(state, args, signal)` effect convention — the send/retry functions therefore take no `signal`,
    store the controller on the state and expose an explicit stop called from the shell's unmount
    cleanup. Also record the first repo-wide use of `react-markdown`.
    **Reason:** both are deliberate, documented deviations from enforced conventions, and the next
    streaming surface will face them again.

21. **New section (or beside the chat pane):** the SSE frame vocabulary.
    **Change:** record `thinking` / `delta` / `done` / `error` as the **first concrete piece of the
    deferred FEAT-013 event protocol**, chosen to match what `api/sse.ts` already special-cases, and
    state plainly that it is **deliberately narrow** — the shared-canvas write protocol (UC-055,
    UC-076, UC-077) is still undesigned, and these four frames are not it.
    **Reason:** a shipped frame set tends to be read as the protocol; it is a floor, not the design.

## `docs/architecture/domain-book.md`

22. **Section:** Book (the field table).
    **Change:** reinforce the wire gap `010.working-page` already raised — `system_prompt` and
    `active_notes` exist on the table but appear in **neither** the backend books schema nor
    `frontend/src/types/books.d.ts`. This feature reads `Book.system_prompt` **server-side** for
    prompt composition, so it needed no DTO change, but the gap is now load-bearing for the
    assistant: whichever feature first lets an author *edit* the book prompt must widen the response
    schema and the `.d.ts` together.
    **Reason:** the first real consumer of the field exists now, which raises the cost of leaving the
    gap unrecorded.

## Observations

- Step 003: `create_model_client` was added beside `_create_client` sharing the extracted `_construct_client` `backend_type` branch, and `run_turn` enters it as an `async with` so the session closes on every path. The pre-existing `_create_client`/`list_models` session leak (outcome item 10) is left untouched — confirmed out of scope. Possible impact: track item-10's `list_models` leak fix as its own backlog task.
- Step 004: this feature establishes the repo's first **shell-owns-one-state-instance-shared-with-a-child** pattern — `WorkspaceShell` owns the single `ChatPaneState` (via `useState`), starts its load in the existing mount `useEffect`, passes the instance to `ChatPane` (through `ChatPaneSlot`) and a zero-arg `onShowChatList` handler to `WorkNavigator`. No React context; the slice is passed explicitly down the tree exactly as `frontend.md` → Components prescribes. `ChatPane` holds only an ephemeral `useState` boolean for the new-chat form (the `BookshelfPage` `createOpen` precedent) and runs no effect. Possible impact: record in `frontend.md` → Components as the worked example of the "pass stores/slices explicitly, one owner" rule.
- Step 004: the active-chats list and the archived (restore) view are backed by one loaded `chats` array filtered client-side by `showArchived` — `loadChatPane` fetches only the non-archived list, and archive/restore flips the row's `archived` flag in place, keeping it available for the restore view within the session. There is no separate archived-list fetch and no re-fetch on toggling the archived view (no effect fn was frozen for it). Possible impact: if freshly loading a book must show pre-existing archived chats before any in-session archive, a second `listChats(bookId, true)` load (or a re-fetch on toggle) would be the follow-up.
- Step 005: this is the repo's **first `streamPost` call site and first `react-markdown` use**. `api/chats.streamChatTurn` awaits the new `client.refreshAuthToken` entry point before opening the stream (because `sse.ts:streamPost` uses raw `fetch` + `authHeaders()` and bypasses `request<T>`'s on-401 silent refresh), and it stores the `AbortController` that `streamPost` owns rather than passing a `signal` in — the one sanctioned break of the trailing-`signal` convention. `react-markdown` renders assistant content only, no plugins configured (none needed). Possible impact: record the refresh-before-stream + controller-ownership seam in `frontend.md` → SSE/streaming as the worked example, and note `react-markdown`'s default no-plugin config as the baseline for future markdown surfaces.
- Step 005: the `done` frame's persisted assistant-message DTO is unreachable through `streamPost` (it calls `onDone()` with no argument), so `sendChatTurn`/retry obtain the stored message by **reloading the chat once via `getChat`** on `done` and atomically swapping `messages` — the in-flight bubble (a `__streaming__`-keyed `RenderedMessage`) then disappears with no duplicate/orphan. Possible impact: if a future streaming surface needs the terminal payload without a reload, `sse.ts:streamPost`'s `onDone` signature would need to forward the parsed `done` data (a frozen-signature change routed through skeleton).
