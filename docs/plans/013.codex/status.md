# Feature 013 — codex

| Step | File                                | Status  | Verifier | Date |
|------|-------------------------------------|---------|----------|------|
| 001  | `001.codex-db-authz.md`             | done    | PASS     | 2026-07-27 |
| 002  | `002.codex-schemas-service.md`      | done    | PASS     | 2026-07-27 |
| 003  | `003.codex-routes.md`               | done    | PASS     | 2026-07-27 |
| 004  | `004.embedding-service.md`          | done    | PASS     | 2026-07-27 |
| 005  | `005.vector-sidecar.md`             | done    | PASS     | 2026-07-27 |
| 006  | `006.incremental-index.md`          | done    | PASS     | 2026-07-27 |
| 007  | `007.mode-runtime-gating.md`        | done    | PASS     | 2026-07-27 |
| 008  | `008.subagent-delegation.md`        | done    | PASS     | 2026-07-27 |
| 009  | `009.codex-assistant-tools.md`      | done    | PASS     | 2026-07-27 |
| 010  | `010.shared-canvas-write.md`        | done    | PASS     | 2026-07-27 |
| 011  | `011.codex-api-list-pages.md`       | done    | PASS     | 2026-07-27 |
| 012  | `012.codex-entry-page.md`           | done    | PASS     | 2026-07-27 |
| 013  | `013.subject-chat-canvas-wiring.md` | done    | PASS     | 2026-07-27 |

## Files Changed

### Step 001 — Codex db layer + authz capabilities
- `backend/app/db/codex_entries.py` — `list_by_book` kind / archived / case-insensitive
  name-or-body needle filtering with explicit name-ascending (nulls last) then-id ordering;
  `update` persists an already-mutated row and returns the stored one.
- `backend/app/db/codex_entry_versions.py` — `next_generation` (`1`, else `max(generation) + 1`)
  and ascending-`generation` ordering for `list_by_entry`.
- `backend/app/services/authz.py` — no change needed: the skeleton already froze
  `browse_codex` / `edit_codex_entry` and their `{owner, co_author}` matrix rows, verified
  against the step file's cells.

### Step 002 — Codex schemas + service
- `backend/app/models/schemas/codex.py` — verified against the step file's DTO intent
  (create / update / entry-response / list envelope, every id `str`, `kind` absent from the
  update request); landed complete at the skeleton, no change needed.
- `backend/app/services/codex.py` — the four entry points plus the response mapper and the
  private rules: `_resolve_name` (kind/name, whitespace-only counts as absent),
  `_require_writable_mode` (co-author × proposal → `proposal_mode_unsupported`, message names
  FEAT-010), `_comparable` (staleness normalization) and `_resolve_entry` (another book's entry,
  an unknown id and a non-numeric id all → `entry_not_found`). `update_entry` writes the
  `CodexEntryVersion` carrying the PRIOR name/body/kind — generation from
  `codex_entry_versions.next_generation`, author = the acting user — **before** mutating the
  entry; create writes no version row.

### Step 003 — Codex routes
- `backend/app/routes/codex.py` — the four handler bodies filled: each parses, calls the one
  matching `services/codex.py` entry point and returns, wrapped in a single
  `try/except authz.BookAuthorizationError → 403 / except CodexError → _map_codex_error`
  (the `routes/admin/db.py` shape). The list route forwards its wire `q` to the service's
  `needle`, `kind=None` meaning every kind and `include_archived` defaulting to false; the two
  write handlers pass `caller` through as the acting user. No capability check and no DB access
  in the route layer. The module docstring's stale "handler bodies are UNIMPLEMENTED" clause was
  trimmed; the frozen supporting shapes (`CodexErrorDetail`, `_CODEX_ERROR_STATUS`,
  `_map_codex_error`, `_map_authz_error`) landed complete at the skeleton and are unchanged.
- `backend/app/main.py` — verified only: the skeleton had already added `from app.routes import
  codex` and `app.include_router(codex.router)` after `chats`; no edit was needed and the
  `vector.init_vector` startup call (step 005's) was not touched.

### Step 004 — Embedding service
- `backend/app/services/embedding.py` — the five function bodies filled; the frozen taxonomy
  (`EmbeddingErrorReason` / `EmbeddingError`) and every signature are unchanged. `embed_batch`
  short-circuits an empty input to `[]` before any lookup, then resolves the designation
  (`llm_servers_db.get_embedding_server`) and raises `no_provider` — before any client exists —
  when the row is absent or its `embedding_model` is blank; resolves the `$ENV` api key at use
  time via `secrets.resolve_env_ref` and converts `LlmServerError` to `unreachable`; constructs
  the model-bound client through `llm_servers_service.create_model_client` (never `_create_client`)
  inside `async with`, and converts `(aiohttp.ClientError, LLMError, ValueError, RuntimeError)` —
  `chat_turn.py:_TURN_FAILURE_EXCEPTIONS`' breadth — to `unreachable`. `is_available` performs the
  same designation test and contacts nothing; `embed_text` is a thin wrapper over `embed_batch`
  (no duplicated resolution) and `probe_dimension` goes through it with `_PROBE_TEXT`, returning
  the returned vector's length; `check_dimension` is synchronous and raises `dimension_mismatch`
  on the first differing length. Module-level `import aiohttp` / `from llm import LLMError` added
  for the failure set; `app.db.vector` is still not imported, and the stale
  "Skeleton … UNIMPLEMENTED" docstring clauses were trimmed.

### Step 005 — Vector sidecar
- `backend/app/db/vector.py` — every stub body filled; no frozen signature moved. The chunk table is
  created from a `pyarrow` schema (`vector` as `fixed_size_list(float32, dimension)`, `book_id`
  `int64`, `source_kind` / `source_id` / `text` strings, `chunk_index` `int64`) built **only** at a
  probed/supplied dimension — never a constant; `get_table_dimension` reads the live table's
  `vector` field back. `upsert_chunks` stringifies the snowflake once (`key = str(source_id)`, the
  module's single conversion site), deletes `(source_kind, source_id)` then inserts with
  `chunk_index` from zero, and creates the table lazily at `len(chunks[0][1])`; `delete_by_source` /
  `delete_by_book` are the same filtered delete. `search` applies `book_id` (and the optional
  `source_kind IN (…)` narrowing) as a **prefilter** — the predicate runs before the
  nearest-neighbour scan, so another book's chunk cannot occupy a result slot at all — and maps
  LanceDB's `_distance` into `ChunkHit.score`, nearest first. The chunker is pure: name +
  blank line prepended verbatim, body ≤ `SINGLE_CHUNK_THRESHOLD_CHARS` → one chunk, longer bodies
  split into paragraph-boundary windows of `CHUNK_SIZE_CHARS - len(prefix)` whose successors open
  with the previous window's trailing **whole paragraphs**, sized to approximate
  `CHUNK_OVERLAP_CHARS`. `VECTOR_SOURCE_REGISTRY`
  gained its single `codex_entry` entry (`from app.db import codex_entries` at module level).
  `rebuild_index` keeps its `-> int` shape and the frozen connect/drop preamble, then probes,
  recreates the table at the probed dimension (so an empty codex still leaves a usable empty table),
  and walks each registry entry, embedding in `_EMBED_BATCH_SIZE = 32` batches; it raises
  `VectorIndexError` when it must probe or embed with no injected embedder. Private helpers added:
  `_PendingChunk`, `_chunk_schema`, `_chunk_record`, `_sql_string`, `_source_predicate`,
  `_create_chunk_table`, `_open_chunk_table`, `_paragraph_units`, `_split_into_windows`,
  `_collect_chunks`, `_embed_and_insert`.
- `backend/app/db/codex_entries.py` — `list_all_unarchived` filled: every `archived == False` entry
  across all books ordered by `id`. Step 001's four functions untouched.
- `backend/app/db/import_export_queries.py` — `run_vector_rebuild` gained the log-and-swallow guard
  (`except Exception` → `logger.exception`, deliberately broad: a missing embedder, an unreachable
  embedding server and a sidecar failure are all recoverable by a later rebuild and none of them
  makes the imported SQLite data wrong). Signature and position unchanged.
- `backend/app/main.py` — verified only: the skeleton had already added
  `from app.services import embedding as embedding_service` and the
  `init_vector(settings.lancedb_dir, embed_batch=…, probe_dimension=…)` startup call. No edit.

### Step 006 — Incremental index maintenance
- `backend/app/services/codex_index.py` — both public bodies filled; no frozen signature moved.
  `index_entry` runs the archived rule first (an archived entry delegates straight to `drop_entry`,
  so nothing is chunked or embedded), then chunks through `vector.chunk_codex_entry` **outside any
  try** (pure function — a programming error there still fails loudly), embeds every chunk in **one**
  `embedding.embed_batch` call, applies the incremental **vector-count guard** step 005's notes
  deferred here, reads `vector.get_table_dimension()` and — only when a table already exists —
  checks the batch with `embedding.check_dimension`, then replaces the entry's chunks with
  `vector.upsert_chunks(book_id, SourceKind.codex_entry, entry.id, zip(chunks, vectors))`. An entry
  that chunks to nothing clears its chunks rather than leaving stale rows. `drop_entry` is
  `vector.delete_by_source` plus the idempotence rule (removing chunks that are not there is
  `dropped`, not a failure). Two private helpers added: `_failure_reason` (maps a caught
  `EmbeddingError` across **by wire value**, so no lookup table can drift; an unknown future member
  degrades to `unreachable`) and `_failed` (the single place a failure is logged at **warning** with
  the entry id, the book id and the reason value, and becomes `IndexOutcome(failed, reason=…)`; the
  message carries `retrieval.md`'s "the index is derived, so this is recoverable by definition"
  framing and states that the save stands). `embedding.EmbeddingError` is caught by name around the
  embed and the dimension check; `_SIDECAR_FAILURE_EXCEPTIONS` wraps **only** the three
  `db/vector.py` calls — there is no bare `except Exception` anywhere in the module. The module
  docstring's stale "both function bodies are UNIMPLEMENTED" clause was trimmed.
- `backend/app/services/codex.py` — **verified only, no edit**: the skeleton had already placed both
  call sites exactly as the step specifies (`await codex_index.index_entry(entry)` after
  `codex_entries.create(...)` in `create_entry`, and after `codex_entries.update(entry)` — i.e. after
  both the version row and the entry mutation — in `update_entry`, each before `_to_entry_response`,
  each discarding the outcome), together with the `from app.services import codex_index` import and
  the as-built docstring paragraph. Step 002's frozen signatures and behaviour are untouched.

### Step 007 — Mode determination, the mode prompt layer, real tool gating
- `backend/app/services/assistant_runtime.py` — the four bodies filled; no frozen signature moved and
  no db helper added (`db/assistant_modes.get_by_id` / `db/mode_tools.list_by_mode` /
  `db/codex_entries.get_by_id` read directly, `services/assistant_config.py` never imported).
  `resolve_subject` returns `NO_SUBJECT` for an absent `subject_kind` (preserved 011 path) and for a
  codex-entry id that does not resolve **inside `access.book_id`**; every other kind resolves to
  itself with no row and no mode; a codex-entry subject **with** an id loads the row (the row's `kind`
  decides, the request's `codex_kind` is ignored), **without** an id it is UC-076's blank entry and
  the request's `codex_kind` decides. The record is built then completed with
  `dataclasses.replace(..., mode_key=…)`, as the skeleton described. `determine_mode` is pure and keys
  off `subject.entry` alone — no row, no mode — so a chapter subject, the lists, book state, the chats
  view and the absence of a subject all fall through. `mode_system_prompt` returns the stored
  `system_prompt` verbatim, or `None` for an absent key, a missing row and a null/empty/whitespace
  prompt (US-110.AC-4). `allowed_tool_names` returns `tuple(row.tool_name …)` from
  `mode_tools.list_by_mode` — zero rows is an empty tuple, never the registry — and `BASE_TOOL_NAMES`
  with no mode; it filters nothing against `TOOL_REGISTRY`, leaving `resolve_tools`' skip-and-log as
  the single place an unknown name is handled. Three private helpers added: `_CODEX_KIND_MODES`
  (keyed by the enum's **wire value**), `_mode_for_codex_kind` and `_entry_within_book` (the
  non-numeric / unknown / other-book triple, `services/codex.py:_resolve_entry`'s rule minus the
  error). The stale "Skeleton … UNIMPLEMENTED" docstring clauses were trimmed.
- `backend/app/models/schemas/chats.py` — **verified only, no edit**: `SubjectKind` and `TurnRequest`'s
  `subject_kind` / `subject_id` / `codex_kind` landed complete at the skeleton; `TurnRequest()` still
  validates an empty body.
- `backend/app/services/chat_turn.py` — **verified only, no edit**: the skeleton had already made all
  three edits inside `run_turn` (step "1b" reading `context.subject.mode_key` and awaiting
  `mode_system_prompt` / `allowed_tool_names` before the compose, `mode=mode_prompt` on
  `compose_system_prompt`, and `resolve_tools(allowed_names)` in place of the `resolve_tools(None)`
  seam) plus `prepare_turn`'s `resolve_subject` call. `services/tools.py` and
  `services/prompt_composition.py` are untouched, as the step requires.

### Step 008 — Sub-agent delegation as synthetic tools
- `backend/app/services/subagent_delegation.py` — the three public bodies filled; no frozen signature
  moved and no db helper added (`db/mode_subagents.list_by_mode`, `db/sub_agents.get_by_id`,
  `db/subagent_tools.list_by_sub_agent` and `db/llm_servers.get_by_id` read directly;
  `services/assistant_config.py` never imported; `services/tools.py` untouched).
  `delegation_tool_name` lowercases, collapses every run of non-`[a-z0-9]` characters to one `_`,
  strips the edges, prepends `DELEGATION_TOOL_PREFIX` and truncates to 64 characters
  (`"Continuity Checker"` → `"ask_continuity_checker"`). `build_delegation_tools` keeps the two
  preserved early returns, then walks the link rows: a link to a **missing** row and a **disabled**
  sub-agent are skipped and logged; a derived name colliding with a real `TOOL_REGISTRY` name or with
  an **earlier synthetic name in the same build** is skipped and logged (the registry always wins);
  each surviving row becomes `ToolDef(name=…, description=<carries the sub-agent's name verbatim>,
  args_schema=DelegationArgs, callable=functools.partial(run_delegation, sub_agent, parent))`.
  `run_delegation` is a thin never-raise guard over the private `_delegate`: it resolves the
  `subagent_tool` rows against `TOOL_REGISTRY` (`_subagent_tools` — unknown names skipped and logged,
  and **nothing but registry entries can enter**, so the nested loop cannot delegate), builds both
  maps in **one** `build_tool_bindings` call, resolves the model (`_resolve_model` — the sub-agent's
  own `(llm_server_id, model_name)` when both are set, otherwise the parent's server / resolved key /
  model, US-113.AC-6), constructs **one** client per delegation through
  `llm_servers_service.create_model_client` (never `_create_client`) inside `async with`, and calls
  `chat_with_tools` with the sub-agent's `system_prompt` **alone** and `SUBAGENT_MAX_LOOPS`. Every
  failure path — a missing / inactive assigned server, an unresolvable `$ENV` credential, a transport
  or LLM error, a raising nested tool, an exhausted nested loop — returns a short error string naming
  no internals and no key. Private helpers added: `_NON_ALNUM_RUN`, `_MAX_TOOL_NAME_CHARS`, the two
  message templates, `_delegate`, `_subagent_tools`, `_resolve_model`; the module docstring's stale
  "UNIMPLEMENTED" clause was trimmed. One import line widened
  (`from app.services.tools import TOOL_REGISTRY, ToolDef, build_tool_bindings`, plus `functools` /
  `re`).
- `backend/app/services/assistant_runtime.py` — **verified only, no edit**: the skeleton had already
  landed `resolve_turn_tools` complete (`resolve_tools(await allowed_tool_names(mode_key))` then
  `build_delegation_tools(mode_key, parent)`, returned as one list, real tools first). Step 007's
  seven symbols are untouched.
- `backend/app/services/chat_turn.py` — **verified only, no edit**: the skeleton had already built
  `parent_turn = ParentTurn(server=server, resolved_key=context.resolved_key,
  model=chat.model_name or "")` inside `run_turn` step 3 and handed
  `await assistant_runtime.resolve_turn_tools(mode_key, parent_turn)` — the combined real+synthetic
  list — to `tools_service.build_tool_bindings` in one call. No other line touched.

### Step 009 — Codex assistant tools
- `backend/app/services/codex_tools.py` — the two callables filled; no frozen signature moved and
  `services/codex.py` still not imported. `codex_search` clamps `limit` to `MAX_SEARCH_LIMIT`
  (bounded output — **no score floor anywhere**), embeds through `embedding.embed_text`, then calls
  `vector.search(book_id=context.book_id, query_vector=…, kinds={SourceKind.codex_entry}, limit=…)`
  — the book comes off the tool context, so no argument can name another book — and renders one
  block per hit **nearest first**: a header line `entry_id=<id> | kind=<kind> | name=<name>` (the
  name segment omitted for a fact) followed by the matched **chunk** text. Each hit's kind and name
  come from the authoritative row (`codex_entries.get_by_id`, cached per id within one call), not
  from the index. Never raises: `EmbeddingError` is mapped by reason (`no_provider` /
  `unreachable` / other) to three distinct error strings, a raw exception from the embed, a sidecar
  failure and a row-read failure each get their own, and **no hits is a plain
  `No codex entries found for "<query>".`** — distinct from every error string.
  `codex_read_entry` parses the wire id (`_parse_entry_id`), reads the row, and answers
  `entry_id=… | kind=… | name=…` plus a blank line plus the body; a malformed id, an unknown id and
  another book's entry all return the **same** not-found string (nothing is confirmed and no content
  leaks), an archived entry its own refusal, and a db failure an error string. Private helpers added:
  the eight message constants, `_parse_entry_id`, `_kind_text`, `_entry_header`, `_render_hit`,
  `_load_indexed_entry`; the module docstring's stale "UNIMPLEMENTED" clause was trimmed and one
  import line added (`from app.models.codex_entry import CodexEntry`).
- `backend/app/services/tools.py` — one branch filled: a `ToolDef` **with** a binder **and** a
  context now appends its `llm.pydantic_to_openai_tool` definition and binds `tool.binder(context)`,
  so both maps keep identical key sets. The three preserved paths are untouched — a bound tool with
  **no** context is still skipped and logged, a plain `callable` is still used verbatim
  (`bindings["web_search"] is web_search` holds), and an entry with neither is skipped. `ToolContext`,
  `ToolBinder`, `ToolDef`, `TOOL_REGISTRY`'s three entries and `resolve_tools` landed complete at the
  skeleton and are unchanged; the `build_tool_bindings` docstring's stale "UNIMPLEMENTED" clauses
  were trimmed.
- `backend/app/services/chat_turn.py` — **verified only, no edit**: the skeleton had already built
  `tool_context = tools_service.ToolContext(book_id=chat.book_id)` in `run_turn` step 3 and passed it
  as `build_tool_bindings`' second positional argument beside the resolved tool list. No signature or
  import moved.

### Step 010 — Shared-canvas write
- `backend/app/services/codex_tools.py` — `write_codex_draft` filled; no frozen signature moved and
  **not one database call on the path** (the module's only db imports stay behind `codex_search` /
  `codex_read_entry` — nothing in the write path reads `codex_entries`, which is what makes
  US-086.AC-2 / US-087.AC-2 / US-088.AC-2 true by construction). The body is an outer never-raise
  guard (`run_delegation`'s shape) over: the editability verdict, the emitter, **one**
  `CanvasFrame` and a short confirmation. Two private helpers added — `_refuse_write` (the whole
  server-side mirror of `frontend/src/work/subject.ts:checkWritePermission`, reading **only** the
  tool context: a non-codex-entry subject or none at all → refused; `subject.entry.archived` →
  refused; `role == co_author` **and** `collaboration_mode == proposal` → refused with the message
  naming **FEAT-010**, the owner never refused, a co-author in a free-mode book never refused;
  `field == "name"` on a **fact** → refused) and `_subject_codex_kind` (an existing entry's kind off
  the row, a blank entry's off `subject.mode_key` through the new `_MODE_KEY_CODEX_KINDS` inverse of
  `assistant_runtime._CODEX_KIND_MODES`, so DoD-9 + DoD-10's "a blank fact refuses a name" is
  answerable with no row). On success **exactly one** frame goes through `context.emit_frame` with
  the event name `"canvas"` and `subject_id = str(entry.id)` — `None` for the blank entry; every
  refusal emits nothing at all. Nine message constants added, in two deliberately distinct
  vocabularies (`Codex draft refused: …` for a verdict, `Codex draft error: …` for a transport
  failure) plus the confirmation. Two import lines widened
  (`app.models.codex_entry.CodexKind`, `app.services.authz`), one added
  (`app.models.book.CollaborationMode`), one `TYPE_CHECKING`-only (`ResolvedSubject`); the
  docstring's stale "Skeleton … UNIMPLEMENTED" clauses were trimmed.
- `backend/app/models/schemas/chats.py` — **verified only, no edit**: `CanvasField` and `CanvasFrame`
  landed complete at the skeleton, field order and required-but-nullable `subject_id` as frozen.
- `backend/app/services/tools.py` — **verified only, no edit**: `FrameEmitter`, the three defaulted
  `ToolContext` fields and the fourth `TOOL_REGISTRY` entry (`write_codex_draft`, bound via
  `bind_write_codex_draft`) landed complete; `build_tool_bindings` needed nothing — the bound-tool
  branch step 009 filled builds the new entry unchanged.
- `backend/app/services/chat_turn.py` — **verified only, no edit**: the skeleton had already moved
  the `asyncio.Queue` above step 3, defined `emit_frame` beside it (the **same**
  put-onto-the-queue path `thinking` / `delta` use, inside the same `drive()` task), built
  `ToolContext(book_id=…, access=context.access, subject=context.subject, emit_frame=emit_frame)`
  and carried `access` on `TurnContext` from `prepare_turn`.
- `backend/app/services/subagent_delegation.py` — **verified only, no edit** (the sanctioned
  out-of-scope edit): `ParentTurn.tool_context` and `_delegate`'s `build_tool_bindings(…,
  parent.tool_context)` landed at the skeleton, so a sub-agent selecting a bound codex tool keeps it.
- `backend/app/routes/chats.py` — **not touched, as the step requires**: its serializer is
  `f"event: {frame.event}\ndata: {frame.data.model_dump_json()}\n\n"`, generic over the event name,
  so a `TurnFrame(event="canvas", …)` reaches the stream as `event: canvas` with no route edit.

### Step 011 — Codex API module, DTOs, and the three list pages
- `frontend/src/types/codex.d.ts` — **verified only, no edit**: the four declarations
  (`CodexKind`, `CreateCodexEntryRequest`, `UpdateCodexEntryRequest`, `CodexEntryResponse`) landed
  complete at the skeleton, wire-exact `snake_case`, every id `string`, timestamps `ISODateString`,
  no list envelope modelled.
- `frontend/src/api/codex.ts` — four bodies filled; no frozen signature moved. Adds the one missing
  import (`request` from `./client`) and nothing else. `listCodexEntries` builds the query string
  with `URLSearchParams` in the route's own order (`kind`, then `q` **only when the needle is
  non-empty**, then `include_archived` always, `false` when the flag is omitted) and returns
  `res.items` — **the `{ items: […] }` envelope is unwrapped here**, so the state holds a plain
  array and the `.d.ts` models no envelope. The other three are thin `request<T>` forwarders
  (`GET` / `POST` / `PUT`), `signal` trailing throughout; a stale `expected_modified_at` therefore
  surfaces untouched as `ApiError(409)` for step 012.
- `frontend/src/work/pages/codexListPageState.ts` — `isEmpty` and both external effect functions
  filled; class shape unchanged. `isEmpty` is `entriesStatus === "ready" && entries.length === 0`,
  so an unmatched search renders the empty state and never the error state, and nothing derived is
  stored. `loadCodexEntries` follows `bookStatePageState.loadBookState` exactly — `runInAction` to
  `loading` + clear the error, `codexApi.listCodexEntries(bookId, state.kind, state.needle ||
  undefined, undefined, signal)`, silent return on `signal?.aborted` (both before and after the
  await), `ApiError → entriesError` / `"error"`, anything else rethrown. The kind is read off
  `state`, never a caller argument. `submitCodexSearch` stays **synchronous**: it commits the
  trimmed `draftNeedle` into `needle` under `runInAction`, fires `loadCodexEntries` without
  awaiting, and returns `new URLSearchParams({ q }).toString()` — or `""` when the needle was
  cleared, so the caller's `setSearchParams("")` drops `q` from the URL.
- `frontend/src/work/pages/CodexListPage.tsx` — render body filled; `CODEX_KIND_LABELS` and
  `CodexListPageProps` untouched. `useSearchParams()` is read **once**, inside the
  `useState(() => new CodexListPageState(kind, searchParams.get("q") ?? ""))` initializer, so a
  deep-linked `?q=` filters the first fetch; the single page-level `useEffect([state])` loads with
  an `AbortController` and aborts on unmount. The submit handler `preventDefault`s, calls
  `submitCodexSearch` and pushes the returned string with `setSearchParams` — **the URL write lives
  in the handler that changed it**, and there is no effect watching the query string anywhere in
  the file (`frontend.md`:192; the repo's first query-param consumer). Renders the kind heading from
  `CODEX_KIND_LABELS`, a `<form>`-wrapped search input bound to `state.draftNeedle` with a submit
  button, a "New entry" button navigating to `/${bookId}/codex/new?kind=${kind}`, and the trio's
  loading / error-with-Retry / empty branches around the two-column table (label + modified-at).
  The row label is `entry.name || bodyExcerpt(entry.body)`, which is what gives a **fact** — whose
  `name` is null by design — a body excerpt instead of a blank cell. Row activation calls
  `navigate('/${bookId}/codex/${entry.id}')` (basename-stripped); the label cell is an
  `UnstyledButton` that `stopPropagation`s so one activation is exactly one navigation. Three small
  module-level pure helpers (`formatTimestamp` — the `BookStatePage` precedent, `bodyExcerpt`,
  `entryLabel`); no `useCallback` / `useMemo` / custom hook, `observer` on the component.
- `frontend/src/work/routes.tsx` — **verified only, no edit**: the three keyed `<CodexListPage>`
  elements, the `codex/new` route ahead of `codex/:id`, and the untouched `codex/:id` placeholder
  all landed at the skeleton. `SubjectPlaceholderPage` is still exported and still used;
  `components/shell/navItems.ts` was not touched.

### Step 012 — The codex entry page
- `frontend/src/work/pages/codexEntryPageState.ts` — every computed and all five external effect
  functions filled; no frozen signature moved and `restoreBuffer.ts` / `subject.ts` consumed
  unchanged. `kind` prefers the **loaded row** for an existing entry and `initialKind` only for a
  blank one; `requiresName` is the character/location test and doubles as the name field's render
  gate; `nameError` is **local only** (blank name on a character/location, any name on a fact) and
  `saveError` — the server's own text — never merges into it. `editability` calls
  `resolveEditability({kind: "codex-entry", entityId, codexArchived: entry?.archived})`, so the
  archived wording is `subject.ts`'s verbatim; `canSave` is `!isReadOnly && isValid && not saving &&
  not reconciling` (dirtiness deliberately does not gate it); `baseVersion` is derived from `entry`,
  which is what makes adopting a save response a single assignment.
  `loadCodexEntry` settles a blank entry at `"ready"` having contacted neither the server nor
  `localStorage`; an existing entry loads, seeds both drafts, then reads the buffer at
  `restoreBufferKey(bookId, "codex-entry", entryId)` — a **matching** `baseVersion` restores the
  buffered body, a **mismatch** puts the buffered body in `bodyDraft`, the loaded entry in
  `conflictEntry` and raises `isReconciling` **with no save attempt**. `editCodexDraft` is
  synchronous and server-free (nothing reaches the server until Save) and buffers the **body only**,
  writing `state.baseVersion ?? ""` and recording a `"saved-after-eviction"` result's keys.
  `saveCodexEntry` creates (blank, with the `?kind=` kind) and returns `/${bookId}/codex/${id}` for
  the caller to navigate to, or updates carrying the **loaded** `modified_at` as
  `expected_modified_at`, then adopts the response and clears the buffer; a **409** re-fetches into
  `conflictEntry` + `isReconciling` (never a merge, and `saveError` stays null — the divergence view
  *is* the warning), and every other `ApiError` — chiefly the **403** proposal-mode refusal naming
  FEAT-010 — lands the server's text in `saveError` with the draft and its buffer untouched.
  `resolveCodexConflict` takes one side: `"server"` clears the buffer and reseeds from the server's
  entry; `"draft"` adopts `conflictEntry` **first** (so `baseVersion` is the server's new
  `modified_at`), leaves the view, then re-saves. Private additions: the two local validation
  messages, `MISSING_KIND_MESSAGE`, and `serverRefusalText` (see Notes & Issues — the reason is
  **nested** at `details.detail`).
- `frontend/src/work/pages/CodexEntryPage.tsx` — the render body filled; `CodexEntryPageProps` and
  the frozen render contract unchanged. `useState` holds the state instance, seeded from `useParams`
  plus `parseCodexKind(searchParams.get("kind"))` read **once** in the initializer; the single
  page-level `useEffect([state])` loads with an `AbortController` and aborts on unmount. Branches:
  the load trio's error (with Retry) and loading states, then the **reconciliation view** while
  `state.isReconciling` — `conflictEntry.body` against `state.bodyDraft`, side by side, with
  "Keep the server version" / "Keep my draft" calling `resolveCodexConflict` — otherwise the editor:
  the `Name` field rendered **only** when `state.requiresName` (a fact shows none) carrying
  `state.nameError` as its field error, the `Body` `Textarea`, both routing every change through
  `editCodexDraft` so the buffer write can never be skipped. Save is **rendered disabled** when
  `!state.canSave` (which is why an archived entry's save action is unavailable), Discard calls
  `discardCodexDraft`. Four separate surfaces: the read-only banner showing
  `state.editability.readOnlyReason`, the server's `state.saveError` alert (distinct from the field
  error), the eviction notice listing each `state.evictedBufferKeys` entry on its own line, and the
  unsaved-changes hint off `state.isDirty`. One module-level `KIND_HEADINGS` constant; `observer`,
  no `useCallback` / `useMemo` / custom hook / context / `useForm`.
- `frontend/src/work/routes.tsx` — **verified only, no edit**: the skeleton had already repointed
  `CodexEntryItemRoute` to `<CodexEntryPage key={id} mode="existing" />` and `codex/new` to
  `<CodexEntryPage mode="blank" />`, kept the static-before-dynamic order, and left
  `SubjectPlaceholderPage` imported and in use by the remaining placeholder routes.

### Step 013 — Subject → chat wiring and canvas application
- `frontend/src/work/contentSubject.ts` — the four frozen bodies filled; no signature moved, and the
  module stays plain functions at the `restoreBuffer.ts` / `activeChat.ts` tier (no class, no MobX,
  no React, no `src/api/` import). One module-level `registration: {source, applyDraft?} | null`.
  `registerContentSubject` overwrites outright (newest wins); `unregisterContentSubject` clears
  **only** when `registration.source === source`, so a late unmount from a superseded page is a
  no-op; `currentContentSubject` **invokes** the source (never snapshots it) or returns `null`.
  `dispatchCanvasFrame` hands `(frame.field, frame.text)` to the registered apply-draft callback when
  the subject's kind **and** `entityId ?? null` both equal the frame's, and otherwise writes the text
  to `restoreBufferKey(bookId, "codex-entry", frame.subject_id)`; a frame with `subject_id === null`
  and no matching target is dropped. The runtime import of `restoreBuffer` (`readBuffer` /
  `restoreBufferKey` / `writeBuffer`) is the only import added.
- `frontend/src/types/chats.d.ts` — **verified only, no edit**: the five declarations the skeleton
  landed (`SubjectKind`, `TurnSubject`, `TurnRequest`, `CanvasField`, `CanvasFrame`) are wire-exact
  with the backend's step-007/010 schemas and complete as written.
- `frontend/src/api/chats.ts` — the `canvas` branch added inside `streamPost`'s `onEvent` callback
  (`handlers.onCanvas?.(frame)`), plus a private `canvasFrame(data: unknown): CanvasFrame | null`
  narrower beside `frameText` — a malformed payload is dropped, never forwarded, and an **absent**
  `subject_id` is malformed (only an explicit `null` is UC-076's blank entry). `streamChatTurn`'s
  frozen signature, its `refreshAuthToken()`-then-`streamPost` shape and its no-`signal` seam are
  untouched, and **`api/sse.ts` was not opened** — `canvas` rides its existing generic-event branch.
- `frontend/src/work/components/chat/chatPaneState.ts` — `sendChatTurn` and `retryChatTurn` now pass
  `turnSubject()` as `streamChatTurn`'s trailing argument, evaluated **at send/retry time**; a new
  private `turnSubject(): TurnSubject | undefined` reads `currentContentSubject()` and maps
  `kind` → `subject_kind`, `entityId ?? null` → `subject_id`, `codexKind ?? null` → `codex_kind`,
  returning `undefined` when nothing is registered (so the posted body is exactly `{ prompt }`).
  `ChatPaneState` gained **no field**; no exported signature moved, so `ChatPane.tsx` and
  `WorkspaceShell.tsx` needed nothing.
- `frontend/src/work/pages/codexEntryPageState.ts` — `get contentSubject()` filled: `kind`
  `"codex-entry"` always, `codexArchived` from the loaded row (`false` before it resolves),
  `codexKind` from `this.kind`, and `entityId` set **only** when `entryId !== null` (the key is left
  absent, not `undefined`, for a blank entry). `applyDraft` was already correct and is untouched.
- `frontend/src/work/pages/CodexEntryPage.tsx` — the **existing** page-level `useEffect([state])`
  now also registers `const source = () => state.contentSubject` with `state.applyDraft` as the
  canvas target, and unregisters that same reference in the cleanup that aborts the load. No second
  effect, no `useCallback`, no wrapper around `applyDraft`.
- `frontend/src/work/pages/CodexListPage.tsx` — same one effect registers a **kind-only** source
  (`() => ({ kind: LIST_SUBJECT_KINDS[kind] })`) with **no** apply-draft callback, so a list resolves
  to a subject with no id and no canvas target, and unregisters it by identity on cleanup. One
  private `LIST_SUBJECT_KINDS: Record<CodexKind, SubjectKind>` constant (`character → "characters"`
  etc.).

Gates: `cd frontend && npx tsc --noEmit` and `cd frontend && npm run build` (= `tsc && vite build`)
both pass. `npm test` deliberately not run — it is the verifier's gate.

## Skeleton

### Step 001 — frozen interface (2026-07-27)

- `backend/app/db/codex_entries.py` — `async def list_by_book(book_id: int, kind: CodexKind | None = None, include_archived: bool = False, needle: str | None = None) -> list[CodexEntry]` — changed (was `async def list_by_book(book_id: int) -> list[CodexEntry]`). `CodexKind` is imported from `app.models.codex_entry`. Body: the pre-013 unfiltered/unordered path is preserved for `list_by_book(book_id)`; any non-default `kind` / `include_archived` / `needle` raises `NotImplementedError`. Filtering **and** the name-then-id (nulls last) ordering are the coder's.
- `backend/app/db/codex_entries.py` — `async def update(row: CodexEntry) -> CodexEntry` — new (raises `NotImplementedError`). Row-in / row-out, following `db/chats.py:update`; this layer sets no timestamps — the service owns `modified_at` / `modified_by`.
- `backend/app/db/codex_entry_versions.py` — `async def next_generation(entry_id: int) -> int` — new (raises `NotImplementedError`).
- `backend/app/db/codex_entry_versions.py` — `async def list_by_entry(entry_id: int) -> list[CodexEntryVersion]` — **unchanged signature** (ascending-`generation` ordering is behavior, left to the coder; the pre-013 body is preserved).
- `backend/app/services/authz.py` — `Capability.browse_codex = "browse_codex"` — new enum member. Matrix row: `frozenset({AccessRole.owner, AccessRole.co_author})`.
- `backend/app/services/authz.py` — `Capability.edit_codex_entry = "edit_codex_entry"` — new enum member. Matrix row: `frozenset({AccessRole.owner, AccessRole.co_author})`.
- `backend/app/services/authz.py` — `BookAccess`, `AccessRole`, `BookAuthorizationError`, `resolve_book_access`, `book_access`, `require` and the seven pre-existing capabilities/matrix rows are **untouched**. No collaboration-mode notion was added to the matrix (step 002's service applies it).
- Caller-compile edits (out of Source-files scope): None. `list_by_book` gained defaulted keyword parameters only; its sole existing caller (`backend/tests/test_data_domain_codex.py`) keeps compiling and passing untouched.

Notes for the pipeline: the step file places the capability × role cells under **Interface intent** and `services/authz.py`'s own docstring declares `_CAPABILITY_MATRIX` part of the frozen contract, so the two rows are populated here rather than left empty — DoD-10, DoD-11 and DoD-12 will therefore be **green at the red gate**. Every other `[test]` DoD item (1–9) is red: 1/3 raise `NotImplementedError`, 2/4/5/9 fail on missing filtering and ordering, 6/7/8 raise `NotImplementedError`.

### Step 002 — frozen interface (2026-07-27)

Both files are **new**; nothing outside them was touched.

**`backend/app/models/schemas/codex.py`** — Pydantic DTOs, declarative (complete, nothing unimplemented). Imports `CodexKind` from `app.models.codex_entry`; every id is `str`.

- `class CreateCodexEntryRequest(BaseModel)` — new — `kind: CodexKind`, `name: str | None = None`, `body: str`
- `class UpdateCodexEntryRequest(BaseModel)` — new — `name: str | None = None`, `body: str`, `expected_modified_at: datetime | None` (**required but nullable** — an omitted field must not silently pass the staleness check; `kind` is absent by design, not updatable)
- `class CodexEntryResponse(BaseModel)` — new — `id: str`, `book_id: str`, `kind: CodexKind`, `name: str | None`, `body: str`, `archived: bool`, `author_id: str`, `modified_by: str | None`, `created_at: datetime | None`, `modified_at: datetime | None`
- `class CodexEntryListResponse(BaseModel)` — new — `items: list[CodexEntryResponse]`

**`backend/app/services/codex.py`** — the error taxonomy is complete; **every function body raises `NotImplementedError`**.

- `class CodexErrorReason(str, enum.Enum)` — new, complete — members (name = wire value): `entry_not_found = "entry-not-found"`, `name_required = "name-required"`, `name_not_allowed = "name-not-allowed"`, `entry_archived = "entry-archived"`, `stale_modified_at = "stale-modified-at"`, `proposal_mode_unsupported = "proposal-mode-unsupported"`. Shape copied from `services/chats.py:ChatErrorReason`; step 003's `_CODEX_ERROR_STATUS` binds to these six.
- `class CodexError(Exception)` — new, complete — `def __init__(self, reason: CodexErrorReason, message: str = "") -> None`, exposing `.reason` / `.message`. Copied from `services/chats.py:ChatError`.
- `def _to_entry_response(entry: CodexEntry) -> CodexEntryResponse` — new (raises `NotImplementedError`). The sole constructor of the DTO.
- `async def create_entry(access: authz.BookAccess, user: User, req: CreateCodexEntryRequest) -> CodexEntryResponse` — new (raises `NotImplementedError`).
- `async def list_entries(access: authz.BookAccess, kind: CodexKind | None = None, needle: str | None = None, include_archived: bool = False) -> CodexEntryListResponse` — new (raises `NotImplementedError`). The route's `q` query param maps to `needle` (the db layer's word).
- `async def get_entry(access: authz.BookAccess, entry_id: str) -> CodexEntryResponse` — new (raises `NotImplementedError`). `entry_id` is the **wire string** id (`chats.get_chat` precedent); an unknown id, a non-numeric id and another book's entry all raise `entry_not_found`.
- `async def update_entry(access: authz.BookAccess, user: User, entry_id: str, req: UpdateCodexEntryRequest) -> CodexEntryResponse` — new (raises `NotImplementedError`).
- `User` is `app.models.user.User` — the **acting user**, passed alongside `access` on the two write paths per the step file ("takes the access context, the acting user and a …request"). Step 003's handlers therefore add `Depends(auth_service.get_current_user)` beside `Depends(authz.book_access)`.
- Caller-compile edits (out of Source-files scope): None — both modules are new and nothing imports them yet.

Notes for the pipeline: no private helper beyond `_to_entry_response` is frozen — id parsing, the kind/name rule and the collaboration-mode rule are behavior inside the four public functions and the coder may factor them freely. Every `[test]` DoD item (1–17) is red at the gate: each one enters through `create_entry` / `list_entries` / `get_entry` / `update_entry`, all of which raise `NotImplementedError` — including DoD-17, whose `authz.require` refusal is behavior the coder adds. Full suite after the stubs: 547 passed.

### Step 003 — frozen interface (2026-07-27)

**`backend/app/routes/codex.py`** — **new** file. `router = APIRouter(prefix="/api/books", tags=["codex"])`, mounted bare in `main.py`. Imports: `CodexKind` from `app.models.codex_entry`, the four DTOs from `app.models.schemas.codex`, `User` from `app.models.user`, `app.services.auth as auth_service`, `app.services.authz as authz`, `app.services.codex as codex_service`.

Declarative supporting shapes — **complete, nothing unimplemented**:

- `class CodexErrorDetail(TypedDict)` — new, complete — `reason: str`, `message: str`. **This is the `detail` body of every `CodexError` refusal**, i.e. the wire body is `{"detail": {"reason": "<CodexErrorReason value>", "message": "<text>"}}`. Structured (not a bare string) because the step file requires "the reason value in the detail body so the client can branch on it"; a `TypedDict` satisfies the root `CLAUDE.md` no-free-dictionaries rule without putting a Pydantic schema in `routes/`.
- `_CODEX_ERROR_STATUS: dict[codex_service.CodexErrorReason, int]` — new, complete — exactly six entries: `entry_not_found` → `404`, `name_required` → `400`, `name_not_allowed` → `400`, `entry_archived` → `400`, `stale_modified_at` → `409`, `proposal_mode_unsupported` → `403`.
- `def _map_codex_error(err: codex_service.CodexError) -> HTTPException` — new, complete — `HTTPException(status_code=_CODEX_ERROR_STATUS[err.reason], detail=CodexErrorDetail(reason=err.reason.value, message=err.message))`.
- `def _map_authz_error(err: authz.BookAuthorizationError) -> HTTPException` — new, complete — **403** with `detail=str(err)` (a plain string), copied verbatim from `routes/books.py` / `routes/chats.py`. The two 403 producers are therefore distinguished by their detail body, not their status: the authz denial's detail is a string, the proposal-mode refusal's is a `CodexErrorDetail` object.

The four handlers — **every body raises `NotImplementedError`**. No handler declares `book_id`; the `authz.book_access` dependency consumes it. Declaration order is as listed and is load-bearing (`/{book_id}/codex` before `/{book_id}/codex/{entry_id}`).

- `@router.post("/{book_id}/codex", status_code=status.HTTP_201_CREATED)` — `async def create_codex_entry(payload: CreateCodexEntryRequest, access: authz.BookAccess = Depends(authz.book_access), caller: User = Depends(auth_service.get_current_user)) -> CodexEntryResponse` — new.
- `@router.get("/{book_id}/codex")` — `async def list_codex_entries(kind: CodexKind | None = None, q: str | None = None, include_archived: bool = False, access: authz.BookAccess = Depends(authz.book_access)) -> CodexEntryListResponse` — new. Wire query params are exactly `kind` / `q` / `include_archived`, all optional, `include_archived` defaulting to `false`; `q` feeds the service's `needle` argument.
- `@router.get("/{book_id}/codex/{entry_id}")` — `async def get_codex_entry(entry_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> CodexEntryResponse` — new. `entry_id` is the wire **string** id (the service parses it; a non-numeric id is `entry_not_found` → 404, not a 422).
- `@router.put("/{book_id}/codex/{entry_id}")` — `async def update_codex_entry(entry_id: str, payload: UpdateCodexEntryRequest, access: authz.BookAccess = Depends(authz.book_access), caller: User = Depends(auth_service.get_current_user)) -> CodexEntryResponse` — new.

**`backend/app/main.py`** — router include only: `from app.routes import codex` plus `app.include_router(codex.router)` after `chats`. Nothing else touched — in particular the `await vector.init_vector(settings.lancedb_dir)` startup call is untouched (step 005's).

- Caller-compile edits (out of Source-files scope): None.

Notes for the pipeline: response models are the return annotations (no `response_model=` anywhere), matching every other router. Verified by generating the OpenAPI schema — all four paths register with the right methods, `201` on create, the correct response schemas, and query params `kind`/`q`/`include_archived` on the list route. At the red gate the four handlers raise `NotImplementedError`, so **DoD-1 … DoD-11 and DoD-13 are red** (a 500 instead of the expected status). **DoD-12 (non-member → 404 from all four routes) and DoD-14 (no token → 401 from all four routes) will be GREEN at the red gate** — both are produced by the `book_access` / `get_current_user` dependencies, which run before the handler body; that is inherited behavior this step re-asserts, not behavior the coder adds. Full suite after the stubs: 583 passed.

### Step 004 — frozen interface (2026-07-27)

**`backend/app/services/embedding.py`** — **new** file, and the only file touched. Module-level imports (the patch targets the tests bind to): `from app.db import llm_servers as llm_servers_db`, `from app.services import llm_servers as llm_servers_service`, `from app.services import secrets` — the `chat_turn.py:49-64` naming, so the designated-server lookup is mocked at `app.db.llm_servers.get_embedding_server` and the client factory at `app.services.llm_servers.create_model_client`. The `secrets` import is **module-level, not function-local**: `secrets → llm_servers` is the only pre-existing edge and nothing imports `embedding`, so the graph stays acyclic (verified by importing the module); the `llm_servers.py:351` function-local form guards the reverse edge and is not needed here — a comment in the module docstring records this. **`app.db.vector` is not imported** (`db → services` is forbidden; step 005 injects instead).

Declarative taxonomy — **complete, nothing unimplemented**:

- `class EmbeddingErrorReason(str, enum.Enum)` — new, complete — three members (name = wire value): `no_provider = "no-provider"`, `unreachable = "unreachable"`, `dimension_mismatch = "dimension-mismatch"`. Shape copied from `services/chats.py:ChatErrorReason`. `unreachable` covers transport (`aiohttp.ClientError`), `LLMError` **and** an unresolvable `$ENV` ref (`LlmServerError(env_not_set)`) — one reason, three causes, per DoD-5/DoD-6.
- `class EmbeddingError(Exception)` — new, complete — `def __init__(self, reason: EmbeddingErrorReason, message: str = "") -> None`, exposing `.reason` / `.message`. Copied from `services/chats.py:ChatError`.

The five functions — **every body raises `NotImplementedError`**:

- `async def is_available() -> bool` — new. The availability probe: true only when a row is designated **and** its `embedding_model` is present and non-blank. Contacts no client, never raises for the unconfigured case.
- `async def embed_batch(texts: Sequence[str]) -> list[list[float]]` — new. The batch embed; one vector per text in input order. `Sequence` is `collections.abc.Sequence`.
- `async def embed_text(text: str) -> list[float]` — new. The single-text/query path; a thin wrapper over `embed_batch`, returning the vector itself (not a one-element list).
- `async def probe_dimension() -> int` — new. Embeds the short constant probe text and returns the returned vector's length.
- `def check_dimension(vectors: Sequence[Sequence[float]], expected_dimension: int) -> None` — new. **Synchronous**, I/O-free; raises `EmbeddingError(dimension_mismatch)` when any vector's length differs, returns `None` otherwise.

Also present but **not frozen contract**: `_PROBE_TEXT = "dimension probe"` — a private module constant the coder may reword; only the behaviour (one short constant string) is specified.

- Caller-compile edits (out of Source-files scope): None — the module is new and nothing imports it yet.

Notes for the pipeline: the two step-005 injection points are `probe_dimension` (no arguments) and `embed_batch` (one positional `Sequence[str]`), so `init_vector` types against `Callable[[], Awaitable[int]]` and `Callable[[Sequence[str]], Awaitable[list[list[float]]]]` — `db/vector.py` must spell those out itself, since it may not import this module to reuse an alias. Every `[test]` DoD item (1–11) is **red** at the gate: 1/2/3 enter through `embed_batch`/`is_available`, 4–9 through `embed_batch`, 10 through `probe_dimension`, 11 through `check_dimension` — all `NotImplementedError`. Module imports cleanly (`python -c "from app.services import embedding"`); full suite after the stubs: **597 passed**.

### Step 005 — frozen interface (2026-07-27)

**`backend/app/db/vector.py`** — rewritten from feature 007's 95-line shell. Module-level imports added: `enum`, `dataclasses.dataclass`, `Awaitable`/`Collection` (beside the existing `Callable`), `Generic`/`TypeVar`, `from sqlmodel import SQLModel`, `from app.models.codex_entry import CodexEntry`. **`app.services.embedding` is NOT imported** (`db → services` is forbidden — the callables are injected instead), and `from app.db import codex_entries` is deliberately **not** added yet (see the registry note below).

Declarative surface — **complete, nothing unimplemented**:

- `EmbedBatch = Callable[[Sequence[str]], Awaitable[list[list[float]]]]` — new type alias. Structurally matches step 004's `embedding.embed_batch`; spelled out here rather than imported.
- `ProbeDimension = Callable[[], Awaitable[int]]` — new type alias. Matches step 004's `embedding.probe_dimension`.
- `CHUNK_TABLE_NAME = "chunks"` — new. The single sidecar table; its columns are fixed by `retrieval.md` (`vector`, `book_id`, `source_kind`, `source_id` as a **string**, `chunk_index`, `text`) and are not separately frozen as constants.
- `class SourceKind(str, enum.Enum)` — new, complete — **one** member: `codex_entry = "codex_entry"`. The `CodexKind` precedent (fixed taxonomy, one table); `retrieval.md`'s three later corpora get members when their chunkers land. Subclasses `str`, so `hit.source_kind == "codex_entry"` holds and a test may bind either way.
- `@dataclass(frozen=True) class ChunkHit` — new, complete — `source_kind: SourceKind`, `source_id: str`, `chunk_index: int`, `text: str`, `score: float`. `source_id` is the **string** form the index stores (and the form `services/codex.py`'s wire-string entry points already take). Frozen typed record, not a dict, following `services/tools.py:ToolDef`.
- `CHUNK_SIZE_CHARS = 1200`, `CHUNK_OVERLAP_CHARS = 200`, `SINGLE_CHUNK_THRESHOLD_CHARS = CHUNK_SIZE_CHARS` — new. The three tuning constants; names frozen, values as-built per `005.context.md`.
- `TRow = TypeVar("TRow", bound=SQLModel)`; `RowSelector = Callable[[], Awaitable[Sequence[TRow]]]`; `Chunker = Callable[[TRow], list[str]]` — new generic aliases.
- `@dataclass(frozen=True) class VectorSource(Generic[TRow])` — new, complete — `source_kind: SourceKind`, `model_class: type[TRow]`, `row_selector: RowSelector[TRow]`, `chunker: Chunker[TRow]`. **This replaces the `(model_class, text_extractor)` tuple** — a tuple could not express "one row becomes many vectors". Field order is as listed; construct by keyword.
- `VECTOR_SOURCE_REGISTRY: list[VectorSource[Any]] = []` — **changed** (was `list[tuple[type, Callable[..., str]]] = []`). Still an empty literal list at the skeleton — see the note below. `Any` is the honest parameter for a heterogeneous registry (`_db: Any` is the same module's precedent).
- `class VectorIndexError(Exception)` — new, complete (**added 2026-07-27 after the orchestrator's ruling on the `## Notes & Issues` block**). A **plain exception class with no reason enum and no custom `__init__`** — bind with `pytest.raises(vector.VectorIndexError)`, read the text with `str(err)`. Chosen over the repo's `XErrorReason` + `XError` pairing (`ChatError` / `CodexError` / `EmbeddingError`) because this module can name exactly **one** failure of its own — "`rebuild_index` must embed and no embedder was injected at `init_vector`" — and a one-member enum would be noise; every *embedding-side* failure already has `services/embedding.py:EmbeddingErrorReason`, which `db/` may not import (`db → services`) and must not duplicate, so those errors travel out of the injected callables unchanged. `db/import_export_queries.py:run_vector_rebuild` logs and swallows it (DoD-14); `services/db_admin.py:rebuild_vector_index` propagates it.

The functions:

- `async def init_vector(vector_dir: Path, embed_batch: EmbedBatch | None = None, probe_dimension: ProbeDimension | None = None) -> None` — **changed** (was `async def init_vector(vector_dir: Path) -> None`). **Body is implemented, not stubbed**: the pre-013 connect is preserved and the two callables are stored in new module globals `_embed_batch` / `_probe_dimension` (both `None` until injected). The two new parameters **default to `None`** — non-negotiable, because `backend/tests/services/test_db_admin_rebuild.py:89,103` and `rebuild_index`'s own lazy self-connect call it with one argument; making them required would break those at the skeleton. A test injects deterministic doubles by keyword exactly as `main.py` injects the real ones.
- `async def get_table_dimension() -> int | None` — new (raises `NotImplementedError`). The table-dimension accessor; `None` when no chunk table exists yet. Step 006 compares an incoming batch against it.
- `async def upsert_chunks(book_id: int, source_kind: SourceKind, source_id: int, chunks: Sequence[tuple[str, Sequence[float]]]) -> None` — new (raises `NotImplementedError`). `chunks` is the ordered `(text, vector)` pairing; `chunk_index` runs from zero in that order. `source_id` is passed as an `int` and stringified **inside the module** (the one conversion site). Returns nothing — the Interface intent names no return value.
- `async def delete_by_source(source_kind: SourceKind, source_id: int) -> None` — new (raises `NotImplementedError`). Keyed on `(source_kind, source_id)`, not on the id alone: the table is discriminated, so a delete can never reach another corpus's rows, and `upsert_chunks` already holds both.
- `async def delete_by_book(book_id: int) -> None` — new (raises `NotImplementedError`).
- `async def search(book_id: int, query_vector: Sequence[float], kinds: Collection[SourceKind] | None = None, limit: int = 10) -> list[ChunkHit]` — new (raises `NotImplementedError`). Takes an **already-embedded** query vector (`db/` may not embed — the documented narrowing against `retrieval.md`'s `search(book_id, query_text, …)`); `kinds` is `Collection` so a set **or** a list binds; `book_id` is a hard in-query filter.
- `def chunk_codex_entry(entry: CodexEntry) -> list[str]` — new (raises `NotImplementedError`). **Synchronous and pure.** The name-prefix *format* is the coder's choice; only determinism is frozen.
- `async def rebuild_index() -> int` — **unchanged signature**, and it stays unchanged: per the orchestrator's ruling it now **raises `VectorIndexError`** when it reaches a point where it must embed and no embedder was injected, which does not alter the `-> int` annotation and does not move either caller's zero-argument call shape. The pre-013 body is **preserved**: the frozen connection contract (reuse `_db`, else lazily `init_vector(get_settings().lancedb_dir)`) and the drop-every-table reset are intact. The **new** passes are unimplemented: a comment marks the probe-then-create-table pass (which is where the `VectorIndexError` guard lands), and the per-source loop body raises `NotImplementedError` (unreachable while the registry is empty).

**`backend/app/db/codex_entries.py`** — one addition; step 001's four functions are untouched.

- `async def list_all_unarchived() -> list[CodexEntry]` — new (raises `NotImplementedError`). The registry's row selector: every non-archived entry across **all** books, ordered by `id`. Takes no `book_id` by design (a rebuild is instance-wide).

**`backend/app/db/import_export_queries.py`** — **not edited.** `async def run_vector_rebuild() -> None` holds unchanged; the log-and-swallow guard is behavior and is entirely the coder's.

**`backend/app/main.py`** — composition-root wiring only: `from app.services import embedding as embedding_service`, and the startup call becomes `await vector.init_vector(settings.lancedb_dir, embed_batch=embedding_service.embed_batch, probe_dimension=embedding_service.probe_dimension)`. Nothing else touched.

- Caller-compile edits (out of Source-files scope): None.

Notes for the pipeline:

- **The registry ships EMPTY at the skeleton — deliberately.** Its *shape* (`VectorSource` + `SourceKind`) is complete, but the single `codex_entry` entry is the coder's one-line wiring (`VectorSource(source_kind=SourceKind.codex_entry, model_class=CodexEntry, row_selector=codex_entries.list_all_unarchived, chunker=chunk_codex_entry)` plus `from app.db import codex_entries`); the docstring at the registry spells it out verbatim. Three reasons: (1) unlike step 001's `_CAPABILITY_MATRIX` or step 003's `_CODEX_ERROR_STATUS`, this entry is **live wiring** to two callables that both raise, not inert data; (2) populating it keeps DoD-11 and DoD-12 genuinely red; (3) `backend/tests/services/test_db_admin_rebuild.py:159` currently asserts `VECTOR_SOURCE_REGISTRY == []` and is **out of this step's Test-files scope** — populating now would turn a green, untouchable test red *before* the red gate and muddy the verifier's signal. See `## Notes & Issues` for the scope collision that entails.
- **Red-gate expectations.** DoD-1…DoD-11 are red (`get_table_dimension` / `upsert_chunks` / `delete_by_source` / `delete_by_book` / `search` / `chunk_codex_entry` all raise; DoD-11 sees an empty registry). DoD-12 is red (`rebuild_index` returns 0 with nothing indexed). **Two items to watch, both because the skeleton preserves the pre-013 "reset and return 0" body:**
  - **DoD-13** — a test asserting only "returns zero for an empty codex" is **green by accident**; the "leaves a usable empty table" half (via `get_table_dimension`, or a `search` that returns `[]` instead of raising) is what makes it red.
  - **DoD-14** — the log-and-swallow guard is the coder's, and at the skeleton `rebuild_index` cannot fail (empty registry, no `VectorIndexError` guard yet), so a test asserting only "`run_vector_rebuild()` completes" is **green by accident**. It goes red by *observing the swallow* — e.g. asserting the failure was logged, or forcing `rebuild_index` to raise (an injected embedder that raises, or the un-injected `VectorIndexError` path decision 1 introduces) and asserting `run_vector_rebuild` still returns while `db_admin.rebuild_vector_index` propagates.
  - DoD-15 is red once the test-coder inverts the superseded assertions in `test_data_domain_codex.py` and `test_db_admin_rebuild.py`.
- Verified: `app.main` and `app.db.vector` import cleanly; every signature above confirmed by `inspect.signature`; `VectorSource` and `ChunkHit` construct; `RowSelector[CodexEntry]` / `Chunker[CodexEntry]` subscript correctly. Full suite after the stubs: **624 passed**.

### Step 006 — frozen interface (2026-07-27)

**`backend/app/services/codex_index.py`** — **new** file, the bulk of the step. Module-level imports (the patch targets the tests bind to): `from app.db import vector`, `from app.models.codex_entry import CodexEntry`, `from app.services import embedding as embedding_service`, plus `logger = logging.getLogger(__name__)` (an `app.*` logger, the step-005 log-assertion shape). **`app.services.codex` is NOT imported** — the edge is one-way (`codex` → `codex_index`) and back-importing is forbidden; verified by importing both modules and `app.main`.

Declarative surface — **complete, nothing unimplemented**:

- `class IndexStatus(str, enum.Enum)` — new, complete — three members (name = wire value): `indexed = "indexed"`, `dropped = "dropped"`, `failed = "failed"`. `dropped` is a **success**: it is what the archived-entry path and `drop_entry` report.
- `class IndexFailureReason(str, enum.Enum)` — new, complete — four members: `no_provider = "no-provider"`, `unreachable = "unreachable"`, `dimension_mismatch = "dimension-mismatch"`, `sidecar_error = "sidecar-error"`. The first three mirror `services/embedding.py:EmbeddingErrorReason` **member-for-member (same names, same values)**, so a caught `EmbeddingError` maps across by value; `sidecar_error` is every failure raised by `db/vector.py` itself.
- `@dataclass(frozen=True) class IndexOutcome` — new, complete — `status: IndexStatus`, `chunk_count: int = 0`, `reason: IndexFailureReason | None = None`. **This is the deliberate return-type freeze**: a small typed record rather than a bare `bool`, because "the archived entry was dropped", "three chunks were written" and each of the four failure causes are materially different outcomes a test must tell apart. Invariants: `reason` is set **iff** `status is failed`; `chunk_count` is zero for `dropped` and `failed`. Field order as listed; construct by keyword. Follows `db/vector.py:ChunkHit`.
- `_SIDECAR_FAILURE_EXCEPTIONS: tuple[type[Exception], ...]` — new, complete — `(vector.VectorIndexError, OSError, ValueError, RuntimeError)`. Private, shape copied from `chat_turn.py:_TURN_FAILURE_EXCEPTIONS`. **Recorded here because the test-coder needs to know what a mocked sidecar may raise to exercise DoD-7**: any of these four out of `vector.get_table_dimension` / `upsert_chunks` / `delete_by_source` must surface as `IndexOutcome(failed, reason=sidecar_error)`. Its docstring pins where it may be used — around the `db/vector.py` calls only, never around `chunk_codex_entry` (pure; its programming errors must keep failing loudly) and never as a bare `except Exception` over the body (`006.context.md`). `embedding.EmbeddingError` is caught by name beside it.

The two public operations — **both bodies UNIMPLEMENTED**:

- `async def index_entry(entry: CodexEntry) -> IndexOutcome` — new. Takes the entry **row** (not an id to re-read — the codex service already holds the freshly stored row). Chunks it, embeds the chunks in **one** batch, checks the vectors against the live table's dimension (skipped when `get_table_dimension()` is `None` — the first upsert creates the table), replaces the entry's chunks via `vector.upsert_chunks(book_id, SourceKind.codex_entry, entry.id, chunks)`. An **archived** entry delegates to `drop_entry` and reports `dropped`. **Never raises.**
- `async def drop_entry(entry: CodexEntry) -> IndexOutcome` — new. Removes one entry's chunks (`vector.delete_by_source`). Takes the entry **row** too, for symmetry and so the log line can name the book. Dropping chunks that are not there is a **success** (`dropped`), not a failure — `delete_by_source` is already a no-op on a missing table. Public **for `017.codex-archive-restore`**, which calls it on archive rather than re-deriving the archived rule. **Never raises.**

No other private helper is frozen — the failure→reason mapping, the positional chunk/vector pairing guard (the one `db/vector.py:rebuild_index` applies on the rebuild path; `## Notes & Issues` records that the incremental path needs its own) and the log wording are behavior the coder may factor freely.

**`backend/app/services/codex.py`** — **two call sites, nothing else changed.** Step 002's frozen signatures (`CodexErrorReason`, `CodexError`, `_to_entry_response`, `create_entry`, `list_entries`, `get_entry`, `update_entry`) all stand, confirmed by `inspect.signature`.

- Added `from app.services import codex_index`.
- `create_entry` — `await codex_index.index_entry(entry)` **after** `codex_entries.create(...)` returns and **before** `_to_entry_response(entry)`.
- `update_entry` — `await codex_index.index_entry(entry)` **after** `codex_entries.update(entry)` returns (i.e. after both the version row and the entry mutation have committed) and before the DTO is built.
- Both discard the outcome — a failed index leaves a successful save. Neither call changes what the service returns or raises. The module docstring's "**Not here:** vector/embedding maintenance is step 006's wiring … Nothing embedding-shaped is called from this module" paragraph was replaced by the as-built description of these two call sites; no other line moved.

- Caller-compile edits (out of Source-files scope): None.

Notes for the pipeline:

- **Why the stubs RETURN instead of raising** — the never-raise contract is part of the *frozen signature here*, not behavior the coder adds later, and `services/codex.py` awaits `index_entry` inside `create_entry` / `update_entry`. A `NotImplementedError` stub would therefore change what two already-shipped, fully-tested entry points raise and would turn ~40 green step-002/003 tests red **before** the red gate — exactly the muddied signal step 005's `## Notes & Issues` block was about. Both stubs instead return `IndexOutcome(status=IndexStatus.failed)` — `failed` **with no `reason`**, a record the real implementation can never produce (every real failure carries one). Neither stub logs, deliberately.
- **Red-gate expectations.** DoD-1, DoD-2, DoD-3 and DoD-8 are unambiguously red (nothing is chunked, embedded or written; an archived entry reports `failed`, not `dropped`; the mocked embedder is never called). DoD-4, DoD-5, DoD-6, DoD-7 and DoD-10 are the ones to write carefully — "the save still succeeds and nothing was indexed" and "no exception escaped" are both **true of the stub**, so a test asserting only that is green by accident. Each goes genuinely red by binding to the frozen result: assert `IndexOutcome.reason` is the matching `IndexFailureReason` member (`no_provider` / `unreachable` / `dimension_mismatch` / `sidecar_error` — the stub's `reason` is `None`), and for DoD-5/DoD-7 additionally assert the **warning record** naming the entry id and the reason (the stub emits none). DoD-9 (nothing pending after the call) is green at the stub and stays green — awaiting rather than scheduling is structural, and the assertion is a regression lock on it.
- Verified: `app.services.codex_index`, `app.services.codex` and `app.main` all import cleanly; every signature above confirmed by `inspect.signature`; `IndexOutcome` constructs. Full suite after the stubs: **642 passed** — unchanged from the step-005 baseline, i.e. the two new call sites regress nothing.

### Step 007 — frozen interface (2026-07-27)

**The shape decision the plan delegated** (`007.context.md` → "`run_turn` currently takes only
`(context, prompt)`"): the subject fields are threaded through **`prepare_turn` / `TurnContext`**, not
through a new `run_turn` parameter. `run_turn`'s signature is therefore **unchanged**. Reasons: (a)
`resolve_subject` takes `authz.BookAccess`, which only `prepare_turn` holds — the `run_turn` shape
would have needed *two* new carriers (an access and the request fields); (b) `prepare_turn` is by its
own docstring the "everything resolved before the first frame" phase, and subject resolution refuses
nothing, so it adds no pre-stream failure mode; (c) `011`'s `test_chat_turn.py:239`
`run_turn(context, prompt)` helper and its keyword-built `TurnContext` both keep binding untouched.

**`backend/app/models/schemas/chats.py`** — declarative, lands **complete**.

- `SubjectKind = Literal["book-state", "chapters", "chapter", "characters", "locations", "facts", "codex-entry", "variants", "chapter-variants", "chats"]` — new module-level type alias, value-for-value with `frontend/src/work/subject.ts:SubjectKind`. Lives here (not in `services/`) because `models/` may not import `services/` and both the DTO and `services/assistant_runtime.py` bind to it; the runtime imports it from here.
- `class TurnRequest(BaseModel)` — **changed**: `prompt: str | None = None` (unchanged) plus `subject_kind: SubjectKind | None = None`, `subject_id: str | None = None`, `codex_kind: CodexKind | None = None`. All three optional-and-absent, so `{"prompt": "..."}` and `{}` are still complete bodies (DoD-13). `subject_id` is a **string** (wire ids are `str`; `None` for UC-076's blank entry). `codex_kind` is the real `app.models.codex_entry.CodexKind` enum, not a str — `models/schemas/codex.py`'s precedent.

**`backend/app/services/assistant_runtime.py`** — **new** file, the bulk of the step. Module-level imports (the patch targets tests bind to): `from app.db import assistant_modes, codex_entries, mode_tools`, `from app.models.codex_entry import CodexEntry, CodexKind`, `from app.models.schemas.chats import SubjectKind`, `from app.services import authz`. **`services/assistant_config.py` is not imported and no db helper was added** — `012` stays unbuilt and untouched.

Declarative surface — **complete, nothing unimplemented**:

- `BASE_TOOL_NAMES: tuple[str, ...] = ("web_search",)` — new. The no-mode allowlist (`context.md` decision 6). A `tuple`, matching `allowed_tool_names`'s return and binding straight into `resolve_tools(allowed_names: Collection[str] | None)`.
- `@dataclass(frozen=True) class ResolvedSubject` — new, complete — `kind: SubjectKind | None = None`, `entry: CodexEntry | None = None`, `mode_key: str | None = None`. Frozen typed record (`ToolDef` / `ChunkHit` / `IndexOutcome` precedent). Every field defaults to `None` so `NO_SUBJECT` and `resolve_subject`'s two-phase build (resolve, then attach the mode via `dataclasses.replace`) both read plainly. `entry` is the **row** — populated only for an *existing* codex entry; a blank entry carries `kind="codex-entry"` with `entry is None`.
- `NO_SUBJECT: ResolvedSubject = ResolvedSubject()` — new, complete. The shared "this turn has no subject" instance and `TurnContext.subject`'s default.

The four functions — **their mode-bearing bodies are UNIMPLEMENTED**:

- `async def resolve_subject(access: authz.BookAccess, subject_kind: SubjectKind | None = None, subject_id: str | None = None, codex_kind: CodexKind | None = None) -> ResolvedSubject` — new. Skeleton body: `subject_kind is None` returns `NO_SUBJECT` (**preserved** 011 behaviour); every subject-bearing path raises `NotImplementedError`.
- `def determine_mode(subject: ResolvedSubject) -> str | None` — new (raises `NotImplementedError`). **Synchronous and pure** — it reads only the record handed to it, so a test needs no db. Returns one of `db/assistant_modes.py:DEFAULT_MODE_KEYS` or `None`.
- `async def mode_system_prompt(mode_key: str | None) -> str | None` — new. Skeleton body: `mode_key is None` returns `None` (**preserved**); a real key raises `NotImplementedError`.
- `async def allowed_tool_names(mode_key: str | None) -> tuple[str, ...]` — new. Skeleton body: `mode_key is None` returns `BASE_TOOL_NAMES` (**preserved**); a real key raises `NotImplementedError`. Never returns `None` — the turn no longer reaches `resolve_tools`' whole-registry branch.

**`backend/app/services/chat_turn.py`** — the three edits, no restructuring. `run_turn`'s signature, `TurnFrame`, `ThinkSplitter`, `MAX_LOOPS`, `_TURN_FAILURE_EXCEPTIONS` and `build_sampling_options` are untouched.

- `@dataclass(frozen=True) class TurnContext` — **changed**: gains a fourth field `subject: assistant_runtime.ResolvedSubject = assistant_runtime.NO_SUBJECT`. **Defaulted, non-negotiably** — `backend/tests/services/test_chat_turn.py:235` builds the context by keyword and is out of this step's Test-files scope.
- `async def prepare_turn(access: authz.BookAccess, chat_id: str, request: TurnRequest | None = None) -> TurnContext` — **changed** (was `async def prepare_turn(access: authz.BookAccess, chat_id: str) -> TurnContext`). The whole parsed body is passed rather than three loose arguments, so steps 009/010 can widen `TurnRequest` without moving this signature again. Body **implemented, not stubbed**: the four pre-stream refusals are byte-for-byte as they were, then `await assistant_runtime.resolve_subject(access, subject_kind=…, subject_id=…, codex_kind=…)` (all `None` when `request is None`) fills the new field.
- `async def run_turn(context: TurnContext, prompt: str | None) -> AsyncGenerator[TurnFrame, None]` — **signature unchanged**; three statements changed inside it. A new step "1b" between the user-message persist and the compose reads `mode_key = context.subject.mode_key` and awaits `mode_system_prompt(mode_key)` / `allowed_tool_names(mode_key)`; `compose_system_prompt` now also passes `mode=mode_prompt`; `resolve_tools(None)` became `resolve_tools(allowed_names)`. Everything else — the queue, `drive()`, the splitter, persistence, the frame order — is untouched.

- Caller-compile edits (out of Source-files scope): **`backend/app/routes/chats.py:216`** — one line, `chat_turn.prepare_turn(access, chat_id)` → `chat_turn.prepare_turn(access, chat_id, payload)`. `payload` is the already-parsed `TurnRequest` the handler holds; no new path parameter, no new dependency, no logic in the route. That is the whole out-of-scope diff.

Notes for the pipeline:

- **Why three stub branches RETURN instead of raising.** `run_turn` and `prepare_turn` are *changed existing* symbols, and DoD-13 is an explicit backward-compatibility clause: 011's turn tests must pass **unmodified**. The no-subject / no-mode branches of `resolve_subject`, `mode_system_prompt` and `allowed_tool_names` are exactly the pre-013 behaviour those tests exercise (no mode layer; the whole registry, which today *is* `("web_search",)`), so they are preserved rather than stubbed — the step-001 pattern ("the pre-013 path is preserved; any non-default argument raises"). Every genuinely new path raises.
- **Red-gate expectations.** DoD-1, DoD-2, DoD-3, DoD-4, DoD-6 are unambiguously red (`resolve_subject` / `determine_mode` raise for every subject-bearing input). DoD-7, DoD-8, DoD-9, DoD-10, DoD-12 are red (a mode key raises out of `mode_system_prompt` / `allowed_tool_names`; through `run_turn` a `NotImplementedError` is **not** in `_TURN_FAILURE_EXCEPTIONS`, so it escapes the generator rather than becoming an `error` frame). **Three to write carefully:**
  - **DoD-5** — "a book-state / list / chats / **absent** subject resolves to no mode". The *absent* half is **green at the gate** (`resolve_subject(access)` → `NO_SUBJECT`, `mode_key is None`); the three named kinds are red. A test asserting only the absent case is green by accident.
  - **DoD-11** — "with no mode, exactly `BASE_TOOL_NAMES` is allowed". **Green at the gate** by construction, since that is the preserved branch. It is a regression lock on decision 6, not a red item; assert the *set of built tool definitions*, not just that `allowed_tool_names(None) == BASE_TOOL_NAMES`.
  - **DoD-13** — green at the gate and must stay green: 011's `backend/tests/services/test_chat_turn.py` and `backend/tests/routes/test_chat_turn.py` pass **unmodified** after these stubs.
- Verified: `app.main`, `app.services.assistant_runtime` and `app.services.chat_turn` import cleanly; every signature above confirmed by `inspect.signature`; `TurnRequest()` still validates an empty body and round-trips `subject_kind="codex-entry"` / `codex_kind="character"`. Full suite after the stubs: **660 passed** — unchanged from the step-006 baseline.

### Step 008 — frozen interface (2026-07-27)

**`backend/app/services/subagent_delegation.py`** — **new** file, the bulk of the step. Module-level imports (the namespaces tests monkeypatch through): `from app.db import llm_servers as llm_servers_db`, `from app.db import mode_subagents, sub_agents, subagent_tools`, `from app.models.llm_server import LlmServer`, `from app.models.sub_agent import SubAgent`, `from app.services import llm_servers as llm_servers_service`, `from app.services import secrets`, `from app.services.tools import TOOL_REGISTRY, ToolDef`, plus `logger = logging.getLogger(__name__)` (an `app.*` logger — the step-005/007 log-assertion shape). **`services/assistant_config.py` is not imported and no db helper was added.** Client construction goes through `llm_servers_service.create_model_client` (**never** `_create_client`), so the existing `app.services.llm_servers.create_model_client` patch seam that `011`/`004`/`007`'s tests already use is the seam here too.

Declarative surface — **complete, nothing unimplemented**:

- `SUBAGENT_MAX_LOOPS = 3` — new. The **nested** loop bound, deliberately its own constant and deliberately **≠ `chat_turn.MAX_LOOPS` (4)**, so tuning the parent's loop cannot silently change delegation depth (DoD-11).
- `DELEGATION_TOOL_PREFIX = "ask_"` — new. The fixed prefix every derived delegation tool name carries, marking it a delegation rather than a code-defined registry entry. Frozen (value included) so a caller — or a test — can tell the two apart without a lookup and can predict a derived name.
- `@dataclass(frozen=True) class ParentTurn` — new, complete — `server: LlmServer`, `resolved_key: str | None`, `model: str`. **The parent-turn value.** Field order as listed; construct by keyword. The three fields are exactly `llm_servers.create_model_client(server, resolved_key, model)`'s arguments, because that is all they are for: a sub-agent with a **null** `(llm_server_id, model_name)` assignment inherits them (US-113.AC-6). `resolved_key` is the **already `$ENV`-resolved** key (`chat_turn.prepare_turn` resolved it before the stream opened), never a raw `$NAME` ref. Frozen typed record — the `ToolDef` / `ResolvedSubject` / `ChunkHit` precedent.
- `class DelegationArgs(BaseModel)` — new, complete — **one** field: `task: str` (required, with a model-facing `Field(description=…)`). The synthetic tools' `args_schema`. It lives in this module, **not** in `models/schemas/tools.py`, because that module is outside this step's Source files; it is a declarative Pydantic schema either way. Its **class docstring is model-facing** (`llm.pydantic_to_openai_tool` copies it into the JSON schema's `description`), so the engineering rationale sits in a comment above the class instead.

The three functions — **all UNIMPLEMENTED except two preserved branches**:

- `def delegation_tool_name(sub_agent_name: str) -> str` — new (raises `NotImplementedError`). **Synchronous and pure.** The derivation rule, frozen as behaviour the coder implements: lowercase, collapse runs of non-alphanumeric characters, prepend `DELEGATION_TOOL_PREFIX`, keep inside the conventional `^[a-zA-Z0-9_-]{1,64}$` tool-name shape. So `"Continuity Checker"` → `"ask_continuity_checker"`. Public (not `_`-prefixed) precisely so a test can name an expected tool without reading the builder. Deriving rather than storing keeps `SubAgent` unchanged — no column, no codec, no feature-012 coordination — at the cost of collisions, which the builder makes observable (DoD-12 / DoD-13).
- `async def build_delegation_tools(mode_key: str | None, parent: ParentTurn) -> list[ToolDef]` — new. **The synthetic-tool builder**: one `ToolDef` per invokable sub-agent of `mode_key`. Skeleton body: `mode_key is None` returns `[]` and a mode with **zero** `mode_subagent` rows returns `[]` (both **preserved behaviour** — see the notes); a mode with at least one link row raises `NotImplementedError`. Contract on its output, which the coder may not vary: `args_schema` is `DelegationArgs`; `name` is `delegation_tool_name(sub_agent.name)`; `description` **contains the sub-agent's `name` verbatim** (the step file: "the description carries the sub-agent's name so the model can choose sensibly"); `callable` is `functools.partial(run_delegation, sub_agent, parent)`.
- `async def run_delegation(sub_agent: SubAgent, parent: ParentTurn, task: str) -> str` — new (raises `NotImplementedError`). **The delegation callable.** `sub_agent` (the **row**, already loaded by the builder — the `codex_index.index_entry(entry)` precedent) and `parent` come **first and positionally** precisely so `functools.partial(run_delegation, sub_agent, parent)` leaves **`task` as the only free parameter** — which is what the `llm` client's `inspect.signature(func).parameters` validation and `func(**kwargs)` dispatch require, there being no per-request context argument. Verified: `inspect.signature(functools.partial(run_delegation, a, p)).parameters == ['task']`, matching `DelegationArgs`' single field. Its finished form **never raises** — every failure returns a short error string (`web_search`'s contract); the stub raising is deliberate (see the notes).

**`backend/app/services/assistant_runtime.py`** — tool resolution grows its second half. Step 007's `BASE_TOOL_NAMES`, `ResolvedSubject`, `NO_SUBJECT`, `resolve_subject`, `determine_mode`, `mode_system_prompt` and `allowed_tool_names` are **untouched** (confirmed by `inspect.signature`); three imports added (`subagent_delegation`, `tools as tools_service`, `ToolDef`).

- `async def resolve_turn_tools(mode_key: str | None, parent: subagent_delegation.ParentTurn) -> list[ToolDef]` — new, and **implemented, not stubbed**: `tools_service.resolve_tools(await allowed_tool_names(mode_key))` followed by `await subagent_delegation.build_delegation_tools(mode_key, parent)`, returned as one list — **real tools first, synthetic after**. The single place `chat_turn` asks "what tools does this turn have". It adds no behaviour of its own (all of step 008's redness lives in `build_delegation_tools`), and it must not raise for a no-mode or no-links turn, because steps 007's and 011's shipped turn tests drive `run_turn` through it — see the notes.

**`backend/app/services/chat_turn.py`** — the call-site edit only. `MAX_LOOPS`, `_TURN_FAILURE_EXCEPTIONS`, `ThinkSplitter`, `build_sampling_options`, `TurnContext`, `TurnFrame`, `prepare_turn` and `run_turn` **all keep their step-007 signatures** — no symbol moved.

- Added `from app.services import subagent_delegation`.
- Inside `run_turn` step 3: `allowed_names = await assistant_runtime.allowed_tool_names(mode_key)` (step 007's line, now called **inside** `resolve_turn_tools`) is gone; the turn builds `parent_turn = subagent_delegation.ParentTurn(server=server, resolved_key=context.resolved_key, model=chat.model_name or "")` and hands `await assistant_runtime.resolve_turn_tools(mode_key, parent_turn)` — the **combined** real+synthetic list — to `tools_service.build_tool_bindings` in **one** call, so `tools_definitions` and `tools` are built together and can never fail the client's pre-flight on a synthetic name. Nothing else in the module changed; `services/tools.py` is untouched.

- Caller-compile edits (out of Source-files scope): **None.** No signature changed, so nothing outside the three Source files needed adapting.

Notes for the pipeline:

- **Why two branches of the builder RETURN `[]` instead of raising.** Step 007's `backend/tests/services/test_assistant_runtime.py` drives `run_turn` end-to-end with **mode-bearing** subjects (`edit-character` / `edit-fact` / `edit-location`) and asserts a `done` frame plus exact tool maps; 011's turn tests drive it with no mode. All of those seed **no `mode_subagent` rows**. A builder that raised for any mode key — or for a mode with no links — would turn a dozen already-green, out-of-scope tests red *before* the red gate and muddy the verifier's signal (step 005's `## Notes & Issues` lesson). The two returning branches are exactly the pre-step-008 truth: before this step no turn had synthetic tools, and a mode that selected no sub-agent still has none. Everything past a real link row raises.
- **Why `run_delegation`'s stub RAISES even though the finished function must never raise.** Unlike step 006's `index_entry`, nothing shipped calls it — it is reachable only through a synthetic tool that the stubbed builder never creates — so a loud `NotImplementedError` costs no green test and keeps DoD-10 / DoD-14 (the never-raise clauses) from being satisfied by an error string the stub could have returned for free. The never-raise contract is behaviour the coder supplies.
- **Red-gate expectations.**
  - Unambiguously **red**: DoD-1 (no synthetic tool is ever built), DoD-5, DoD-6, DoD-7, DoD-8, DoD-9, DoD-10, DoD-11, DoD-14, DoD-15 — every one of them enters through `build_delegation_tools` with a link row, or through `run_delegation` directly, and both raise. DoD-12 and DoD-13 are red for the same reason (the collision guard lives in the builder), **provided** the test seeds a real `mode_subagent` link — a test that only inspects `delegation_tool_name` would be red on that stub instead, which is weaker but still red.
  - **Green by accident — write these carefully.** **DoD-2** ("a `disabled` sub-agent is excluded even with a stale link row") and **DoD-3** ("a sub-agent not in the mode's set is not built") are *negative* assertions: the stub raises for a mode with links, so a test phrased as "assert the disabled agent's tool is absent" will hit `NotImplementedError` (red, right reason) **only if** it does not swallow it — but phrased as "`build_delegation_tools` returns `[]`" against a mode with **no** links it would be green against nothing. Bind them to a mode that **has** at least one link row and assert the *surviving* tool set, so the exclusion is observed against a non-empty build.
  - **DoD-4** ("with **no** mode, no synthetic delegation tools are built") is **GREEN at the gate** by construction — it is the preserved branch. It is a regression lock, not a red item; make it bite by asserting the full turn's tool maps equal exactly the real `BASE_TOOL_NAMES` selection (no `ask_`-prefixed key), not merely that a list is empty.
- Verified: `app.main`, `app.services.subagent_delegation`, `app.services.assistant_runtime` and `app.services.chat_turn` all import cleanly; every signature above confirmed by `inspect.signature`; `ParentTurn` and `DelegationArgs` construct; `llm.pydantic_to_openai_tool("ask_x", …, DelegationArgs)` produces a one-property `task` schema; `resolve_turn_tools(None, parent)` returns exactly `["web_search"]`. Full suite after the stubs: **694 passed**, unchanged from the pre-step-008 baseline.

### Step 009 — frozen interface (2026-07-27)

**`backend/app/services/tools.py`** — the **first modification** since feature 011. `resolve_tools` is **untouched** (signature and body), and `web_search`'s registry entry is byte-identical. Two imports added: `from app.services.codex_tools import (CodexEntryReadArgs, CodexSearchArgs, bind_codex_read_entry, bind_codex_search)`.

- `@dataclass(frozen=True) class ToolContext` — **new, complete** — **one** field: `book_id: int`. The per-turn value a **bound** tool is closed over. Frozen typed record (the `ToolDef` / `ParentTurn` / `ResolvedSubject` precedent); construct by keyword. `int`, not the wire `str`, because it is an internal value flowing into `db/vector.search(book_id: int, …)` and compared against `CodexEntry.book_id` — it never crosses the wire. **Extended additively by step 010** (the content-pane subject and the frame emitter join it as further fields; anything added there must carry a default so this step's `ToolContext(book_id=…)` construction keeps binding).
- `ToolBinder = Callable[[ToolContext], Callable[..., object]]` — **new** type alias. The `ToolDef.binder` shape: given the turn's context, return the callable to dispatch, whose free parameters are exactly the `args_schema` field names.
- `@dataclass(frozen=True) class ToolDef` — **changed**, additively — now `name: str`, `description: str`, `args_schema: type[BaseModel]`, `callable: Callable[..., object] | None = None`, `binder: ToolBinder | None = None` (was `… callable: Callable[..., object]` required, no `binder`). **Exactly one of `callable` / `binder` is set**: a bound entry has no context-free callable to offer, since a plain callable beside a binder would be one whose signature does not match its `args_schema`. `callable` becoming optional is what lets a bound entry omit it; every existing construction passes `callable=` by keyword (`web_search`'s entry, `subagent_delegation.build_delegation_tools`) and is unaffected, and `TOOL_REGISTRY[0].callable is web_search` still holds.
- `TOOL_REGISTRY: list[ToolDef]` — **changed**: now **three** entries, `web_search` **first and unchanged**, then the two new **bound** ones. Both carry a non-empty model-facing `description` and a `binder`, no `callable`:
  - `codex_search` — `args_schema=CodexSearchArgs`, `binder=bind_codex_search`.
  - `codex_read_entry` — `args_schema=CodexEntryReadArgs`, `binder=bind_codex_read_entry`. (The step file says only "the entry-read tool"; the name is frozen here as `codex_read_entry`, matching its callable, as `web_search` does.)
- `def build_tool_bindings(tools: list[ToolDef], context: ToolContext | None = None) -> tuple[list[dict[str, object]], dict[str, Callable[..., object]]]` — **changed** (was `def build_tool_bindings(tools: list[ToolDef]) -> …`). **`context` defaults to `None`** — non-negotiable, exactly as step 005's `init_vector` parameters did: `subagent_delegation._delegate` and feature 011's `tests/services/test_tools.py` call it with one positional argument, and a required parameter would break them at the skeleton. Resolution rule, in order: a `ToolDef` **with** a binder and **no** context is **skipped and logged** (left out of **both** maps, so the client's pre-flight invariant — every `tools_definitions` name has a `tools` key — is preserved, which is the one contract this step must not touch); a `ToolDef` with a binder **and** a context raises `NotImplementedError` — **this is the new behaviour and it is UNIMPLEMENTED**; a `ToolDef` with a plain `callable` is used **unchanged** (011's path, preserved verbatim); an entry with neither is skipped and logged.

**`backend/app/services/codex_tools.py`** — **new** file. Module-level imports (the namespaces tests monkeypatch through): `from app.db import codex_entries, vector`, `from app.services import embedding`. **`services/codex.py` is deliberately not imported** (it wants a `BookAccess` the tool context does not carry; the capability check is already satisfied upstream by the turn's `book_access` dependency). `from app.services.tools import ToolContext` is a **`TYPE_CHECKING`-only** import with a quoted annotation, because `tools.py` imports *this* module for the registry — the catalogue → tool-module direction `web_search` established — and a runtime import would be a cycle.

Declarative surface — **complete, nothing unimplemented**:

- `DEFAULT_SEARCH_LIMIT = 5`, `MAX_SEARCH_LIMIT = 20` — new. `codex_search`'s default and ceiling. A **bounded-output** concern only; there is **no minimum-score / relevance threshold anywhere in this module** and adding one would close UC-078's open `_TBD:` (challenge C27) by design.
- `class CodexSearchArgs(BaseModel)` — new, complete — **two** fields: `query: str` (required, model-facing `Field(description=…)`) and `limit: int = Field(default=DEFAULT_SEARCH_LIMIT, ge=1, le=MAX_SEARCH_LIMIT, description=…)`. **There is deliberately NO book field** — `retrieval.md`'s hard-filter rule means the model must have no way to name a book (US-085.AC-1). Lives here, not in `models/schemas/tools.py`, because that module is outside this step's Source files (step 008's `DelegationArgs` precedent). Its **class docstring is model-facing** (it reaches the model through `model_json_schema()`), so the engineering rationale sits in a comment above the class.
- `class CodexEntryReadArgs(BaseModel)` — new, complete — **one** field: `entry_id: str` (required, model-facing description). A **wire string** id — the house id rule, and the form `db/vector.py:ChunkHit.source_id` (hence `codex_search`'s output) carries, so a search hit feeds the read tool directly.
- `def bind_codex_search(context: "ToolContext") -> Callable[..., object]` — new, **implemented** — `functools.partial(codex_search, context)`. Verified: `inspect.signature(bind_codex_search(ctx)).parameters == ["query", "limit"]`, exactly `CodexSearchArgs`' fields.
- `def bind_codex_read_entry(context: "ToolContext") -> Callable[..., object]` — new, **implemented** — `functools.partial(codex_read_entry, context)`. Verified: free parameters `["entry_id"]`, exactly `CodexEntryReadArgs`' field. The binders are implemented because they *are* the binding declaration — the "exactly the schema field names are free" property is the contract, not behaviour.

The two callables — **both raise `NotImplementedError`**:

- `async def codex_search(context: "ToolContext", query: str, limit: int = DEFAULT_SEARCH_LIMIT) -> str` — new. `context` comes **first and positionally** precisely so `functools.partial` leaves `query` / `limit` as the only free parameters. Contract the coder fills: embed `query` via `services/embedding.embed_text`; `db/vector.search` with **`context.book_id`** as the hard filter, `kinds={SourceKind.codex_entry}` and `limit`; render nearest-first, one block per hit, **entry id first**, plus kind, name when present and the matched **chunk** text as the snippet. Its finished form **never raises** — no provider, an empty/stale index and a transport failure each return their own informative string, and "nothing found" is a distinct string from an error.
- `async def codex_read_entry(context: "ToolContext", entry_id: str) -> str` — new. Contract: `db/codex_entries.get_by_id`, then return kind / name / body as text; a **malformed**, **unknown**, **other-book** or **archived** id each returns an informative string leaking none of that entry's content. Also never raises.

**`backend/app/services/chat_turn.py`** — the call-site edit only. `MAX_LOOPS`, `_TURN_FAILURE_EXCEPTIONS`, `ThinkSplitter`, `build_sampling_options`, `TurnContext`, `TurnFrame`, `prepare_turn` and `run_turn` **all keep their step-008 signatures** — no symbol moved, no import added.

- Inside `run_turn` step 3, beside the existing `parent_turn`: `tool_context = tools_service.ToolContext(book_id=chat.book_id)`, handed to `tools_service.build_tool_bindings(await assistant_runtime.resolve_turn_tools(mode_key, parent_turn), tool_context)` as the second positional argument. `chat.book_id` is the turn's book, already on the resolved `TurnContext`; no new lookup. Nothing else in the module changed.

- Caller-compile edits (out of Source-files scope): **None.** `build_tool_bindings`' new parameter defaults, so `services/subagent_delegation.py:_delegate`'s one-argument call keeps compiling **and** keeps its meaning — see the note below on what that implies for a sub-agent.

Notes for the pipeline:

- **Two pre-existing feature-011 tests now FAIL and are outside every role's write scope** — recorded in full under `## Notes & Issues` (step 009). They are `tests/services/test_tools.py::test_registry_has_single_web_search_entry__DoD3` (`assert len(TOOL_REGISTRY) == 1`) and `tests/services/test_chat_turn.py::test_system_prompt_and_whole_registry_offered__DoD11` (a null-mode turn offers the *whole* registry). Both assert a fact this step deliberately falsifies; neither can be fixed by the coder (test files) or by this step's test-coder (a different file). **Read that note before running the red gate** — these two reds are not step-009 signal.
- **Why a bound tool with no context is SKIPPED rather than raising.** It is the only reading that keeps 011's context-free `build_tool_bindings(TOOL_REGISTRY)` behaving exactly as it shipped (one definition, one binding, identical key sets — `test_tools.py`'s DoD-4 pair stays green), and it keeps the pre-flight invariant intact. Everything past "a context IS supplied and the tool is bound" raises, which is where step 009's redness lives.
- **Consequence for sub-agents (behavioural, worth a decision later).** `subagent_delegation._delegate` calls `build_tool_bindings` with **no** context, so a sub-agent whose `subagent_tool` rows select `codex_search` / `codex_read_entry` silently loses them from its nested call (skipped and logged). Giving a sub-agent codex access would mean carrying a `ToolContext` on `ParentTurn` — a **step-008 signature change**, and `subagent_delegation.py` is not in this step's Source files. Out of scope here; flagged so it is a decision rather than a discovery.
- **Red-gate expectations.**
  - **DoD-1 … DoD-11** all enter through `codex_search` / `codex_read_entry`, which raise → red.
  - **DoD-12** ("both tools are present in `TOOL_REGISTRY` and are **bound with the turn's context at binding time**") is **split**: the *presence* half is **green by construction** (the registry entries are declarative), and the *binding* half is **red** — `build_tool_bindings(tools, context)` raises `NotImplementedError` for a bound tool. Write it so the binding is actually exercised (resolve a mode that selects them and build the bindings **with** a context), not merely `assert "codex_search" in {t.name for t in TOOL_REGISTRY}`, which would be green against nothing. The clause's second half ("a mode whose `mode_tool` rows do not select them builds neither") is **green by construction** — step 007's gating — and is a regression lock, not a red item.
  - **DoD-13** (`web_search` still binds and dispatches unchanged through the widened `build_tool_bindings`) is **GREEN at the gate** by design — it is the preserved path, and preserving it is this step's whole compatibility claim. Make it bite by passing a **real** `ToolContext` and asserting `bindings["web_search"] is web_search`.
  - Note for a `NotImplementedError`-catching test: it is a subclass of `RuntimeError`, so a turn driven end-to-end through `run_turn` with a codex tool selected surfaces it via `_TURN_FAILURE_EXCEPTIONS`-adjacent paths rather than crashing the test — bind at the `build_tool_bindings` level for an unambiguous red.
- Verified: `app.main`, `app.services.tools`, `app.services.codex_tools` and `app.services.chat_turn` import cleanly (no cycle); every signature above confirmed by `inspect.signature`; `ToolContext(book_id=7)` constructs; both binders' free parameters equal their schema's field names exactly; `llm.pydantic_to_openai_tool` renders all three registry entries (`codex_search` → `query`/`limit`, `codex_read_entry` → `entry_id`); `build_tool_bindings(TOOL_REGISTRY)` with no context still yields exactly `web_search`. Full suite after the stubs: **717 passed, 2 failed** — the two pre-existing tests named above, and no others. (The count is above step 008's 694-passed skeleton snapshot because step 008's own test file landed after it; the pre-step-009 baseline is 719 passed, so this step's stubs cost exactly those two.)

### Step 010 — frozen interface (2026-07-27)

**`backend/app/models/schemas/chats.py`** — declarative, lands **complete** (nothing unimplemented). The four 011 frame payloads, `SubjectKind` and `TurnRequest` are untouched; no import added.

- `CanvasField = Literal["name", "body"]` — **new** module-level type alias, declared beside `CanvasFrame`. The **constrained literal** the step file requires instead of a free string, in one place: it types both the wire frame's `field` and `services/codex_tools.py:WriteCodexDraftArgs.field`, so the model-facing enum and the wire enum cannot drift. (`services/` may import `models/`, so the sharing costs nothing; the reverse would be a layer violation.)
- `class CanvasFrame(BaseModel)` — **new, complete** — `subject_kind: SubjectKind`, `subject_id: str | None`, `field: CanvasField`, `text: str`. Field order as listed.
  - `subject_kind` is the **whole** `SubjectKind` union, not a `Literal["codex-entry"]`: step 013 dispatches the frame to a registered canvas target by `(subjectKind, subjectId)`, and a later chapter canvas must not need a second frame type. This step only ever emits `"codex-entry"`.
  - `subject_id` is **required-but-nullable** (the step-002 `expected_modified_at` discipline): `None` is UC-076's blank entry, which has no row yet, and an *omitted* id must never be silently read as one.
  - The `data:` payload is serialized by the route's existing generic serializer; the event **name** (`"canvas"`) is not part of this model — it is chosen at the emit site (see `codex_tools.py` below).

**`backend/app/services/tools.py`** — widened **additively**. `ToolDef`, `ToolBinder`, `resolve_tools` and `build_tool_bindings` are **untouched** (signatures *and* bodies), and `web_search`'s entry is still byte-identical and still first. Two imports widened (`Awaitable`; the three new `codex_tools` names), one added (`from app.services import authz`), one `TYPE_CHECKING`-only (`ResolvedSubject`).

- `FrameEmitter = Callable[[str, BaseModel], Awaitable[None]]` — **new** type alias. How a bound tool puts a frame on its turn's SSE stream: `await emit_frame(event_name, payload)`.
  **Why `(str, BaseModel)` and not `(TurnFrame,)`** — `services/chat_turn.py` imports this module, so naming its `TurnFrame` envelope here (or *constructing* one inside a tool) would be an import cycle; `chat_turn`'s closure wraps the pair into `TurnFrame(event=…, data=…)` and puts it on the queue. The pair is chosen over a payload-only emitter deliberately: **the tool names its own event**, so `write_codex_draft`'s "exactly one frame whose event is `canvas`" (DoD-1) is observable in a unit test with a recording emitter, not only end-to-end.
- `@dataclass(frozen=True) class ToolContext` — **changed, additively** — now `book_id: int`, `access: authz.BookAccess | None = None`, `subject: "ResolvedSubject | None" = None`, `emit_frame: FrameEmitter | None = None` (was `book_id: int` alone). All three new fields **default**, exactly as step 009 required, so `ToolContext(book_id=…)` still constructs and every step-009 binding behaves identically.
  - **`access` is the one field beyond the step file's two named additions, and it is required by the DoD, not a convenience.** DoD-7 / DoD-8 need the caller's `role` **and** the book's `collaboration_mode` (`context.md` decision 3 — a co-author is refused in a `proposal`-mode book, an owner is not); neither is on `ResolvedSubject`, on `book_id`, or on `TurnContext` before this step. `BookAccess` carries both, is the repo's canonical "who is acting on which book", and is the value this feature's tests already build directly. `book_id` stays the frozen hard filter for step 009's two tools — `run_turn` builds both from the same resolved turn, so they always name the same book.
  - `subject` is typed `ResolvedSubject | None` with a `None` default rather than `NO_SUBJECT`: `assistant_runtime` imports **this** module (`resolve_turn_tools`), so a runtime import of `NO_SUBJECT` would be a cycle. The annotation is quoted and the import is `TYPE_CHECKING`-only — `codex_tools.py`'s existing discipline, the other way round. `None` and `NO_SUBJECT` are the same refusal for this tool ("no subject at all"), so nothing is lost.
- `TOOL_REGISTRY: list[ToolDef]` — **changed**: now **four** entries, `web_search` first and unchanged, the two step-009 codex entries unchanged, then one new **bound** entry:
  - `write_codex_draft` — `args_schema=WriteCodexDraftArgs`, `binder=bind_write_codex_draft`, non-empty model-facing `description`, no `callable`. Mode-gated like every other entry: under step 007's gating a mode with no `mode_tool` row cannot see it, and `BASE_TOOL_NAMES` does not name it (DoD-12, green by construction).

**`backend/app/services/codex_tools.py`** — one new schema, one new callable, one new binder; step 009's `DEFAULT_SEARCH_LIMIT` / `MAX_SEARCH_LIMIT` / `CodexSearchArgs` / `CodexEntryReadArgs` / `codex_search` / `codex_read_entry` / both binders / every private helper are **untouched** (confirmed by `inspect.signature`). One import added: `from app.models.schemas.chats import CanvasField, CanvasFrame` (no cycle — that module imports only pydantic and `app.models.codex_entry`). `CanvasFrame` is imported for the coder's emit site and is referenced only from the docstring at the skeleton.

- `class WriteCodexDraftArgs(BaseModel)` — **new, complete** — **two** fields: `field: CanvasField = Field(description=…)` and `text: str = Field(description=…)`, both required, in that order. Its **class docstring is model-facing** (`llm.pydantic_to_openai_tool` renders it through `model_json_schema()`), so the engineering rationale sits in a comment above the class, as step 008/009 established. **There is deliberately no subject / entry-id field** — the draft always targets `context.subject`, the entry the author actually has open; a subject argument would let the model aim a draft elsewhere and would be a second source of truth beside the resolved turn subject. Verified: the literal renders as a JSON-schema `enum: ["name", "body"]`.
- `async def write_codex_draft(context: "ToolContext", field: CanvasField, text: str) -> str` — **new**, body **raises `NotImplementedError`**. `context` comes **first and positionally** so `functools.partial` leaves exactly `field` / `text` free. The contract the coder fills, and may not vary: validate server-side (a non-codex-entry subject or **no** subject → refused; an archived entry → refused; a **co-author** in a `proposal`-mode book → refused with a reason **naming FEAT-010**; `field="name"` on a **fact** → refused; a **blank** entry — `subject.kind == "codex-entry"` with `subject.entry is None` — is **allowed**); on success emit **exactly one** frame through `context.emit_frame` with event name `"canvas"` and a `CanvasFrame` payload (`subject_id` = `str(entry.id)`, or `None` for the blank entry) and return a **short confirmation string**; emit **no** frame on any refusal; **touch no database at all**; and **never raise** — every refusal, a missing emitter and a failure *inside* the emitter all return a string.
- `def bind_write_codex_draft(context: "ToolContext") -> Callable[..., object]` — **new, implemented** — `functools.partial(write_codex_draft, context)`. Implemented because it *is* the binding declaration (step 009's reasoning). Verified: free parameters `["field", "text"]`, exactly `WriteCodexDraftArgs`' fields.

**`backend/app/services/chat_turn.py`** — one new `TurnContext` field, one carried value, and the emitter wiring. `MAX_LOOPS`, `_TURN_FAILURE_EXCEPTIONS`, `ThinkSplitter`, `build_sampling_options`, `TurnFrame`, `prepare_turn`'s and `run_turn`'s **signatures** all stand unchanged (confirmed by `inspect.signature`); no import added.

- `@dataclass(frozen=True) class TurnContext` — **changed**: gains a fifth field `access: authz.BookAccess | None = None`. **Defaulted, non-negotiably** — `tests/services/test_chat_turn.py:235` and `tests/services/test_codex_tools.py:779` build this record by keyword and are outside this step's Test files. `prepare_turn` fills it with the `access` it already holds (carried, never re-resolved); it is the only path by which the caller's role and the book's collaboration mode can reach `run_turn`, which receives nothing but a `TurnContext`.
- `run_turn` — **wired, not stubbed** (the step-007/008/009 pattern: the call site lands complete and the coder verifies only). `queue: asyncio.Queue[object] = asyncio.Queue()` **moved up** to just before step 3, and `async def emit_frame(event: str, data: BaseModel) -> None: await queue.put(TurnFrame(event=event, data=data))` defined beside it — the move is forced, because the tool context closes over the emitter and is built at step 3. The turn then builds `ToolContext(book_id=chat.book_id, access=context.access, subject=context.subject, emit_frame=emit_frame)` and passes it to `build_tool_bindings` as before, **and** onto `ParentTurn(..., tool_context=tool_context)`. Nothing else moved: `emit`, `on_delta`, `drive()`, the frame loop, the persistence and the frame order are byte-for-byte as they were, and the emitter is the **same** put-onto-the-queue path `thinking` / `delta` use, running inside the same `drive()` task.

**`backend/app/routes/chats.py` — NOT changed, confirmed by reading it.** The serializer at lines 224–229 is `f"event: {frame.event}\ndata: {frame.data.model_dump_json()}\n\n"` — **generic over the event name**, with no vocabulary of frame kinds anywhere in the handler (the four names appear only in its docstring). A `TurnFrame(event="canvas", data=CanvasFrame(...))` is therefore serialized as `event: canvas` with the model's JSON payload, interleaved in queue order with the turn's `delta` frames, and DoD-2 is satisfied with **zero** route edits.

- Caller-compile edits (out of Source-files scope): **`backend/app/services/subagent_delegation.py`** — the carried item (a), **sanctioned and taken**, because it *is* mechanical. Three lines: `ParentTurn` gains a fifth field `tool_context: ToolContext | None = None` (**defaulted**, so every existing `ParentTurn(server=…, resolved_key=…, model=…)` construction — `run_turn`'s and `tests/services/test_subagent_delegation.py`'s — keeps binding **and keeps its exact current meaning**: no context ⇒ bound tools skipped, as today); `_delegate`'s `build_tool_bindings(await _subagent_tools(sub_agent))` gains `parent.tool_context` as its second positional argument; and one import line widened to include `ToolContext` (no cycle — `tools.py` does not import this module). **Reasoning that it is mechanical, not a rewrite:** `ParentTurn` is constructed in exactly one production site (`run_turn`, in this step's Source files), the new field is additive and defaulted, `_delegate`'s call site takes one extra argument with no restructuring, and no behaviour changes for any existing caller — a sub-agent only *gains* a bound tool when a real turn supplies a context **and** its own `subagent_tool` rows select one. This closes step 009's flagged consequence ("a sub-agent whose rows select a codex tool silently loses it") at the place its verifier nominated.

Notes for the pipeline:

- **One pre-existing test now FAILS and is outside every step-010 role's write scope** — `tests/services/test_tools.py::test_registry_has_single_web_search_entry__DoD3`, whose registry pin (`{"web_search", "codex_search", "codex_read_entry"}`) step 009's test-coder set and this step's fourth entry falsifies. Same shape as, and the same recommended resolution as, the step-009 collision recorded under `## Notes & Issues` (option 1: update the assertion in place, keeping the test's intent — the catalogue is pinned, not open-ended). **Read that note before the red gate: `733 passed, 1 failed` is the step-010 baseline** and only other failures carry step-010 information. No other assertion in the repo pins the registry's contents — the six other places derive from it (`assistant_config` catalogue tests, `ALL_TOOL_NAMES` helpers, the `resolve_tools(None)` identity test).
- **Why the stub RAISES even though the finished tool must never raise.** Step 008's `run_delegation` reasoning applies verbatim: nothing shipped can reach `write_codex_draft` — it is reachable only through a `mode_tool` row that no seeded mode has — so a loud `NotImplementedError` costs no green test, and it stops DoD-11 (never raises, including on a queue failure) from being satisfied for free by an error string the stub could have returned. The never-raise contract is behaviour the coder supplies.
- **Facts the coder has to hand for the validation, so none of it needs a new lookup:** the subject kind is `context.subject.kind`; the row (hence `archived`, `kind`, `id`) is `context.subject.entry`; a **blank** entry has `entry is None` and its codex kind is recoverable from `context.subject.mode_key` (`edit-character` / `edit-location` / `edit-fact`), which is what makes DoD-9 + DoD-10's "a blank fact refuses a name" answerable without a row; the role and the collaboration mode are `context.access.role` / `context.access.collaboration_mode`. Nothing else is needed and **nothing may be read from the database** (DoD-3).
- **Red-gate expectations.**
  - Unambiguously **red**: DoD-1, DoD-4, DoD-5, DoD-6, DoD-7, DoD-8, DoD-9, DoD-10, DoD-11 — every one enters `write_codex_draft`, which raises. DoD-2 is red for the same reason (no frame is ever emitted, so no `event: canvas` line reaches the stream), **provided** the route test drives a mocked `llm` client that actually *invokes* the tool callable it was handed; a test that only asserts "the SSE body parses" would be green against nothing.
  - **Green by accident — write these two carefully.** **DoD-3** ("`codex_entries` / `codex_entry_versions` are byte-for-byte unchanged after a turn that invoked the tool") is **true of the stub**, which touches nothing; it only bites if the turn genuinely reached the tool — assert the invocation happened (the raised/returned tool result, or the model's second round) *and* the tables are unchanged. **DoD-12** ("a mode without the `mode_tool` row builds no `write_codex_draft` definition") is **GREEN at the gate** by construction — it is step 007's gating, a regression lock rather than a red item; make it bite by asserting the built definitions/callables of a *selecting* mode contain it and a sibling mode's contain neither it nor a stray `ask_`/codex key.
- Verified: `app.main`, `app.services.tools`, `app.services.codex_tools`, `app.services.chat_turn` and `app.services.subagent_delegation` all import cleanly (no cycle); every signature above confirmed by `inspect.signature`; `ToolContext(book_id=7)` still constructs with the three new fields defaulted; `bind_write_codex_draft(ctx)`'s free parameters equal `WriteCodexDraftArgs`' fields exactly; `llm.pydantic_to_openai_tool` renders all **four** registry entries, the new one as `{field: enum[name, body], text: string}`; `CanvasFrame(subject_kind="codex-entry", subject_id=None, field="body", text=…)` constructs and round-trips as `{"subject_kind":"codex-entry","subject_id":null,"field":"body","text":…}`; `build_tool_bindings(TOOL_REGISTRY, ctx)` yields identical four-name key sets and with **no** context still yields exactly `web_search`. Full suite after the stubs: **733 passed, 1 failed** — the one test named above, and no others (the pre-step-010 baseline is 734 passed).

### Step 011 — frozen interface (2026-07-27)

The feature's **first frontend step**. Five source files, four of them new; nothing outside them was touched. Gate: `cd frontend && npm run build` (= `tsc && vite build`) — **passes**; `cd frontend && npm run test:types` — **passes** (no existing spec is type-broken by these signatures).

**`frontend/src/types/codex.d.ts`** — **new**, hand-written wire DTOs mirroring step 002's `backend/app/models/schemas/codex.py` field-for-field. **Declarations, complete — nothing unimplemented.** Wire-exact `snake_case`; every id `string`; timestamps `ISODateString` (`import type { ISODateString } from "./common"`); no `any`, no runtime validation. **The list envelope `CodexEntryListResponse` is deliberately NOT modelled** — `api/codex.ts` unwraps `{ items }`.

- `export type CodexKind = "character" | "location" | "fact"` — new. The backend enum's **values**, as a union.
- `export interface CreateCodexEntryRequest` — new — `kind: CodexKind`, `name?: string | null`, `body: string`. (`name` is optional because the backend field defaults to `None`; the kind/name rule is server-side and is not modelled client-side.)
- `export interface UpdateCodexEntryRequest` — new — `name?: string | null`, `body: string`, `expected_modified_at: ISODateString | null`. `expected_modified_at` is **required but nullable**, exactly as the backend DTO — an omitted field must not silently pass the staleness check. No `kind` (not updatable).
- `export interface CodexEntryResponse` — new — `id: string`, `book_id: string`, `kind: CodexKind`, `name: string | null`, `body: string`, `archived: boolean`, `author_id: string`, `modified_by: string | null`, `created_at: ISODateString | null`, `modified_at: ISODateString | null`. Ten fields, same order as `CodexEntryResponse` in step 002's block.

**`frontend/src/api/codex.ts`** — **new**. Mirrors `api/chats.ts`: module-level `const BASE = "/api/books"`, string snowflake ids interpolated straight into the path, `signal?: AbortSignal` as the **trailing** argument on every function, list envelope unwrapped here. Namespace-imported (`import * as codexApi from "../../api/codex"`). Wire query params on the list route are exactly **`kind` / `q` / `include_archived`** (step 003's route). **Every body throws** — no `request` import yet; the coder adds it.

- `export async function listCodexEntries(bookId: string, kind: CodexKind, needle?: string, includeArchived?: boolean, signal?: AbortSignal): Promise<CodexEntryResponse[]>` — new. Returns the **plain array**, `.items` unwrapped. `needle` omitted/empty ⇒ no `q`; `includeArchived` omitted ⇒ `false`.
- `export async function getCodexEntry(bookId: string, entryId: string, signal?: AbortSignal): Promise<CodexEntryResponse>` — new.
- `export async function createCodexEntry(bookId: string, body: CreateCodexEntryRequest, signal?: AbortSignal): Promise<CodexEntryResponse>` — new.
- `export async function updateCodexEntry(bookId: string, entryId: string, body: UpdateCodexEntryRequest, signal?: AbortSignal): Promise<CodexEntryResponse>` — new. A stale `expected_modified_at` surfaces as an `ApiError` with `status === 409` (step 012 renders the reconciliation).

**`frontend/src/work/pages/codexListPageState.ts`** — **new**. Observable data + one pure `get` computed; **no effectful methods, no setters** — the two effects are external `(state, args, signal)` functions, per the enforced MobX rules.

- `export class CodexListPageState` — new. Constructor `constructor(kind: CodexKind, initialNeedle: string = "")`, calling `makeAutoObservable(this, { kind: false })`. Members:
  - `readonly kind: CodexKind` — route-supplied, **not user-selectable**: `readonly` and excluded from the MobX annotations, so it can neither be reassigned nor observed. A different kind is a different route and a fresh instance.
  - `entries: CodexEntryResponse[] = []` · `entriesStatus: "idle" | "loading" | "ready" | "error" = "idle"` · `entriesError: string | null = null` — the async trio, inline union as `bookStatePageState.ts` writes it.
  - `needle = ""` — the **committed** search needle: the value the current list was loaded with and the value mirrored into the URL's `q`. Empty string = no filter.
  - `draftNeedle = ""` — the uncommitted needle the search input binds to.
  - Constructor **seeds both** `needle` and `draftNeedle` from `initialNeedle` (the `q` read once from the URL at mount), so a deep-linked filtered list is filtered on its **first** fetch. This seeding is the only non-throwing code in the class.
  - `get isEmpty(): boolean` — new, **throws**. Contract: `true` only when the load completed and matched nothing (⇒ empty state, never an error); `false` while idle/loading, on error, and with ≥1 entry. **No derived data is stored.**
- `export async function loadCodexEntries(state: CodexListPageState, bookId: string, signal?: AbortSignal): Promise<void>` — new, **throws**. The loader and the error-state retry: reads the needle off `state`, calls `listCodexEntries(bookId, state.kind, …)`, drives the trio with `runInAction`, maps an `ApiError` to `entriesError` / `"error"`, returns silently on `signal?.aborted`.
- `export function submitCodexSearch(state: CodexListPageState, bookId: string, signal?: AbortSignal): string` — new, **throws**. **Synchronous by design** and returns **the new query string for the caller to push**: the search-string form **without** a leading `?` — `"q=<encoded needle>"`, or `""` when the needle was cleared, so `setSearchParams(returned)` drops `q` (DoD-4). It commits `draftNeedle` → `needle` and **starts** `loadCodexEntries` for the new needle (one submit ⇒ one fetch); it does not await the load, so the URL write lands immediately, **in the event handler that changed it** — never a `useEffect` watching the query string (`frontend.md`:192).

**`frontend/src/work/pages/CodexListPage.tsx`** — **new**. One `observer` component shared by the three routes.

- `export const CODEX_KIND_LABELS: Record<CodexKind, string>` — new, **complete**: `{ character: "Characters", location: "Locations", fact: "Facts" }`. The navigator's own words; the page's heading is derived from it, which is why the heading is not a prop.
- `export interface CodexListPageProps` — new — **`kind: CodexKind`, and nothing else.** The book id comes from `useParams`, the heading from `CODEX_KIND_LABELS`, the initial needle from the URL's `q`.
- `export const CodexListPage = observer(function CodexListPage({ kind }: CodexListPageProps) { … })` — new, **render body throws**. The frozen render contract the coder fills (recorded here because the test-coder binds to it): `useState(() => new CodexListPageState(kind, searchParams.get("q") ?? ""))` — the query string is read **once**, at mount, to seed the first load; **one** page-level `useEffect` calling `loadCodexEntries(state, bookId, ctrl.signal)` and aborting on unmount; the kind heading; a search input bound to `state.draftNeedle` whose submit handler calls `submitCodexSearch(...)` and pushes the returned string with `setSearchParams(...)`; a "new entry" action navigating to **`/${bookId}/codex/new?kind=${kind}`**; the entries table (name — or a body excerpt for facts, which have none — plus modified-at) whose rows activate to **`/${bookId}/codex/${entry.id}`** (both basename-stripped, `/work` is the router basename); and the loading / error-with-retry / empty states of the trio.

**`frontend/src/work/routes.tsx`** — **changed**: three placeholder elements replaced, one route added, one import added. Nothing else moved.

- `characters` → `element={<CodexListPage key="character" kind="character" />}`; `locations` → `key="location" kind="location"`; `facts` → `key="fact" kind="fact"`. **The explicit `key` is load-bearing**, not decoration: without it React reconciles the same component type across `/characters` → `/locations` (same position in the tree, no key applied by React Router to a nested match) and keeps the previous kind's `CodexListPageState` alive, breaking "page = route = fresh state instance".
- **`<Route path="codex/new" …>` added immediately BEFORE `codex/:id`**, per the step file. Its element is `<SubjectPlaceholderPage heading="New codex entry" owner="013.codex" />` — a **reservation**: step 012 supplies the real element. React Router 7 would rank the static segment above the dynamic one anyway; the order is declared for readability.
- **`codex/:id` is untouched** — still `<CodexEntryItemRoute />` rendering the keyed placeholder until step 012. **`SubjectPlaceholderPage` is not deleted** (chapters / variants / the two item routes still use it). **`components/shell/navItems.ts` was not touched** — the three navigator entries already exist and this feature adds none.
- Caller-compile edits (out of Source-files scope): **None.** No source file outside the five imports any symbol this step added or changed.

Notes for the pipeline:

- **One pre-existing spec is now falsified and is outside every step-011 role's write scope** — three parameterized cases of `frontend/tests/work/subjectRoutes.test.tsx` (feature 010, DoD-5) assert that `/bk-1/characters`, `/bk-1/locations` and `/bk-1/facts` render an empty state naming `013.codex`. Replacing those placeholders is precisely what this step's Interface intent requires, so the three cases cannot survive. Recorded with a suggested resolution under `## Notes & Issues` → "Step 011 (skeleton)". Read it before the red gate. The file's other cases (`/chapters`, `/variants`, `/codex/ce-1`, the `/chats` redirect, the catch-alls) are unaffected. `tests/work/chatsNavigatorEntry.test.tsx` and `tests/work/WorkNavigator.test.tsx` mount the **navigator only**, never `WorkRoutes`, so they never render a codex route element and are unaffected.
- **Why the render body THROWS rather than rendering an empty shell.** A component that renders a plausible-but-empty table would satisfy "an empty state is shown" for free and make DoD-6 green against nothing. Throwing keeps every rendering DoD honestly red; the stub is unreachable in production because the step lands with the coder.
- **Red-gate expectations.** DoD-1 … DoD-8 all enter the component's render, which throws ⇒ **red**. DoD-9 (the api module unwraps `{items}`) is red only if the spec exercises the **real** `api/codex.ts` (mocking `../../src/api/client`, not the codex module) — a spec that mocks `api/codex` cannot observe the unwrap at all; `listCodexEntries` throws, so that route is red. **DoD-10 (every id crossing the boundary is a `string`) is GREEN at the gate and is a compile-time property**, not a runtime one: it is discharged by `types/codex.d.ts` + the four api signatures, which land complete here. The honest way to bite it is `npm run test:types` (a spec that assigns a `number` id must not compile) or an assertion on the argument types the mocked api module received — not a red runtime expectation.
- **Test-mount reminder** (`011.context.md`): any spec mounting `WorkRoutes` or `WorkspaceShell` must also mock `../../src/api/chats` (`listChats` / `listModelOptions` → `[]`) **and** `../../src/api/books` (`getBookDetail`), re-armed in `beforeEach`, or the shell/chat-pane loads throw before the codex route renders.
- Verified: `npm run build` (tsc + vite) clean; `npm run test:types` clean; the five files are the only ones changed (`git status`).

### Step 012 — frozen interface (2026-07-27)

Exactly the three Source files; nothing outside them was touched. Gates: `cd frontend && npm run build` (= `tsc && vite build`) — **passes**; `cd frontend && npm run test:types` — **passes**. `npm test` was deliberately not run (the red gate is the verifier's).

**`frontend/src/work/pages/codexEntryPageState.ts`** — **new**. Observable data + pure `get` computeds; the effects are the five external `(state, args, signal)` functions. Imports at the skeleton are **type-only plus `makeAutoObservable`** — `runInAction`, `api/codex`, `ApiError`, `restoreBuffer` and `resolveEditability` are the coder's to add (step 011's precedent: a stub that imports nothing it does not use keeps `noUnusedLocals` honest).

Declarative surface — **complete, nothing unimplemented**:

- `export type CodexEntryPageMode = "existing" | "blank"` — new. `"blank"` is `/codex/new?kind=…` (UC-076): **no loaded server entry and no buffer base version until the first save**.
- `export type CodexDraftField = "name" | "body"` — new. **Wire-identical to the backend's `CanvasField`** (`models/schemas/chats.py:257`), so step 013 binds a `canvas` frame's `field` to `applyDraft` with no translation.
- `export type ReconciliationSide = "server" | "draft"` — new. The two per-side choices in the reconciliation view; there is no third (no merge).
- `export function parseCodexKind(value: string | null): CodexKind | null` — new, **complete** (a total membership check over the three kinds, backed by a private `CODEX_KINDS`). Narrows the `?kind=` query-param value; the page calls it once at mount inside the state initializer. Declarative — there is no behaviour here to leave red, and nothing routes a DoD through it alone.

`export class CodexEntryPageState` — new. Constructor `constructor(bookId: string, entryId: string | null, initialKind: CodexKind | null = null)`, calling `makeAutoObservable(this, { bookId: false, mode: false, initialKind: false, applyDraft: false })`. **The constructor's seeding is the only non-throwing code in the class.**

- `readonly bookId: string` — the restore-buffer key's first segment.
- `readonly mode: CodexEntryPageMode` — **derived in the constructor** as `entryId === null ? "blank" : "existing"`, so an inconsistent `(mode, entryId)` pair cannot be constructed. Fixed for the instance's life: a blank entry that saves adopts an id but the navigation to `/codex/:id` remounts a fresh `"existing"` page.
- `readonly initialKind: CodexKind | null` — the `?kind=` kind for the blank route; `null` on the existing route.
- `entryId: string | null` — **mutable**: `null` for a blank entry until the first save creates the row and the state adopts the created id. Drives `bufferKey`.
- `entry: CodexEntryResponse | null = null` · `entryStatus: "idle" | "loading" | "ready" | "error" = "idle"` · `entryError: string | null = null` — the load trio, inline union as `bookStatePageState.ts`/`codexListPageState.ts` write it. `entry` stays `null` for a blank entry, which settles at `"ready"` having contacted nothing.
- `saveStatus: "idle" | "saving" | "saved" | "error" = "idle"` — **the separate save status** the Interface intent requires, so a failed save never blanks the editor the author is still looking at.
- `saveError: string | null = null` — the **server's** refusal text (the 403 reason, read out of `ApiError.details`; and any other non-409 failure). **Merged separately from local validation** (`nameError`): a server error never masquerades as a field message and never clears the draft or its buffer.
- `nameDraft = ""` · `bodyDraft = ""` — the two drafts. **Only `bodyDraft` is buffered** — `restoreBuffer.ts`'s `BufferedDraft.draft` is a single string and the body is the content the buffer exists to protect (`012.context.md`). `restoreBuffer.ts` is **not** widened.
- `conflictEntry: CodexEntryResponse | null = null` — the server's current entry (re-fetched after a 409, or the just-loaded entry when a buffer's `baseVersion` no longer matches it), held **beside** the draft.
- `isReconciling = false` — the flag that makes the page render the reconciliation view **instead of** the editor.
- `evictedBufferKeys: string[] = []` — the keys the most recent buffer write had to evict (`WriteResult.status === "saved-after-eviction"`). **Surfacing only** — eviction is already implemented in `restoreBuffer.ts`, and the current item's buffer is never the victim (DoD-13).

Computeds — **every getter throws**:

- `get kind(): CodexKind | null` — the loaded row's kind for an existing entry (authoritative), `initialKind` for a blank one; `null` while an existing entry loads.
- `get requiresName(): boolean` — `true` for `character`/`location`, `false` for a `fact`; **also the render gate for the name field** (a fact shows none — US-078.AC-1 / US-078.AC-2). `false` while the kind is unknown.
- `get isDirty(): boolean` — drafts vs the loaded entry; for a blank entry, whether either draft is non-empty.
- `get nameError(): string | null` — **local** validation only: a message when a character/location's name is blank or a fact carries one; `null` otherwise.
- `get isValid(): boolean` — no local validation message outstanding.
- `get editability(): Editability` — `resolveEditability` over this entry's `LoadedSubject`. `work/subject.ts` is **consumed unchanged**, so an archived entry's reason is its exact wording (`"This codex entry is archived and read-only; restore it to make changes."`) and no new string is written here.
- `get isReadOnly(): boolean` — the archived case.
- `get canSave(): boolean` — not read-only, locally valid, not saving, not reconciling. **Dirtiness deliberately does NOT gate it** (nothing in the DoD requires an edit before a save is offered, and gating on it would make a legitimate no-op save unreachable).
- `get bufferKey(): string | null` — `restoreBufferKey(bookId, "codex-entry", entryId)`, or `null` for a blank entry (no id to key on).
- `get baseVersion(): ISODateString | null` — **the concurrency contract's anchor.** The loaded entry's `modified_at`; it is *both* the buffer's `baseVersion` and the update request's `expected_modified_at`. **Derived from `entry`, not stored** — so adopting a save response is the single assignment `state.entry = saved`, and the next save cannot 409 against a value the client itself produced. `null` for a blank entry and for an entry never edited since creation; the buffer, whose `BufferBaseVersion` admits no null, records `""` in that case.

The one method:

- `readonly applyDraft = (field: CodexDraftField, text: string): void => …` — new, **throws** (via `editCodexDraft`). **The apply-draft entry point, frozen with step 013 as its consumer**: a *bound arrow property*, excluded from `makeAutoObservable`'s annotations, so step 013 registers `state.applyDraft` with the module-level canvas registry **directly** — no `useCallback` (banned), no wrapper, and the page never learns where the text came from. It is a bound adapter, not an effect of its own: it forwards to `editCodexDraft`, which is exactly the path a keystroke takes (draft set → buffer written → dirty), which is what makes the assistant's write and the author's indistinguishable downstream.

External effect functions — **every body throws**:

- `export async function loadCodexEntry(state: CodexEntryPageState, signal?: AbortSignal): Promise<void>` — new. No `bookId`/`entryId` argument: both live on `state` (unlike step 011's list state, this one owns the book id because the buffer key needs it). Contract in the docstring: blank ⇒ contact nothing and settle `"ready"`; existing ⇒ load, seed both drafts, then read the buffer — absent ⇒ server text stands, `baseVersion` **matches** ⇒ restore the buffered body, **mismatch** ⇒ stale buffer: buffered body into `bodyDraft`, loaded entry into `conflictEntry`, `isReconciling = true`, **and no save attempt**.
- `export function editCodexDraft(state: CodexEntryPageState, field: CodexDraftField, text: string): void` — new. **Synchronous and server-free — there is no `signal`**, because nothing reaches the server until Save (US-107.AC-4 / US-088.AC-2 / US-103.AC-3). Sets the field's draft, then for the **body** of an entry that has a key writes the buffer with `state.baseVersion ?? ""` and records a `"saved-after-eviction"` result's keys into `evictedBufferKeys`.
- `export async function saveCodexEntry(state: CodexEntryPageState, signal?: AbortSignal): Promise<string | null>` — new. **Returns the route path to navigate to after a successful CREATE** (`/${bookId}/codex/${id}`, basename-stripped), `null` for an update and for every failure — `submitCodexSearch`'s precedent from step 011: the state stays router-free and the caller does the navigation in the handler that caused it. Contract: blank ⇒ `createCodexEntry` with the `?kind=` kind then adopt (`entry`, `entryId`); existing ⇒ `updateCodexEntry` carrying `expected_modified_at: state.baseVersion` (the **loaded** `modified_at`), then adopt the response and **clear the buffer**; `ApiError.status === 409` ⇒ re-fetch into `conflictEntry` + `isReconciling`, never a merge; `403` ⇒ the server's reason out of `err.details` (the `{reason, message}` object step 003 put in the detail body — branch on **status**, read the reason from **details**, never parse the message) into `saveError`, **draft and buffer left intact**; any other `ApiError` ⇒ `saveError`/`saveStatus = "error"`, else rethrow.
- `export function discardCodexDraft(state: CodexEntryPageState): void` — new. Clears the buffer, resets both drafts to the loaded entry (empty for a blank one), clears `evictedBufferKeys` and `saveError`. Local only.
- `export async function resolveCodexConflict(state: CodexEntryPageState, side: ReconciliationSide, signal?: AbortSignal): Promise<void>` — new. `"server"` ⇒ discard the draft, adopt `conflictEntry` as `entry`, reseed the drafts, clear the buffer, leave the view. `"draft"` ⇒ adopt `conflictEntry` as `entry` **first** (so `baseVersion` is the server's new `modified_at`), keep the drafts, leave the view, then re-save through `saveCodexEntry` — which now succeeds (DoD-8).

**`frontend/src/work/pages/CodexEntryPage.tsx`** — **new**. One `observer` component; **render body throws** (step 011's reasoning: a plausible-but-empty editor would satisfy several rendering DoD items against nothing).

- `export interface CodexEntryPageProps` — new — **`mode: CodexEntryPageMode`, and nothing else.** The book id and entry id come from `useParams`, the blank route's kind from `useSearchParams`. One component for both routes because they share one editor, one draft, one buffer and one reconciliation view.
- `export const CodexEntryPage = observer(function CodexEntryPage({ mode }: CodexEntryPageProps) { … })` — new, **throws**. The frozen render contract (in the file's docstring, recorded because the test-coder binds to it): `useState(() => new CodexEntryPageState(bookId ?? "", mode === "existing" ? (id ?? null) : null, parseCodexKind(searchParams.get("kind"))))` — the query string read **once**, in the initializer, never by an effect watching it (`frontend.md`:192); **one** page-level `useEffect([state])` calling `loadCodexEntry(state, ctrl.signal)` and aborting on unmount (step 013 adds the canvas registration to this same effect); the **reconciliation view** while `state.isReconciling` (`conflictEntry`'s text against `bodyDraft`, per-side buttons calling `resolveCodexConflict(state, "server" | "draft")`); otherwise the editor — the name field bound to `state.nameDraft` rendered only when `state.requiresName`, the body editor bound to `state.bodyDraft`, **both routing every change through `editCodexDraft`** and never assigning a draft directly (so the buffer write can never be skipped); Save gated on `state.canSave` calling `saveCodexEntry(state)` and navigating to a non-null return; Discard calling `discardCodexDraft(state)`; and the four surfaces — `state.nameError` (local) rendered **separately** from `state.saveError` (server), the read-only banner showing `state.editability.readOnlyReason` with Save unavailable when `state.isReadOnly`, the load trio's loading/error states, and an eviction notice naming `state.evictedBufferKeys`.

**`frontend/src/work/routes.tsx`** — **changed**: one import added, two elements repointed. Nothing else moved.

- `CodexEntryItemRoute` (the existing `key={id}` wrapper) now returns `<CodexEntryPage key={id} mode="existing" />` instead of the placeholder. The wrapper and its key rule are unchanged.
- `codex/new` — element changed from step 011's reservation (`<SubjectPlaceholderPage heading="New codex entry" …>`) to `<CodexEntryPage mode="blank" />`. Declaration order (static before dynamic) is unchanged. **No key**: the blank route's kind is a *query* param, and query-param-read-once has exactly the exposure step 011 accepted for the list page's `q` (a hand-edited `?kind=` does not remount). No in-app navigation produces that case — the "New entry" button always arrives from a different route.
- The comment above the codex block was updated to say both routes render the entry page. `SubjectPlaceholderPage` is **still imported and still used** (chapters, variants, the two remaining item routes); `components/shell/navItems.ts` was not touched.
- Caller-compile edits (out of Source-files scope): **None.** No source file outside the three imports any symbol this step added or changed.

Notes for the pipeline:

- **One more pre-existing spec case is now falsified, and step 011 predicted it.** `frontend/tests/work/subjectRoutes.test.tsx`'s `/bk-1/codex/ce-1` case asserts the item route renders a placeholder naming `013.codex`; repointing `/codex/:id` is precisely this step's Interface intent. Recorded with resolutions under `## Notes & Issues` → "Step 012 (skeleton)". Read it before the red gate.
- **Red-gate expectations.** DoD-1 … DoD-13 all enter either the component's render or one of the five external functions, every one of which throws ⇒ **all thirteen are red**. There is no green-at-the-gate item in this step: even DoD-9's read-only reason and DoD-10's fact/name rule route through throwing computeds (`editability`, `requiresName`) that the render never reaches.
- **What the coder may NOT do**: widen `restoreBuffer.ts` to hold a `(name, body)` pair (the buffered draft is the **body**, `012.context.md`), edit `subject.ts` (the archived wording is its, verbatim), or branch a save failure on `ApiError.message` text (branch on `status`, read the reason from `details`).
- Verified: `npm run build` (tsc + vite) clean; `npm run test:types` clean; `git status` shows exactly the three files.

### Step 013 — frozen interface (2026-07-27)

Five of the seven Source files were touched; **`CodexEntryPage.tsx` and `CodexListPage.tsx` were deliberately NOT touched** (see "Why the two pages are untouched" below). Nothing outside the Source list was changed — in particular **`frontend/src/api/sse.ts` is untouched**, and `WorkspaceShell.tsx`, `work/subject.ts` and `work/restoreBuffer.ts` are consumed unchanged. Gates: `cd frontend && npm run build` (= `tsc && vite build`) — **passes**; `cd frontend && npm run test:types` — **passes**. `npm test` was deliberately not run (the red gate is the verifier's).

**`frontend/src/work/contentSubject.ts`** — **new**. Module-tier plain functions beside `restoreBuffer.ts` / `activeChat.ts`: no class, no MobX, no React, no `src/api/` import. Type-only imports (`CanvasField` / `CanvasFrame` from `../types/chats`, `CodexKind` from `../types/codex`, `LoadedSubject` from `./subject`); `restoreBuffer`'s runtime import is the **coder's** to add (step 011/012's precedent — a stub imports nothing it does not use, so `noUnusedLocals` stays honest).

- `export interface ContentSubject extends LoadedSubject` — new, complete — adds exactly one member: `codexKind?: CodexKind | null`.
  - **Why the extension is necessary and is not a widening of `subject.ts`.** The wire needs `codex_kind` (`013.context.md`'s mapping table: "codex kind from the loaded entry" / "from the `/codex/new` query param"), and `LoadedSubject` — which this feature **consumes unchanged** (`context.md`, planner-derived decision) — carries no kind. The registration record therefore carries it beside the subject rather than inside it. `ContentSubject` **is** a `LoadedSubject` structurally, so "the page declares its `LoadedSubject`" still reads true and `resolveEditability(subject)` still accepts one.
- `export type ContentSubjectSource = () => ContentSubject` — new. **How a page declares its subject, and simultaneously the identity token.**
  - **Why a function and not a record — this is the load-bearing decision of the step.** (a) *Correctness*: registration happens in the page's mount/unmount effect, but an existing codex entry's **kind** and **archived** flag are unknown until the load resolves. A record snapshotted at mount would put `codex_kind: null` on every subsequent turn and **DoD-1 could not pass**; a source is read at send time, so it is always current. (b) *The identity guard*: the page's cleanup closure already holds the function reference, so `registerContentSubject` can return **nothing the caller must thread anywhere** (the Interface intent's words) while `unregisterContentSubject` still has a token to guard on (DoD-9).
- `export type CanvasDraftApplier = (field: CanvasField, text: string) => void` — new. **Structurally identical to step 012's `CodexEntryPageState.applyDraft`** (`(field: CodexDraftField, text: string) => void`, `CodexDraftField` ≡ `CanvasField` ≡ `"name" | "body"`), so the page registers `state.applyDraft` **directly** — no `useCallback` (banned), no wrapper.
- `export function registerContentSubject(source: ContentSubjectSource, applyDraft?: CanvasDraftApplier): void` — new, **throws**. Contract: the newest registration wins outright; a registration with **no** `applyDraft` (the three list pages) is a legitimate subject with no canvas target.
- `export function unregisterContentSubject(source: ContentSubjectSource): void` — new, **throws**. Contract: clears **only** when the live registration's `source` is `===` this one; a late unmount from a page that has already been superseded is a **no-op** (DoD-9).
- `export function currentContentSubject(): ContentSubject | null` — new, **throws**. Contract: invoke the registered source and return its result, or `null` when nothing is registered. This is what `ChatPaneState` calls while composing a turn.
- `export function dispatchCanvasFrame(bookId: string, frame: CanvasFrame): void` — new, **throws**. Contract: a registered target **with** an apply-draft callback whose subject kind **and** id both match (`frame.subject_id` compared against the registered `entityId ?? null`, so a blank entry matches null-to-null) receives `(frame.field, frame.text)`; **otherwise** the text goes to the restore buffer at `restoreBufferKey(bookId, "codex-entry", frame.subject_id)`; a frame for a **blank** entry (`subject_id === null`) with no matching target is **dropped**. Never throws into the SSE handler once implemented.

**`frontend/src/types/chats.d.ts`** — **changed, additively**: five new declarations, one type-only import added (`CodexKind` from `./codex`). The seven pre-existing interfaces are untouched. **Declarative — complete, nothing unimplemented.** Wire-exact `snake_case`, ids `string`, no `any`, no runtime validation, no list envelope.

- `export type SubjectKind` — new — the backend `SubjectKind` literal union's **ten members in the backend's order** (`"book-state" | "chapters" | "chapter" | "characters" | "locations" | "facts" | "codex-entry" | "variants" | "chapter-variants" | "chats"`). Declared here rather than imported from `work/subject.ts`: `src/types/` models the **wire** and must not depend on an entry's domain modules. It is structurally identical to `work/subject.ts:SubjectKind`, so the two are interchangeable and a member added to one alone stops compiling at the mapping site.
- `export interface TurnSubject` — new — `subject_kind: SubjectKind`, `subject_id: string | null`, `codex_kind: CodexKind | null`. The three fields **supplied together** by `streamChatTurn`'s caller. Fields are required-but-nullable inside an **optional** parameter, which is what makes "all three absent" (nothing registered) and "kind only, no id" (a list) two distinct, expressible states.
- `export interface TurnRequest` — new — `prompt: string | null`, `subject_kind?: SubjectKind | null`, `subject_id?: string | null`, `codex_kind?: CodexKind | null`. Mirrors backend `TurnRequest` (step 007). The repo's **first** modelled turn body — `011.chat-panel` built `{ prompt }` inline. All three subject fields optional, so `{ prompt }` is still a complete request (DoD-4).
- `export type CanvasField = "name" | "body"` — new — wire-exact with the backend's `CanvasField`, and identical to `codexEntryPageState.ts:CodexDraftField`.
- `export interface CanvasFrame` — new — `subject_kind: SubjectKind`, `subject_id: string | null`, `field: CanvasField`, `text: string`. **Wire-exact with step 010's frozen backend `CanvasFrame`**, field for field and in the same order, including `subject_id` **required-but-nullable** (`null` is UC-076's blank entry; an omitted id must never be read as one).

**`frontend/src/api/chats.ts`** — **changed**: one handler added, one parameter added, one body variable. The five other functions, `BASE`, `frameText` and the `refreshAuthToken()`-then-`streamPost` shape are untouched.

- `export interface TurnStreamHandlers` — **changed, additively** — gains `onCanvas?: (frame: CanvasFrame) => void`. **OPTIONAL, non-negotiably**: `frontend/tests/work/chatStreaming.test.ts:355` builds a four-handler object literal for the real `streamChatTurn` and is outside this step's Test files, so a required fifth member would break `npm run test:types` on a file no role here may edit. A test-coder firing a canvas frame through `tests/support/sseFixture.ts` reaches it as `fixture.last().handlers.onCanvas?.(frame)`.
- `export async function streamChatTurn(bookId: string, chatId: string, prompt: string | null, handlers: TurnStreamHandlers, subject?: TurnSubject): Promise<AbortController>` — **changed** (was `(bookId, chatId, prompt, handlers)`). `subject` is the **trailing** argument and **no `signal` parameter was added** — `streamPost` still owns and returns the `AbortController`, the one sanctioned break of the trailing-`signal` convention, and it is preserved exactly.
- **Wired, not stubbed (one line):** the posted body is now `const body: TurnRequest = { prompt, ...subject }`. Landed complete because `noUnusedParameters` is on — an unused `subject` would fail the build — and because a spread of `undefined` yields exactly `{ prompt }`, so DoD-4's "no subject fields at all" holds by construction rather than by a branch. **The red still lives at the caller**: `chatPaneState` does not yet read the registry, so DoD-1/2/3 are red.
- **NOT wired (the coder's):** the `canvas` branch inside `streamPost`'s `onEvent` callback and its payload narrowing. `onEvent` still routes only `thinking` / `delta`, which is what keeps **DoD-11 red**. `api/sse.ts` is **not** in the Source list, was **not** opened for edit, and needs none — its `else { handlers.onEvent?.(eventType, parsed) }` branch is the path `canvas` takes.

**`frontend/src/work/components/chat/chatPaneState.ts`** — **changed**: one import, one handler entry, one docstring. **No signature moved, no field added** — `ChatPaneState` still has no subject field, and `sendChatTurn(state, bookId, text)` / `retryChatTurn(state, bookId)` / `stopChatTurn(state)` are unchanged, so `ChatPane.tsx` and `WorkspaceShell.tsx` need nothing.

- `turnStreamHandlers` (private) gains `onCanvas: (frame) => { dispatchCanvasFrame(bookId, frame); }`, contextually typed off the declared `chatsApi.TurnStreamHandlers` return type. **Wired, not stubbed**, and safe: a canvas frame is the only thing that reaches it, so no pre-existing 011 spec touches this path, while **DoD-5 … DoD-8 all enter `dispatchCanvasFrame`, which throws** ⇒ honestly red.
- **NOT wired (the coder's, and deliberately so):** `sendChatTurn` / `retryChatTurn` do **not** yet call `currentContentSubject()` nor pass a `subject` to `streamChatTurn`. Landing that call at the skeleton would throw inside every existing 011 turn test (the registry stub throws), turning a whole shipped suite red for no red-gate information. The coder adds the read **at send time** in both functions plus the private `ContentSubject` → `TurnSubject` mapper (`013.context.md`'s table); the mapper is **not** frozen — it has no external consumer.

**`frontend/src/work/pages/codexEntryPageState.ts`** — **changed**: one type-only import, one computed. Every step-012 symbol — the four exported types, `parseCodexKind`, all thirteen computeds, `applyDraft` and the five external effect functions — is **untouched**.

- `get contentSubject(): ContentSubject` — **new, throws**. The value the page's registered source returns. Contract: `kind: "codex-entry"` always; `entityId` the entry's id and **absent** for a blank entry (which is what puts a null `subject_id` on the wire, UC-076); `codexArchived` from the loaded row; `codexKind` from `this.kind` (the loaded row's for an existing entry, the `?kind=` param's for a blank one). It lives on the state, not in the `.tsx`, because it derives from loaded observable state and because the page must stay dumb.
- **The apply-draft entry point needed no change**: step 012 already froze `readonly applyDraft = (field: CodexDraftField, text: string): void` as a bound arrow property excluded from `makeAutoObservable`, explicitly "frozen with step 013 as its consumer". It forwards to `editCodexDraft` — the exact path a keystroke takes — and step 012's verifier confirmed that. The page registers `state.applyDraft` **as-is**.

**Why the two pages are untouched.** `CodexEntryPage.tsx` and `CodexListPage.tsx` change **behaviourally only** — each adds a `registerContentSubject(...)` / `unregisterContentSubject(...)` pair inside its **existing** page-level `useEffect` — and add **no** exported symbol, prop or signature. Landing those calls against the throwing registry stub would make **every** step-011/012 page spec fail at mount (an effect that throws propagates through React Testing Library's render), destroying the red gate's signal for this step's own tests. The frozen contract the coder implements, and the test-coder may bind to by mounting:

- `CodexEntryPage.tsx` — in the existing `useEffect([state])`, beside `loadCodexEntry`: `registerContentSubject(source, state.applyDraft)` where `const source = () => state.contentSubject`, and `unregisterContentSubject(source)` in the same cleanup that aborts the load. One effect, mount/unmount only.
- `CodexListPage.tsx` — same effect, `registerContentSubject(() => ({ kind: <the list's subject kind> }))` with **no** callback and **no** `entityId`, unregistered by identity on cleanup. The kind mapping is `character → "characters"`, `location → "locations"`, `fact → "facts"` (`work/subject.ts:SubjectKind`'s plural members); it is a private constant of the page, not a frozen export, because nothing outside the file needs it.

- Caller-compile edits (out of Source-files scope): **None.** `streamChatTurn`'s new parameter is optional and `onCanvas` is optional, so `ChatPane.tsx`, `WorkspaceShell.tsx`, `tests/support/sseFixture.ts` and `tests/work/chatStreaming.test.ts` all keep compiling untouched — verified by `npm run test:types`.

Notes for the pipeline:

- **No pre-existing spec is falsified by this step** — the first step in this feature's frontend arc for which that is true. `git status` shows exactly the five files above.
- **Red-gate expectations.**
  - Unambiguously **red**: **DoD-1 / DoD-2 / DoD-3** (the pane does not read the registry, so no subject field is posted), **DoD-5 / DoD-6 / DoD-7 / DoD-8** (every one enters `dispatchCanvasFrame`, which throws), **DoD-9** (nothing registers; `currentContentSubject` throws), **DoD-11** (`streamChatTurn` does not route `canvas` out of `onEvent`, so `onCanvas` is never called).
  - **Green at the gate, by construction — write these two carefully.** **DoD-4** ("nothing registered ⇒ no subject fields and the turn still runs") is `011.chat-panel`'s shipped behaviour, which this step must not break; it is a regression lock, not a red item. Make it bite by asserting the posted body's **key set** is exactly `["prompt"]` (a spread of `undefined` adds no keys) *and* that the turn completes. **DoD-10** (subject and active chat are independent) is likewise inherited: `activeChat.ts` and the registry share no state at all, and `ChatPaneState` gained no field. Make it bite by asserting both directions over a real switch, not by asserting the absence of a field.
  - **A canvas frame can only be fired through the api seam** (`fixture.last().handlers.onCanvas?.(frame)`, or the real `streamChatTurn` with a mocked `sse.streamPost` calling `onEvent("canvas", payload)`). The latter is DoD-11's own shape and is the only one that proves `sse.ts` is unmodified.
- **What the coder may NOT do**: edit `frontend/src/api/sse.ts` (not in scope; the generic branch is the path), add a `signal` parameter to `streamChatTurn`, give `ChatPaneState` a subject field or store the subject on it (it is read at send time, every time), widen `restoreBuffer.ts`, edit `work/subject.ts`, add a second `useEffect` to either page, or make the registry reactive (plain functions, per `frontend-workspace.md`).
- **Two behaviours the DoD leaves open and the coder must settle** (both inside `dispatchCanvasFrame`, neither a frozen signature): the buffer fallback's `baseVersion` — the dispatcher has no `modified_at` to hand, and `013.context.md` explicitly accepts that a stale one routes the author into step 012's reconciliation view, which surfaces the buffered body either way; and whether a `field: "name"` frame with no registered target is buffered at all — `restoreBuffer.ts`'s `BufferedDraft.draft` is a single string and `012.context.md` settled that **the buffered draft is the body**.
- Verified: `npm run build` (tsc + vite) clean; `npm run test:types` clean; `git status` shows exactly the five files this block names.

## Tests

### Step 001 — tests (2026-07-27)

- `backend/tests/db/test_codex_entries.py` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5, DoD-6 — the
  widened `list_by_book` (kind filter, archived exclusion by default, case-insensitive `name`-or-`body`
  needle incl. a null-named fact matched on body, empty/absent needle not narrowing, and the explicit
  name-ascending / nulls-last / then-id deterministic order) plus `update` persisting every changed
  field with the returned row agreeing with an independent re-read.
- `backend/tests/db/test_codex_entry_versions.py` — covers DoD-7, DoD-8, DoD-9 — `next_generation`
  returning `1` with no version rows and highest+1 otherwise (insertion order irrelevant, per-entry
  scoped), and `list_by_entry` returning only that entry's rows in ascending `generation` order.
- `backend/tests/services/test_authz_codex.py` — covers DoD-10, DoD-11, DoD-12 — `browse_codex` and
  `edit_codex_entry` granted to `owner`/`co_author` and raising `BookAuthorizationError` for
  `reader`/`none`, plus a regression guard re-asserting all seven pre-existing capabilities × four
  roles. `BookAccess` built directly; no DB, no HTTP.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓

### Step 002 — tests (2026-07-27)

- `backend/tests/services/test_codex.py` — covers DoD-1 … DoD-17 — the whole codex service contract:
  the kind/name rule (character/location require a non-blank name, whitespace-only counts as absent,
  a fact refuses one and stores null, refusals write nothing); the collaboration-mode rule (free mode
  applies owner *and* co-author create/edit immediately; proposal mode refuses a **co-author's**
  create and edit with `proposal_mode_unsupported` whose message contains "FEAT-010", leaving the
  entry untouched, while the owner's writes still apply); version-row ordering (exactly one
  `CodexEntryVersion` per edit carrying the entry's **prior** name/body/kind, none on create, the
  second edit capturing the first edit's content, generations 1/2/3 across three edits);
  `modified_by` = editor with `author_id` pinned to the original creator; optimistic concurrency
  (a shifted, a null-after-an-edit and a superseded `expected_modified_at` each raise
  `stale_modified_at` with no version row and the entry unchanged); the archived refusal; the list
  envelope's kind / needle (name-or-body, case-insensitive, null-named fact matched on body) /
  include-archived filters with book scoping and `str` ids throughout; another book's entry and an
  unknown id raising `entry_not_found` on get and update; and `reader` / `none` raising
  `BookAuthorizationError` on all four of create / list / get / update with nothing reaching the db.
  Rows seeded through `db/{users,books,codex_entries,codex_entry_versions}`; `BookAccess` built
  directly (frozen dataclass) with the acting `User` row passed on the write paths. No HTTP, no
  network.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓, DoD-14 ✓, DoD-15 ✓, DoD-16 ✓, DoD-17 ✓

### Step 003 — tests (2026-07-27)

- `backend/tests/routes/test_codex.py` — covers DoD-1 … DoD-14 — the codex HTTP surface end to end
  through the real app (`http_client`, real JWTs, no network): `POST` → **201** + a
  `CodexEntryResponse`-validating body with `str` ids; the kind/name refusals (`fact` + name →
  400 `name-not-allowed`; `character` with an omitted **and** a whitespace-only name → 400
  `name-required`); the list route's three wire query params (`kind` narrowing to one kind and
  omission returning all three, `q` matching name **or** body case-insensitively incl. a null-named
  fact matched on body and a no-match empty list, `include_archived` excluding archived by default
  and including them when set); `GET` one plus **404 `entry-not-found`** for an unknown id and for
  another book's entry; `PUT` with the current `modified_at` applying the edit and returning a
  **strictly later** `modified_at` (re-read confirms); a stale `modified_at` → **409
  `stale-modified-at`** with the entry's name/body/`modified_at` unchanged on re-read; an archived
  entry → **400 `entry-archived`**; proposal mode refusing a co-author's `POST` and `PUT` with
  **403 `proposal-mode-unsupported`** (entry unchanged) while the owner's create and edit still
  apply; a non-member of a private book getting **404** from all four routes (the
  `test_chats.py:test_non_member_gets_404_from_every_route__DoD9` shape); a logged-in reader of a
  **public** book getting **403** from all four routes with a plain-string (authz) detail rather
  than the codex reason object; and an unauthenticated caller getting **401** from all four.
  Archived rows are seeded through `db/codex_entries` (this feature exposes no archive route).
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓, DoD-14 ✓

### Step 004 — tests (2026-07-27)

- `backend/tests/services/test_embedding.py` — covers DoD-1 … DoD-11 — the embedding service
  contract with **no network**: the designated-server lookup
  (`app.db.llm_servers.get_embedding_server`) and the client factory
  (`app.services.llm_servers.create_model_client`) are monkeypatched, the factory returning an
  async-context-manager double whose `embed` / `embed_batch` are scripted and whose
  `__aenter__` / `__aexit__` are observable; `$ENV` resolution is driven through real
  `monkeypatch.setenv` / `delenv` rather than mocked. Asserted: no designated row raises
  `no-provider` with the factory never called; an empty / whitespace-only / null `embedding_model`
  is also `no-provider`; `is_available()` is false in both those cases and true for a full
  designation, never constructing or contacting a client; a `$VAR` api key reaches client
  construction **resolved** (raw `$NAME` never does) and the client is bound to the designated
  `embedding_model`; an **unset** `$VAR` surfaces as `unreachable`, not a raw `LlmServerError`;
  `aiohttp.ClientError`, `aiohttp.ClientConnectionError`, `LLMError`, `ValueError` and
  `RuntimeError` from the client each surface as `unreachable`; a three-text call returns one
  vector per text in input order with the texts reaching the client unreordered; an empty input
  returns `[]` with no client constructed and no call made; `__aexit__` runs on both the success
  and the raising path; `probe_dimension()` returns the returned vector's length for two different
  mocked lengths (3 and 1536); and `check_dimension` passes a uniform batch (returns `None`) while
  raising `dimension-mismatch` when the only / a middle / a trailing vector differs.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 [manual/live, no test]

### Step 005 — tests (2026-07-27)

- `backend/tests/db/test_vector.py` — covers DoD-1 … DoD-14 — the sidecar exercised **for real**
  against a per-test `tmp_path` LanceDB dir with only the **embedder** mocked (deterministic
  `embed_batch` / `probe_dimension` doubles injected through `init_vector`; fixed orthogonal 4-dim
  vectors so nearest-neighbour order is metric-independent). Asserted: the table is created at the
  **probed** dimension, with probes of 4 **and** 8 producing differently-dimensioned tables and
  `get_table_dimension()` `None` before creation (DoD-1); `upsert_chunks` writes one row per chunk
  with `chunk_index` 0,1,2 in the supplied order, `source_id` a **string**, `source_kind`
  `codex_entry`, and another book seeing none of it (DoD-2); a re-upsert with **one** chunk after
  three leaves exactly one row and none of the old texts (DoD-3); `delete_by_source` leaves the
  sibling source's rows intact (DoD-4); `delete_by_book` empties one book and leaves the other
  (DoD-5); a foreign chunk placed **exactly on** the query vector — proven nearest by searching its
  own book — is never returned to the other book (DoD-6); hits carry `source_kind` / `source_id` /
  `chunk_index` / `text` / numeric `score`, `kinds` binds as a set **and** a list, `limit` is
  honoured (2 of 5), and the exact-match chunk comes first (DoD-7); the chunker yields one chunk
  beginning with the entry's `name` for a fitting character **and** location body (DoD-8), the bare
  body for a null-named `fact` (DoD-9), and splits a 20-paragraph body into >1 chunk each within
  `CHUNK_SIZE_CHARS`, cutting only on paragraph boundaries (no paragraph split or lost) with an
  adjacent-chunk overlap bounded by `CHUNK_OVERLAP_CHARS` ± the longest paragraph — asserted against
  **the constants**, not 1200/200 (DoD-10); `VECTOR_SOURCE_REGISTRY` holds exactly one entry read
  **by name** (`source_kind` `codex_entry`, `model_class` `CodexEntry`) whose `row_selector` returns
  the two non-archived entries and never offers the archived one to the `chunker` (DoD-11);
  `rebuild_index` drops a pre-existing unrelated row, indexes three short entries while skipping an
  archived one, returns **3**, and the hits' `source_id`s are the three entry snowflakes as strings
  (DoD-12); an empty codex returns **0** and leaves a usable empty table (dimension 6 reported, a
  search answers `[]`) (DoD-13); and `run_vector_rebuild()` **swallows and logs** both the
  un-injected failure (`rebuild_index` raising `VectorIndexError` directly) and a raising injected
  embedder, returning `None` while a record is emitted from an `app.*` logger (DoD-14).
- `backend/tests/test_data_domain_codex.py` — covers DoD-15 — the feature-008 deferral guard
  `test_codex_not_registered_as_vector_source__DoD5` is **replaced** by its inverse,
  `test_codex_registered_as_vector_source__DoD15`: exactly one registry entry, fields read **by
  name** (`source_kind == "codex_entry"`, `model_class is CodexEntry`), `CodexEntryVersion` not a
  source. The rest of that file's coverage is untouched (only its docstring's DoD-5 lines were
  re-worded to match).
- `backend/tests/services/test_db_admin_rebuild.py` — **granted scope extension** — covers DoD-15's
  sibling guard and the `VectorIndexError` decision: `test_vector_source_registry_is_empty__DoD5_D6`
  becomes `test_vector_source_registry_holds_codex_entry__DoD5_D6` (inverse assertion, fields by
  name), and `test_rebuild_valid_designation_returns_zero__DoD1_US020_AC1` /
  `test_rebuild_twice_is_idempotent__DoD2_US020_AC1` now inject deterministic doubles through
  `init_vector` and take the `db` fixture (an **empty** codex) — their assertions about `db_admin`
  (`0`, and `0` twice) are unchanged. The other three tests in that file are untouched.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓, DoD-14 ✓, DoD-15 ✓, DoD-16 [manual/live, no test]

### Step 006 — tests (2026-07-27)

- `backend/tests/services/test_codex_index.py` — covers DoD-1 … DoD-10 — incremental index
  maintenance with **only the model call faked**: `app.services.embedding`'s `embed_batch` /
  `is_available` are monkeypatched while LanceDB runs **for real** against a per-test `tmp_path`
  vector dir, so every "nothing was inserted" claim is asserted against the sidecar's actual
  contents. Asserted: a create through `codex_service.create_entry` lands the entry's chunks under
  `SourceKind.codex_entry` with a **stringified** `source_id` and this book only (another book's
  search is empty), the outcome being `indexed` with a matching `chunk_count` (DoD-1); an edit that
  shortens a >`CHUNK_SIZE_CHARS` body to one line leaves **exactly one** chunk and none of the 20
  original paragraphs anywhere in the index (DoD-2); an `index_entry` double asserts from **inside**
  the call that the entry is already readable from the db with its new name/body on both the create
  and the update path (DoD-3); with **no designated embedding server at all** (the real embedding
  service, nothing mocked) create *and* update return their DTOs, the row really holds the edit, no
  chunk table is ever created, and a direct `index_entry` reports `failed` / `no_provider` /
  `chunk_count == 0` (DoD-4); an `EmbeddingError(unreachable)` leaves the save successful and
  produces `failed` / `unreachable` plus a **WARNING record from an `app.*` logger carrying the entry
  id and the reason** (DoD-5); vectors of twice the live table's dimension are **refused** — the save
  succeeds, `get_table_dimension()` still reports the original dimension, the offending entry has no
  chunks, the healthy entry's chunks are the only rows present, and the outcome is `failed` /
  `dimension_mismatch` with a warning (DoD-6); a raising `vector.upsert_chunks`
  (`VectorIndexError`), a raising `vector.get_table_dimension` (`RuntimeError`) and a raising
  `vector.delete_by_source` (`OSError`) each surface as `failed` / `sidecar_error`, logged with the
  entry id and reason, with the codex save still returning its DTO (DoD-7); an archived entry's
  previously indexed chunks are **dropped** (`status=dropped`, `chunk_count=0`) with the embedder
  never called again, and `drop_entry` removes only that entry's chunks while a second drop is still
  a success (DoD-8); the embedder call count is already 1 (then 2) at the instant
  `create_entry` / `update_entry` return, no `asyncio` task is left pending, and the edited text is
  already searchable (DoD-9); and a parametrized never-raise sweep over all four failure modes plus
  `drop_entry` and a service-level create+update pass, each asserting the **specific**
  `IndexFailureReason` rather than the absence of an exception (DoD-10).
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 [manual/live, no test]

### Step 007 — tests (2026-07-27)

- `backend/tests/services/test_assistant_runtime.py` — covers DoD-1 … DoD-13 — the FEAT-020 mode
  runtime with **no network** (011's `create_model_client` seam replaced by a fake async-context
  client recording `system` / `tools_definitions` / `tools`), rows seeded through
  `db/{users,books,codex_entries,llm_servers,chats,assistant_modes,mode_tools}` against the real
  `db` fixture, `BookAccess` and `TurnContext` (with its new `subject` field) built directly.
  Asserted: the three codex kinds resolving `edit-character` / `edit-location` / `edit-fact` through
  `resolve_subject` **and** the pure `determine_mode` (DoD-1); a blank entry (`subject_id=None`)
  taking its mode from the request's `codex_kind` with `entry is None` (DoD-2); an existing entry's
  **row** kind winning over a deliberately conflicting request `codex_kind`, all three ways round
  (DoD-3); another book's entry resolving to `kind is None` / `entry is None` / `mode_key is None` —
  the foreign row **never loaded**, not merely mode-less (DoD-4); book-state, all six list kinds and
  the chats subject each resolving to no mode, plus the absent subject and `NO_SUBJECT` (DoD-5); a
  chapter subject resolving to no mode in this feature (DoD-6); the mode's `system_prompt` reaching
  the composer as its **mode** layer, with base < mode < book by index and the whole composed string
  equal to `compose_system_prompt(base=…, mode=…, book=…)` (DoD-7); a null / empty / whitespace-only
  / newline-tab `system_prompt` yielding `mode_system_prompt(...) is None` and a composed prompt
  **exactly equal** to the no-mode composition — no header, no blank block — plus a missing row and
  an absent key both yielding none (DoD-8); with the registry widened by a second `ToolDef` (as step
  009 will), a mode selecting only `web_search` offering exactly that in **both** the callable map
  and the definitions while a sibling mode's `note_tool` selection leaks into neither (DoD-9); a mode
  with zero `mode_tool` rows offering an empty map and empty definitions while another mode has
  selections (DoD-10); with no mode, the built tool map and definitions being **set-equal** to
  `BASE_TOOL_NAMES` against the widened registry — `web_search` present, `note_tool` absent — on both
  the chats and the book-state subject (DoD-11); an unknown `mode_tool` name staying in the allowlist
  but skipped from the bindings, a WARNING record from an `app.*` logger naming it, and the turn
  still reaching `done` with the remaining tool (DoD-12); and backward compatibility — `TurnRequest`
  validating `{}` and `{"prompt": …}` with all three subject fields absent, `prepare_turn` with and
  without a request yielding a subject-less context, and a subject-less turn composing base+book with
  no mode layer, offering `BASE_TOOL_NAMES`, streaming and persisting the reply, ending in one `done`
  (DoD-13). `backend/tests/services/test_chat_turn.py` and `backend/tests/routes/test_chat_turn.py`
  are **untouched** — they are DoD-13's regression evidence.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓

### Step 008 — tests (2026-07-27)

- `backend/tests/services/test_subagent_delegation.py` — covers DoD-1 … DoD-15 — sub-agent delegation
  as synthetic tools, with **no network**: the frozen construction seam
  `app.services.llm_servers.create_model_client` is monkeypatched with a recording factory that
  captures every `(server, resolved_key, model)` triple and hands back a **fresh** fake
  async-context-manager client per call, counting `__aenter__` / `__aexit__` and recording the nested
  `chat_with_tools` kwargs (`system` / `tools_definitions` / `tools` / `max_loops`). Rows are seeded
  through `db/{users,books,llm_servers,chats,assistant_modes,mode_tools,sub_agents,mode_subagents,subagent_tools}`
  against the real `db` fixture; `ParentTurn` and `TurnContext` are built directly. Where a second (or
  a deliberately `ask_`-named) catalogue entry is needed, `TOOL_REGISTRY` is monkeypatched in **both**
  `app.services.tools` and `app.services.subagent_delegation` (which imports the name directly).
  Asserted: a mode's sub-agent appearing beside the real registry tool in one `build_tool_bindings`
  pair with identical key sets, the description carrying the sub-agent's name verbatim, `args_schema`
  being `DelegationArgs` and `inspect.signature(tool.callable)` leaving exactly `task` free — plus the
  same combined maps arriving at a live turn's `chat_with_tools` (DoD-1); a **stale link row** to a
  `disabled` sub-agent excluded while an enabled sibling on the same mode IS built, so the exclusion is
  observed against a non-empty build (DoD-2); a sub-agent linked only to *another* mode absent from
  both the build and the callable map while its in-mode sibling is present, and built when that other
  mode is asked for (DoD-3); with no mode, `build_delegation_tools(None, …) == []` and a full turn's
  maps set-equal to `BASE_TOOL_NAMES` with **no** `ask_`-prefixed key, even though a mode elsewhere
  selects a sub-agent (DoD-4); the nested `system` equal to the sub-agent's own `system_prompt` alone
  with `BASE_SYSTEM_PROMPT` and the mode prompt absent from it, and the nested final string returned to
  the parent (DoD-5); the nested `tools`/`tools_definitions` being exactly the sub-agent's
  `subagent_tool` allowlist resolved against `TOOL_REGISTRY` — another catalogue entry, another
  sub-agent's selection and **every** delegation tool excluded (DoD-6); an unknown `subagent_tool` name
  skipped with a record from an `app.*` logger naming it while the delegation still runs (DoD-7); a
  fully assigned sub-agent constructing through the seam for **its** server and model, explicitly not
  the parent's (DoD-8); a null — and each half-null — assignment inheriting the parent's server,
  resolved key and model (DoD-9); a missing assigned server (no client constructed at all) and an
  unusable one (construction raising `ValueError`) each returning a non-empty error string that is not
  the nested answer, without raising (DoD-10); `max_loops` equal to `SUBAGENT_MAX_LOOPS` and that
  constant differing from `chat_turn.MAX_LOOPS` — asserted against the constants, never a literal
  (DoD-11); a sub-agent named "Expert" colliding with a real `ask_expert` registry entry being skipped
  and logged while the **real** tool survives as the sole `ask_expert` in the maps with the registry's
  own callable (DoD-12); two sub-agent names deriving to `ask_continuity_checker` producing exactly one
  tool beside a third distinct one, with the duplicate logged (DoD-13); five nested failure modes —
  `aiohttp.ClientConnectionError`, `aiohttp.ClientError`, `LLMError`, `RuntimeError("max_loops
  exhausted")` and a wrapped raising nested tool — each returning an error string and never raising
  (DoD-14); and the client entered and exited exactly once on the success path, a second invocation
  constructing a second **distinct** client, and `__aexit__` still running when the nested call blew up
  (DoD-15).
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓, DoD-14 ✓, DoD-15 ✓, DoD-16 [manual/live, no test]

### Step 009 — tests (2026-07-27)

- `backend/tests/services/test_codex_tools.py` — covers DoD-1 … DoD-13 — the two codex assistant
  tools, with **no network**: step 004's embed call is mocked at `app.services.embedding`
  (`embed_text` / `embed_batch` / `is_available` substituted together, so the "no provider" world is
  consistent whichever the tool consults), while step 005's sidecar runs **for real** against a
  per-test `tmp_path` vector dir with four fixed short vectors (`V_EXACT` / `V_NEAR` / `V_MID` /
  `V_FAR`) whose distances are strictly ordered under both L2 and cosine; codex rows are seeded in
  **two** books through `db/{users,books,codex_entries,llm_servers,chats,assistant_modes,mode_tools}`
  against the real `db` fixture, chunks are written straight through `vector.upsert_chunks`, and
  `ToolContext` / `TurnContext` are built directly. Asserted: a **foreign book's** entry sitting
  exactly on the query vector — proved nearest by a direct `vector.search` against that book — never
  reaching the answer while the turn's own, strictly worse-matching entry does (DoD-1); a chunk of
  **another source kind** in the *same* book, also sitting on the query vector, excluded while the
  codex chunk survives (DoD-2); each hit's **entry id** rendered beside its chunk snippet, and that id
  read back verbatim by the read tool (DoD-3); a `limit=2` over three strictly-ranked entries dropping
  the third and ordering the two by nearness, both by snippet and by id position in the string
  (DoD-4); **no provider** returning a non-empty string carrying no indexed content and not raising
  (DoD-5); an **empty** index *and* a **stale** index (chunks exist, none of them this book's) each
  returning a non-empty string **distinct from both** the no-provider and the transport-failure
  strings — "nothing found" is not an error (DoD-6); an embedding **transport failure**
  (`EmbeddingError(unreachable)`) returning a string and not raising (DoD-7); the read tool returning
  an entry's kind value, name and body (DoD-8); **another book's** entry refused with neither its body
  nor its name in the returned string, while the same id read from its own book does return the
  content (DoD-9); an unknown-but-well-formed id and four malformed ids (`"not-a-number"`, `"12x"`,
  `""`, `"-1"`) each returning a string and not raising (DoD-10); an **archived** entry refused
  without its body while a live sibling in the same book still reads (DoD-11); both tools present in
  `TOOL_REGISTRY`, `build_tool_bindings(selected, ToolContext(book_id=…))` producing definitions and
  callables with one key set and free parameters exactly equal to each `args_schema`'s fields, the
  bound read tool reaching **that** book's entry and the same tool bound to another book's context not
  — plus, through a live `run_turn`, a mode whose `mode_tool` rows select both offering exactly both
  (bound to the turn's book, dispatch-verified) and a sibling mode selecting neither building neither
  (DoD-12); and `web_search` binding to **its own shipped callable** (`is web_search`) through the
  widened `build_tool_bindings` both with a real `ToolContext` and with none, plus a no-mode turn still
  offering it (DoD-13). No score threshold is asserted anywhere — UC-078's relevance criterion is an
  open product `_TBD:`.
- `backend/tests/services/test_tools.py` — **one superseded assertion replaced** (scope extension
  granted by the orchestrator; the rest of the file is feature 011's regression evidence and is
  untouched). `test_registry_has_single_web_search_entry__DoD3`'s `len(TOOL_REGISTRY) == 1` became a
  pin of the registry's new contents (`web_search` + `codex_search` + `codex_read_entry`), keeping the
  test's original intent — the catalogue is known and pinned — and its remaining four assertions
  (`web_search` first, its description, its `args_schema`, its `callable`) unchanged.
- `backend/tests/services/test_chat_turn.py` — **one superseded assertion replaced** (same grant).
  `test_system_prompt_and_whole_registry_offered__DoD11`'s "a null-mode turn offers the whole registry"
  became "offers exactly `assistant_runtime.BASE_TOOL_NAMES`", per `context.md` decision 6 as landed by
  step 007; the system-prompt half of the test is untouched, and the now-unused `TOOL_REGISTRY` import
  was swapped for `BASE_TOOL_NAMES`. These two edits resolve the `## Notes & Issues` → "Step 009
  (skeleton)" collision along its recommended option 1, so the red gate's baseline is the ordinary
  "everything passes except step 009's own new tests".
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓, DoD-14 [manual/live, no test]

### Step 010 — tests (2026-07-27)

- `backend/tests/services/test_codex_canvas_tools.py` — covers DoD-1, DoD-4 … DoD-12 — the
  `write_codex_draft` tool's behaviour, driven directly with a **recording emitter** matching the
  frozen `FrameEmitter = Callable[[str, BaseModel], Awaitable[None]]` shape, so "exactly one frame
  whose event is `canvas`" is observable without a live stream. Rows are seeded through
  `db/{users,books,codex_entries,llm_servers,chats,assistant_modes,mode_tools}` against the real `db`
  fixture; `ToolContext(book_id=…, access=…, subject=…, emit_frame=…)`, `BookAccess` and
  `ResolvedSubject` are built directly; no network anywhere. Asserted: an editable codex-entry subject
  emitting **exactly one** `("canvas", CanvasFrame)` pair whose payload carries `subject_kind`
  `"codex-entry"`, `subject_id == str(entry.id)`, the field written and the text written — verified
  for both `body` and `name` so the payload reports what was written rather than a fixed value
  (DoD-1); a **non-empty** confirmation string on success that is **not equal** to the refusal string
  (DoD-4); an **archived** entry refused with a string and **zero** frames while a live sibling in the
  same book still emits one (DoD-5); a book-state subject, all six list kinds, a chapter, `NO_SUBJECT`
  and a literal `None` subject each refused for both fields with a string and no frame (DoD-6); a
  **co-author** in a `proposal`-mode book refused with a string containing **`FEAT-010`** and no
  frame, while the same co-author in a `free`-mode book is not refused — so the rule is the
  collaboration mode, not the role (DoD-7); the **owner** of a proposal-mode book emitting the frame
  normally, with no `FEAT-010` in the answer (DoD-8); a **blank** entry (`kind="codex-entry"`,
  `entry is None`) under `edit-character` and `edit-location` allowed, with the frame's `subject_id`
  **`is None`** — not `""`, not a placeholder (DoD-9); a `fact` subject refusing `field="name"` with
  no frame yet allowing `field="body"` with one frame, asserted for an **existing fact row and for a
  blank fact** (whose kind rides on `mode_key="edit-fact"`), plus a character still accepting a name
  so the refusal is the fact rule (DoD-10); a **failing emitter** (`RuntimeError`, standing in for the
  queue failure), a **missing** emitter, a missing `access`, and every refusal path each returning a
  non-empty string with **nothing raised** (DoD-11); and, through a live `run_turn`, a mode whose
  `mode_tool` row names `write_codex_draft` offering it in both the definitions and the callable map
  with free parameters exactly `WriteCodexDraftArgs`' fields, a sibling mode building **neither** it
  nor any `ask_` key, and a no-mode turn offering exactly `BASE_TOOL_NAMES` (DoD-12).
- `backend/tests/routes/test_chat_turn_canvas.py` — covers DoD-2, DoD-3 — the wire, end to end
  against the real `app.main.app` through the **unchanged** `POST /api/books/{book_id}/chats/{chat_id}/turn`.
  Auth is real (seeded user + minted JWT, helpers copied from `tests/routes/test_chats.py`); the `llm`
  client is faked by a `_ToolInvokingClient` that streams prose, **invokes the `write_codex_draft`
  callable it was handed** mid-stream, then streams more prose — without that invocation DoD-2 would
  be green against nothing. The mode is unlocked with `assistant_modes.seed_default_modes()` plus one
  `ModeTool(mode_key="edit-character", tool_name="write_codex_draft")` row, and the turn request
  carries `subject_kind="codex-entry"` / `subject_id`. Asserted: the raw body containing the literal
  `event: canvas` line **exactly once**, its `data:` parsing to exactly the four keys
  `{subject_kind, subject_id, field, text}` with the seeded entry's id and the written text, and
  re-validating as `CanvasFrame`; a `delta` frame **before** and **after** it on the one stream
  (interleaving), the stream still ending in one `done` with no `error`, and the tool proven offered
  and invoked (DoD-2); and a **byte-for-byte** before/after snapshot of `codex_entries` (all rows of
  the book, `include_archived=True`) **and** `codex_entry_versions` (per entry) comparing equal after
  a turn that provably invoked the tool — zero version rows, the entry's `name`/`body` re-read
  unchanged, while the chat's own user message *did* persist so the turn was a real one (DoD-3).
- `backend/tests/services/test_tools.py` — **one superseded assertion updated** (scope extension
  granted by the orchestrator; nothing else in the file touched). The registry pin in
  `test_registry_has_single_web_search_entry__DoD3` gained the fourth entry `write_codex_draft`,
  keeping the test's intent — the catalogue is known and pinned, not open-ended. This resolves the
  `## Skeleton` → Step 010 note's "one pre-existing test now FAILS", so the red gate's baseline is
  again "everything passes except step 010's own new tests".
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓ (no `[manual/live]` item in this step)

### Step 011 — tests (2026-07-27)

- `frontend/tests/work/codexListPage.test.tsx` — covers DoD-1 … DoD-10 — the three codex list
  routes, the query-string search, row activation, the trio's states and the api module's wire
  boundary. `globals: false` (every primitive imported from `"vitest"`); `api/codex`, `api/chats`
  and `api/books` mocked module-factory form, never `fetch`; `api/client` mocked as
  `{...importActual, request: vi.fn()}` so **`ApiError` stays the real class** while the two
  api-module cases can drive the **real** `api/codex` through `vi.importActual`. Every mock is
  re-armed in `beforeEach` (`restoreMocks`). The list mock answers with the book's entries **of the
  requested kind**, so a page that asked for the wrong kind renders the wrong rows. Asserted:
  - **DoD-1** — parameterized over the three routes mounted through the **real `WorkRoutes`**:
    `/bk-1/characters` calls the api with kind `character` and shows only `Aria Stormcrow`, while
    the location and fact markers are absent from the content pane (`main`); likewise
    `/locations` and `/facts` (the fact has `name: null`, so it is identified by its body excerpt).
    Plus a "kind is not user-selectable" case: no `combobox` / `radio` / `listbox` and no
    kind-named button inside `main` (the chat pane's own controls are outside it).
  - **DoD-2** — the needle is typed and submitted while the **second fetch is held pending**, and
    the URL already carries `q=storm` at that moment (so the write is in the handler, not
    downstream of the load); the second api call carries the needle. A second case proves the
    *causation* the other way: a query-string change made **from outside the page** (a probe on the
    same router) triggers **no** further fetch — a page reacting to the URL in an effect would
    refetch there (`frontend.md`:192). A third case binds the frozen `submitCodexSearch` directly:
    it commits `draftNeedle` → `needle`, starts exactly one fetch with the needle, and returns
    `"q=storm"` **without** a leading `?`.
  - **DoD-3** — mounting on `?q=storm` makes the **first** call carry the needle and there is
    exactly **one** call (no unfiltered load first); the search input shows the deep-linked needle.
    Plus a state-level case: the constructor seeds both `needle` and `draftNeedle`.
  - **DoD-4** — clearing the input and submitting removes `q` from the URL entirely (not an empty
    `q=`) and refetches with no needle; plus `submitCodexSearch` returning `""` for a cleared
    needle.
  - **DoD-5** — the **second** row is activated, and the router lands on `/bk-1/codex/ce-char-2`,
    so the id is the activated row's own (basename-stripped).
  - **DoD-6** — an empty result renders an empty state: no `alert`, no error wording, no retry
    control, a non-blank pane naming the emptiness. Plus the frozen `isEmpty` computed: `false`
    while idle, `true` after a completed load that matched nothing, `false` with entries, and
    `false` on an error.
  - **DoD-7** — a rejected load renders error wording and no rows, and clicking retry re-fetches
    (call count 2) with the list arriving on the second attempt; plus a state-level case that
    `loadCodexEntries` leaves `entriesStatus === "error"` with a non-empty `entriesError` and no
    entries.
  - **DoD-8** — parameterized over `character` and `fact`: the new-entry action lands on
    `/bk-1/codex/new` with `?kind=<route kind>`.
  - **DoD-9** — the **real** `listCodexEntries` given `{items: [a, b]}` returns the plain array
    `[a, b]` (and `{items: []}` → `[]`), plus a compile-time pair (`ListResult` accepts `[]` and a
    `@ts-expect-error` rejects `{items: []}`) pinning that the `.d.ts` models no envelope.
  - **DoD-10** — largely compile-time, as the skeleton flagged: `@ts-expect-error` declarations
    that a numeric book id / entry id must not compile, plus runtime evidence — the real
    `create` / `update` / `get` calls put the string ids verbatim into the url and no `*_id` key in
    any request body is a number, and the book id the page hands the mocked api is the string it
    was given.
- `frontend/tests/work/subjectRoutes.test.tsx` — **three superseded cases updated** (narrow scope
  extension granted by the orchestrator; nothing else in the file touched). Feature 010's DoD-5
  rows for `/bk-1/characters`, `/bk-1/locations` and `/bk-1/facts` asserted a `013.codex`
  placeholder — exactly what this step replaces. They now assert the **new truth**: each route
  renders the codex list page listing its own kind's entry and **no** `013.codex` placeholder
  survives in the content pane. `/chapters`, `/variants`, `/codex/ce-1` (step 012's), the `/chats`
  redirect and the catch-alls are unchanged. An `api/codex` module-factory mock and its
  `beforeEach` re-arm were added because those three routes now load through it (the file mocks
  `api/`, never `fetch`). This resolves the `## Skeleton` → Step 011 note's "three pre-existing
  cases falsified".
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓ (no `[manual/live]` item in this step; DoD-10 is expected **green** at the red gate —
  the skeleton records it as a compile-time property discharged by `types/codex.d.ts` + the four
  frozen api signatures, so its bite is `npm run test:types`)

### Step 012 — tests (2026-07-27)

- `frontend/tests/work/codexEntryPage.test.tsx` — covers DoD-1 … DoD-13 — load / draft / buffer /
  save / reconciliation for one codex entry. `globals: false`; `api/codex` mocked module-factory
  form (never `fetch`), re-armed in `beforeEach` (`restoreMocks`); **`ApiError` imported real** from
  `api/client` so the 409 / 403 rejections are the genuine class carrying step 003's wire detail
  body `{detail: {reason, message}}`. The page is mounted **directly** under its two routes
  (`/:bookId/codex/new` + `/:bookId/codex/:id`, basename-stripped) beside a location probe, never
  through `WorkRoutes`, so no `api/chats` / `api/books` mock is needed. `restoreBuffer.ts` is used
  **for real** (complete and unit-tested) and every buffer is seeded inside the test that needs it
  (`tests/setup.ts` clears `localStorage` in `afterEach`). Each behaviour is asserted at the page
  and, where the value is exact, again at the frozen state/effect layer. Asserted:
  - **DoD-1** — `/bk-1/codex/ce-1` calls `getCodexEntry("bk-1", "ce-1")` and both the name and the
    body reach the surface; plus the trio settling `ready` with both drafts seeded, `isDirty` false
    and `baseVersion === modified_at`.
  - **DoD-2** — one body change writes `restoreBufferKey(bookId, "codex-entry", id)` with
    `draft === the typed body` and `baseVersion === the entry's modified_at` (the ISO string, not a
    number); plus `editCodexDraft` marking `isDirty` and keying through `state.bufferKey`, and
    `applyDraft` (step 013's entry point) taking the identical dirty/buffer path.
  - **DoD-3** — a buffer seeded at the **matching** `baseVersion` puts the buffered body on screen
    and the server text is **absent** from the fields; state-level: `bodyDraft` restored, `isDirty`
    true, **not** reconciling, `conflictEntry` null. Plus the no-buffer case: server text stands.
  - **DoD-4** — after editing both fields the buffer holds the draft and **no** create/update call
    exists; the page is then unmounted (navigating away) and, after a tick, still none, with the
    draft surviving in the buffer. Plus `editCodexDraft` making **no** api call at all.
  - **DoD-5** — Save calls `updateCodexEntry(bookId, entryId, {body, expected_modified_at: the
    LOADED modified_at})` and the buffer is gone afterwards; state-level: `saveStatus "saved"`,
    `null` return (only a create navigates), the response's `modified_at` adopted so the **second**
    save carries `M3` (the `012.context.md` anti-409-loop clause). Plus discard: buffer cleared,
    drafts back to the loaded row, no server call.
  - **DoD-6** — a 409 (real `ApiError`) puts the re-fetched server body **and** the author's draft
    on screen at once with ≥2 enabled actions (an explicit per-side choice), exactly **one** update
    attempt (no silent overwrite) and the draft unmerged; state-level: `conflictEntry` = the
    re-fetched row, `isReconciling` true, `bodyDraft` untouched.
  - **DoD-7** — a buffer seeded at a **stale** `baseVersion` reconciles straight off the load
    (server text beside the buffered draft) with **no write call at all**; state-level:
    `conflictEntry` = the loaded row, `saveStatus` still `"idle"`.
  - **DoD-8** — from the 409 state, `resolveCodexConflict(state, "server")` leaves `bodyDraft` =
    the server body, clears the buffer, leaves the view and writes nothing further;
    `resolveCodexConflict(state, "draft")` fires a **second** update whose
    `expected_modified_at` is the **new** `modified_at` (`M2`) with the author's body, and it
    succeeds (`saveStatus "saved"`, view left, buffer cleared).
  - **DoD-9** — an archived entry renders `subject.ts`'s verbatim reason ("This codex entry is
    archived and read-only; restore it to make changes.") and **no enabled save control**;
    state-level `isReadOnly` / `editable: "none"` / `readOnlyReason` / `canSave === false`, with the
    non-archived control case (`"whole"`, `null`, `canSave` true).
  - **DoD-10** — a `fact` renders no name-labelled field and exactly one editable field, and its
    save carries `name == null`; `requiresName` false and valid without a name. Parameterized over
    `character` and `location`: emptying the name (and whitespace-only) makes Save unavailable and a
    real name unlocks it, with no write fired; state-level `nameError` / `isValid` / `canSave`.
  - **DoD-11** — `/bk-1/codex/new?kind=location` contacts nothing on mount, creates with
    `kind: "location"` + the typed name/body (never an update), then the router lands on
    `/bk-1/codex/ce-new-9`; the `?kind=fact` case additionally has no name field and creates with
    `name == null`. State-level: a blank state settles `ready` with `entry === null` and
    `bufferKey === null`, and `saveCodexEntry` returns the created entry's route while adopting
    its id.
  - **DoD-12** — a 403 whose detail body is `{reason: "proposal_mode_unsupported", message: …
    FEAT-010 …}` puts **FEAT-010** on screen while the draft stays in the editor and the buffer
    survives with its `baseVersion`; state-level: the text lands in `saveError` (not `nameError`),
    `saveStatus "error"`, and it is **not** a reconciliation (no `conflictEntry`, no re-fetch).
  - **DoD-13** — a seeded *other* buffer plus a one-shot `QuotaExceededError` on the current key
    drives `restoreBuffer`'s real eviction: the evicted key is **named on screen**, the victim is
    gone and the **current** item's buffer holds the draft; state-level `evictedBufferKeys` contains
    the victim and never the current key, and an ordinary write reports `[]`.
- `frontend/tests/work/subjectRoutes.test.tsx` — **one superseded case updated** (narrow scope
  extension granted by the orchestrator; nothing else in the file touched). Feature 010's DoD-6 row
  for `/bk-1/codex/ce-1` asserted a `013.codex` placeholder — exactly what this step replaces. It
  now asserts the **new truth**: the item route renders the loaded entry inside the content pane and
  no `013.codex` placeholder survives. A `getCodexEntry` re-arm was added to `beforeEach` because
  that route now loads through it. `/chapter/:id`, `/variants/:chapterId`, the list routes, the
  `/chats` redirect and the catch-alls are unchanged. This resolves the `## Skeleton` → "Step 012
  (skeleton)" note.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓ (no `[manual/live]` item in this step; the skeleton
  expects **all thirteen red** at the gate — every path enters the throwing render or one of the
  five throwing effect functions)

### Step 013 — tests (2026-07-27)

- `frontend/tests/work/contentSubject.test.ts` — covers DoD-4, DoD-5, DoD-7, DoD-8, DoD-9 (and
  DoD-1's read-at-call-time premise) — the module-tier registry on its own: register / unregister /
  read / dispatch. A pure module spec in the `restoreBuffer.ts` / `activeChat.ts` tier — no router,
  no render, no api mock; `restoreBuffer.ts` is used **for real** and `tests/setup.ts` clears
  `localStorage` in `afterEach`. `contentSubject.ts` is **module-level state**, so every case resets
  the registry **through the frozen API alone** (register a sentinel source, then unregister it —
  the newest registration wins outright), in `beforeEach` *and* `afterEach`; the reset is harness
  hygiene and is deliberately fault-tolerant, so an unimplemented registry cannot redden a case for
  an unrelated reason (DoD-4's case asserts "nothing registered" for itself). Asserted:
  - **DoD-9** — a registration becomes the current subject and unregistering clears it; the newest
    registration **wins outright**; a **late** unregister from a superseded source is a **no-op**
    (the identity guard) while the owner can still clear it.
  - **DoD-4** — with nothing registered, `currentContentSubject()` is `null`.
  - **DoD-1** — the source is invoked at **read** time, so a `codexKind` still unknown when the page
    mounted is carried once the load resolves (the reason the registration is a function).
  - **DoD-5** — a matching frame's `(field, text)` reaches the apply-draft callback for both
    `"body"` and `"name"`; a dispatched frame goes to the target **instead of** the buffer (the
    spec's "otherwise"), and a **blank** target (no `entityId`) matches a `subject_id: null` frame.
  - **DoD-7** — with nothing registered the text lands at the literal key
    `bookwriter.restore-buffer:<bookId>:codex-entry:<id>` (asserted as a string **and** as
    `restoreBufferKey(...)`'s output), a **list** registration (no callback) is "no target" for this
    purpose, only that one key is written, and a **blank-entry** frame with no target is **dropped**
    (no key written, no throw).
  - **DoD-8** — a frame naming another entry id, a `null` id against an open existing entry, and a
    frame whose **kind** differs all leave the callback uncalled and the open entry's own buffer
    **null**, while the text is buffered under the **frame's** key; an already-unregistered target
    receives nothing even for its own entry.
- `frontend/tests/work/canvasWiring.test.tsx` — covers DoD-1 … DoD-11 — the wiring end to end.
  `globals: false`. `api/codex` is mocked module-factory form (re-armed in `beforeEach`);
  **`api/chats` is deliberately NOT mocked** so the **real** `streamChatTurn` runs and the asserted
  POST body is the body the app actually sends; below it **`api/sse.streamPost` is mocked** (the
  skeleton-nominated seam — it owns the `AbortController`) so the posted body and the turn's handlers
  are observable — **except in the DoD-11 block**, which restores the **real** `sse.ts` through
  `vi.importActual` and feeds it raw `event:` / `data:` chunks over a streamed fetch double, so
  `sse.ts`'s own parsing and branching actually execute (that block is the one place `fetch` is
  doubled, deliberately: the transport's own routing **is** the clause under test).
  `api/client` keeps its real `ApiError` while `request` / `refreshAuthToken` are stubbed, so no test
  reaches the network. Pages are mounted **directly** under their own routes (basename-stripped),
  never through `WorkRoutes`, so no `api/books` mock is needed. The registry is reset through its own
  API around every case. Asserted:
  - **DoD-1** — with `/bk-1/codex/ce-1` loaded, the posted body carries `subject_kind
    "codex-entry"`, `subject_id "ce-1"` and `codex_kind "character"` beside the prompt; a location
    entry sends `"location"` (the kind is the **open row's**, not a constant); and after navigating
    from one entry to another, a **retry** carries the **new** entry — the subject is read at send
    time in both send and retry paths.
  - **DoD-2** — `/bk-1/codex/new?kind=location` fetches nothing and sends `subject_id` **null**
    (strictly null, never omitted) with `codex_kind "location"`; the `?kind=fact` case likewise.
  - **DoD-3** — parameterized over the three list routes: the body carries `"characters"` /
    `"locations"` / `"facts"` and **no id**.
  - **DoD-4** — with **no content page mounted at all**, the posted body's key set is **exactly**
    `["prompt"]`, and the turn still runs (the stream opens, `turnStatus === "streaming"`, the
    author's message shows). The body is the only evidence taken — the case never probes the
    registry API, so it stays a regression lock on the pane's inertness.
  - **DoD-5** — a `canvas` frame delivered through the pane puts its text in the open entry's **body**
    field (and the server text it replaced is gone from the fields); a `field: "name"` frame lands in
    the **name** field and leaves the body alone.
  - **DoD-6** — an applied canvas draft sets `bodyDraft`, makes the page **dirty** and writes the
    buffer with the entry's loaded `modified_at` as `baseVersion`, with **no create/update call**;
    the buffer record is asserted **field-equal to the one a keystroke writes** through
    `editCodexDraft`; and the through-the-pane route makes no save call either.
  - **DoD-7** — the page is mounted, a turn opened, then the page **unmounted** (the author navigated
    away mid-turn) before the frame arrives: the draft lands at the literal
    `bookwriter.restore-buffer:bk-1:codex-entry:ce-1`, and **remounting the entry surfaces that text**
    (the round trip, asserted through the page, not just the write) with still no save call.
  - **DoD-8** — a frame for `ce-other-7` is buffered under **its** key while the open entry keeps its
    own text on screen, its own buffer stays `null`, and the other body is nowhere on the page;
    state-level, `bodyDraft` is unchanged and `isDirty` stays false.
  - **DoD-9** — the entry page's registration exists after mount (`kind "codex-entry"`, its
    `entityId`) and is `null` after unmount; a list page registers a kind-only subject (no
    `entityId`) and clears it; and with two pages overlapping, a **late** unmount of the previous one
    leaves the newer page's registration standing until the newer page itself unmounts.
  - **DoD-10** — both directions are observed **through the app's own path**, never by probing the
    registry: a **real** subject switch (entry page unmounted, list page mounted) leaves
    `activeChatId`, the per-book pointer and the loaded messages untouched while the **next turn's
    body** shows the subject really did change to `"characters"`; and a **real** chat switch
    (`pickChat`) leaves the entry on screen and the next turn's three subject fields **equal to the
    pre-switch turn's**, while that turn's URL names the **new** chat.
  - **DoD-11** — three cases run the **real** `sse.ts` over a raw `event: canvas\ndata: {…}` chunk
    fed through a streamed fetch double (never a hand-invoked `onEvent`, which would pass just as
    well against an `sse.ts` that special-cased `canvas`): (a) `sse.ts` parses the frame and routes
    it to its **generic** `onEvent("canvas", payload)` branch with the payload intact, while `done`
    still reaches `onDone` and `onError` is never called; (b) with the real `streamPost` reinstated
    behind the real `streamChatTurn`, the same wire frame reaches `onCanvas` exactly once, intact;
    (c) end to end — wire -> `sse.ts` -> `onCanvas` -> the registry -> the open entry's draft on
    screen.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓ (no `[manual/live]` item in this step)
- **`npm run test:types` was NOT run by the test-coder — no shell tool was available in either of
  its sessions.** The verifier ran it on round 1 (clean). The round-2 revision (the DoD-11 rewrite
  onto the real `sse.ts` + the DoD-4 / DoD-10 reframing) is likewise **typecheck-unverified** by the
  test-coder and must be re-run at the gate.
- **Round 2 (TEST fault, DoD-11) — resolved.** The verifier ruled the original DoD-11 block invalid:
  it mocked `api/sse` file-wide and then invoked `handlers.onEvent("canvas", …)` by hand, so
  `sse.ts`'s real `else { handlers.onEvent?.(…) }` branch never executed and the cases would have
  passed against an `sse.ts` that special-cased `canvas` — the exact distinction the clause exists to
  draw. The block now reinstates the real module through `vi.importActual` and drives raw SSE chunks
  into it. Also taken (advisory): DoD-4's first case and both DoD-10 cases no longer call
  `currentContentSubject()` inside the test body — they read the subject through the posted turn body
  and the rendered page, so they stay regression locks on 011-era behaviour rather than being red on
  the registry stub. Nothing else changed.

## Notes & Issues

- Step 001: name ordering uses SQLite's default (binary) collation — `"Keep" < "Zara" < "alba"`.
  The step file says "name ascending" without a case-folding rule, so no `lower()` was applied;
  if the list page later wants case-insensitive ordering that is a service/step-002 decision.
- Step 001: the needle is `LIKE`-escaped (`autoescape`), so a literal `%` or `_` in the search
  text matches itself rather than acting as a wildcard — "substring", as the step file words it.
- Step 002: `create_entry` sets **both** `created_at` and `modified_at` to now (the `books` /
  `chats` precedent), so a freshly created entry already carries a non-null version token — step
  003 DoD-8 ("returns the updated DTO with a *later* `modified_at`") and step 012's restore-buffer
  `baseVersion` both need one. A `None` stored `modified_at` (a row seeded straight through `db/`)
  still compares correctly on the update path.
- Step 002: the staleness comparison normalizes a tz-aware `expected_modified_at` to naive UTC
  before comparing, because SQLite returns stored timestamps naive — the same instant sent back
  aware would otherwise read as stale. Only a genuinely different value is refused.
- Step 002: a passing name is stored **exactly as supplied** — the whitespace rule decides
  presence/absence only, it does not trim what it stores. If the entry page should trim, that is a
  later decision, not one this step's spec asks for.
- Step 004: the `embedding_model` passed to `create_model_client` is the **stripped** stored value
  (the blankness test and the model binding read the same local), so a stored `" model "` binds as
  `"model"`. The step file only specifies blank → `no_provider`; trimming what is otherwise sent is
  the conservative reading.
- Step 004: `embed_text` raises `unreachable` when `embed_batch` comes back empty for a non-empty
  input. The step file does not name that case, but letting an `IndexError` escape would break the
  module's "no caller catches anything but `EmbeddingError`" contract.
- Step 004: no vector-count check — `embed_batch` returns exactly what the client returned, so a
  client that answers with fewer vectors than texts would silently mis-pair chunks. Adding a
  count/alignment guard is a candidate for step 006, where the pairing is actually consumed.

- **Step 005 (skeleton) — RESOLVED 2026-07-27 by the orchestrator (user decisions); recorded here as
  history. A second superseded feature-007 guard test sat outside the step's Test-files scope.**
  - **What intent asked for:** step 005 DoD-11 — "`VECTOR_SOURCE_REGISTRY` holds exactly one entry,
    discriminated `codex_entry`" — and DoD-12/DoD-13, a `rebuild_index` that probes, creates the
    chunk table and walks the registry.
  - **What conflicts:** `backend/tests/services/test_db_admin_rebuild.py` (feature 007, step 004)
    holds three tests that step 005 must break, and that file is **not** in step 005's Test files:
    - line 159 `test_vector_source_registry_is_empty__DoD5_D6` — `assert
      vector.VECTOR_SOURCE_REGISTRY == []`. Directly contradicted by DoD-11; unavoidable.
    - lines 86 / 100 `test_rebuild_valid_designation_returns_zero__DoD1_US020_AC1` and
      `test_rebuild_twice_is_idempotent__DoD2_US020_AC1` — they call `init_vector(tmp_path /
      "vector")` with **no** injected embedder, then expect `rebuild_vector_index()` to return `0`.
      Their fate depends on a behaviour choice the step file does not make: what `rebuild_index`
      does when no embedder was injected. Preserve-the-old-outcome (drop tables, return `0`) keeps
      them green; raising a typed error kills them. They also seed no codex rows and open no db
      engine, so a registry walk would hit an uninitialized engine.
    `005.context.md` identified the *analogous* guard in `test_data_domain_codex.py:552` and put that
    file in the Test files list; it missed this one. Both were written as feature-007/008 deferral
    locks pointing at exactly this step.
  - **Why the skeleton did not resolve it:** the freeze itself ripples nowhere — the two new
    `init_vector` parameters default to `None` and the registry stays empty, so all 624 tests still
    pass. The collision is unavoidable **at implementation time**, not at freeze time, so it is
    recorded rather than guessed at.
  - **Resolution (user, via the orchestrator) — options 1 + 2 of the three offered, taken together:**
    1. **`rebuild_index()` un-injected raises a typed error**, not "returns 0". `db/vector.py` gained
       its own `VectorIndexError` for it (a plain exception class — rationale in the Step 005
       Skeleton record; it may not reuse `services/embedding.py:EmbeddingError`, that is the
       forbidden `db → services` direction). `rebuild_index() -> int` is otherwise untouched:
       raising changes no signature and no call shape. `run_vector_rebuild()` log-and-swallows it
       (DoD-14); `db_admin.rebuild_vector_index()` propagates it.
    2. **The scope extension is granted** for `backend/tests/services/test_db_admin_rebuild.py`: the
       test-coder inverts the `VECTOR_SOURCE_REGISTRY == []` guard at line 160 and re-points
       `test_rebuild_valid_designation_returns_zero__DoD1_US020_AC1` /
       `test_rebuild_twice_is_idempotent__DoD2_US020_AC1` to inject deterministic mock callables
       through `init_vector`, since decision 1 makes their current un-injected one-argument calls
       raise.
    Option 3 ("do nothing, let verify report it as `CODE`") was rejected — the fault was `SPEC`.
    The skeleton was amended to add `VectorIndexError` **only**; every other frozen signature
    stands and the registry stays empty as recorded.
- Step 005: **the vector-count guard step 004 deferred was added here**, in `rebuild_index`'s batch
  loop: when the injected embedder returns a different number of vectors than the batch had chunks,
  the rebuild raises the frozen `VectorIndexError` rather than `zip`-truncating. Positional pairing
  is the only thing tying a chunk to its vector, so a short answer would mis-pair every chunk after
  the gap and write a silently wrong index — and a full rebuild is the one operation that can be
  re-run for free. No new error type and no signature change. The **incremental** path (step 006)
  consumes the same pairing and needs its own guard there; this one only covers the rebuild.
- Step 005: the single-chunk threshold is measured on the **body**, not on body-plus-name-prefix
  (DoD-8's wording: "an entry whose *body* fits the chunk size"). A 1200-character body with a name
  is therefore one chunk of 1200 + `len(name) + 2` characters; only a body that actually overflows
  is split, and then every chunk is ≤ `CHUNK_SIZE_CHARS` because the prefix comes out of the first
  window's budget. `outcome.md` item 9 says "with the name prefix included in the size budget" —
  true of the split path, one step removed from the threshold test; recorded under `## Observations`
  so the architect words it as built.
- Step 005: **the chunk overlap is paragraph-aligned, not character-exact** (as-built after the
  DoD-10 fix). The paragraph boundary is the structural rule and `CHUNK_OVERLAP_CHARS` is a tuning
  quantity, so a window opens with the shortest run of **whole** trailing paragraphs of the window
  before it that reaches ~200 characters: every chunk begins and ends on a boundary and holds
  nothing but complete paragraphs of the body, and the realized overlap is approximately, not
  exactly, 200 characters. Two bounded consequences: (a) the carry is capped at half a window so
  overlap can never crowd out new material, which means a body whose paragraphs are each longer
  than half a window gets **no** overlap — whole-paragraph overlap is arithmetically impossible
  there without breaking the size bound; (b) when only the carry is standing between a paragraph
  and a window it would fit in alone, the carry is dropped rather than the paragraph cut. The one
  sanctioned exception is a single paragraph longer than a whole window: it is still cut
  mid-paragraph with a plain character tail, because there is no boundary to cut on. Determinism
  is unchanged — chunking is a pure function of the entry.
- Step 005: only the **first** chunk of a split body carries the name prefix — the step file states
  the prepend rule for the one-chunk case only, and repeating the prefix would put text that is not
  in the body into every window. As-built retrieval characteristic: a name-only query ("Marek")
  reaches a long entry through its first chunk, but its later chunks are findable by their own
  content, not by the name. If name-prefixing every chunk is wanted, that is a chunker tune, not a
  contract change.
- Step 005: `db/vector.py` now imports `pyarrow` directly (to declare the chunk table's schema at a
  runtime dimension with zero rows). It is not a declared dependency in `backend/pyproject.toml` —
  it arrives as a hard, pinned dependency of `lancedb`. Adding it explicitly to `pyproject.toml` is
  a packaging decision, not this step's scope.
- Step 005: `upsert_chunks` / `delete_by_*` / `search` treat an uninitialized store (`init_vector`
  never called) as "no table" — a logged no-op / empty result rather than a raise. `VectorIndexError`
  is frozen as `rebuild_index`'s failure, and the maintenance path (step 006, `retrieval.md`) never
  blocks an author's save; the lifespan always initializes the sidecar in practice.
- Step 005: `search` treats an **empty** `kinds` collection as "no corpus matches" and returns `[]`
  (`None` remains "every kind"). The step file only defines `None`; returning everything for an
  explicit empty narrowing would be the surprising reading.
- Step 006: **the deferred vector-count guard is now in place on the incremental path too** — a batch
  that comes back with a different number of vectors than there were chunks is reported as
  `failed` / **`unreachable`**, never written. `unreachable` rather than a fifth reason because the
  frozen `IndexFailureReason` has exactly four members and this is the same "the call did not produce
  usable vectors" case `services/embedding.py:embed_text` already calls `unreachable` (step 004's
  note: an empty answer to a non-empty input). Both rebuild and incremental paths now refuse to
  `zip`-truncate.
- Step 006: `index_entry` does **not** pre-check `embedding.is_available()`. Step 004's docstring
  suggested it as the quiet-degradation probe, but `embed_batch` already raises `no_provider` before
  constructing any client, so the pre-check would only add a second designation lookup on every save
  — and it would let a *stubbed* embedder be skipped on the strength of an unconfigured db row. The
  no-provider outcome is produced by mapping the caught `EmbeddingError`, exactly as the skeleton's
  "maps across by value" note describes.
- Step 006: the dimension check is **skipped when `get_table_dimension()` is `None`** (no table
  yet) — the first upsert creates the table at the length of the vectors in hand, so there is nothing
  to disagree with. A mismatch against an existing table refuses the write and leaves the entry's
  **previous** chunks in place rather than deleting them: a stale chunk is better than none while the
  index waits for the rebuild the mismatch requires.
- Step 006: an entry that chunks to nothing (blank name and body) reports `dropped`, not `indexed`
  with zero chunks — it goes through `drop_entry`, so an emptied entry cannot leave its old chunks
  behind. The step file's "an entry with no chunks clears the index for that source" wording, applied
  literally.
- Step 006: the two `services/codex.py` call sites needed no edit — the skeleton had already landed
  them. Recorded here because the step file lists that file as in-scope and the diff for it is empty.
- Step 007: **UC-076's blank entry gets its mode inside `resolve_subject`, not from
  `determine_mode`.** The frozen `ResolvedSubject` carries `kind` / `entry` / `mode_key` only — there
  is no field for a blank entry's codex kind, and the frozen `determine_mode(subject)` is pure — so
  `determine_mode(ResolvedSubject(kind="codex-entry", entry=None))` is `None` by construction while
  `resolve_subject(access, "codex-entry", None, CodexKind.character)` is `"edit-character"`. Both
  functions share one private `_mode_for_codex_kind` map, so the two paths cannot drift. The
  alternative — synthesizing a transient `CodexEntry` for the blank case — was rejected: the frozen
  record documents `entry` as "the loaded row … `None` … for UC-076's blank entry".
- Step 007: `allowed_tool_names` does **not** de-duplicate. The `(mode_key, tool_name)` unique
  constraint on `mode_tool` makes a duplicate impossible today, and the step words the result as
  "exactly that mode's `mode_tool` rows' `tool_name` values"; `resolve_tools` sets the collection
  anyway, so a duplicate could not reach the tool definitions even if the constraint were dropped.
- Step 007: `_CODEX_KIND_MODES` is keyed by `CodexKind.<member>.value`, and `_mode_for_codex_kind`
  falls back to `str(kind)` for a non-enum value, so a row whose `kind` came back as a bare string
  still maps — step 006's "map across by wire value" rule, applied to the mode table.
- Step 007: a codex-entry subject naming an **archived** entry still resolves to that entry and its
  mode. Archiving is UC-072 (`017`), the step file says nothing about it, and the assistant's canvas
  write is refused by `010`'s server-side editability check rather than here.
- Step 008: because every synthetic name carries `DELEGATION_TOOL_PREFIX`, a collision with a **real**
  registry tool is only reachable if `TOOL_REGISTRY` itself ever gains an `ask_`-prefixed entry — the
  live collision in practice is synthetic-vs-synthetic (two sub-agent names that sanitise alike, e.g.
  `"Continuity Checker"` and `"continuity-checker"`). Both are guarded and logged the same way, the
  real tool always winning. If `012`'s editor ever wants to *prevent* the collision rather than
  observe it, the check belongs at sub-agent create/rename, not here.
- Step 008: a sub-agent carrying an `llm_server_id` with a **blank** `model_name` (or the reverse) is
  treated as **no assignment** and inherits the parent turn's server/key/model rather than failing.
  The step words the own-model case as "both set"; a half-set pair cannot construct a client, and
  inheriting is the behaviour US-113.AC-6 already defines for an unassigned sub-agent.
- Step 008: an assigned server that exists but is **inactive** counts as unusable and produces the
  error string, mirroring `prepare_turn`'s refusal of an inactive server for the parent turn. The
  step file names only "no longer exists or is unusable"; running a delegation on a server an admin
  has deactivated would be the surprising reading.
- Step 008: `run_delegation` catches `Exception` broadly (the `web_search` shape) rather than
  `chat_turn._TURN_FAILURE_EXCEPTIONS`' named four. The never-raise contract is absolute here — a
  raising tool aborts the **parent's** whole loop and the model never sees the error — so a failure
  mode nobody enumerated must still return a string. `asyncio.CancelledError` is a `BaseException` and
  still propagates, so a cancelled turn is not swallowed.
- Step 008: the nested call's tools are resolved in **`subagent_tool` row order**, not registry order,
  and are not de-duplicated — the `(sub_agent_id, tool_name)` unique constraint makes a duplicate
  impossible, and `build_tool_bindings` keys by name anyway. A sub-agent with **zero** tool rows runs
  its nested loop with no tools at all (`012`'s zero-rows rule, applied to the sub-agent side).
- Step 008: the nested call's return value is passed to the parent **verbatim**, including an empty
  string. `run_turn`'s "an empty result is a failure" rule (UC-056) is about the author-facing turn;
  the step file says only "return the nested call's final string", and inventing a second empty-result
  policy here would hide what the sub-agent actually answered.

### Step 009 (skeleton) — two feature-011 tests assert "the registry has exactly one tool"

**Step:** 009 — codex assistant tools. Raised by the skeleton; **needs an orchestrator/user ruling
before the red gate**, because no role in this step's pipeline may fix it.

**What intent asked for.** `009.codex-assistant-tools.md` → Interface intent: "**two new
`TOOL_REGISTRY` entries** — `codex_search` and the entry-read tool, both bound." DoD-12 asserts
"Both tools are present in `TOOL_REGISTRY`". Adding them is unavoidable and unambiguous.

**What conflicts.** Two tests shipped by feature `011.chat-panel` assert, as literal expectations,
that `TOOL_REGISTRY` holds exactly one entry. They fail the moment the two entries exist — before any
behaviour is implemented:

- `backend/tests/services/test_tools.py::test_registry_has_single_web_search_entry__DoD3` —
  `assert len(tools.TOOL_REGISTRY) == 1`. (The same file's other four assertions survive: `web_search`
  stays `TOOL_REGISTRY[0]`, and the context-free `build_tool_bindings(TOOL_REGISTRY)` still yields
  exactly one definition because a bound tool with no context is skipped.)
- `backend/tests/services/test_chat_turn.py::test_system_prompt_and_whole_registry_offered__DoD11` —
  `assert set(fake.call["tools"].keys()) == {t.name for t in TOOL_REGISTRY}` and
  `assert len(fake.call["tools_definitions"]) == len(TOOL_REGISTRY)` for a **null-mode** turn. Step
  007 already replaced "null mode ⇒ the whole registry" with `BASE_TOOL_NAMES`; this test only kept
  passing because the two sets coincided while the registry had one entry. `007.context.md` →
  "Backward compatibility gotcha" **predicted exactly this** ("the behaviour does not change until
  step 009 adds registry entries") but assigned no owner for the update, and `009`'s step file does
  not list either test file.

**Why a clean freeze is impossible.** The step's Test files are `backend/tests/services/
test_codex_tools.py` only; both failing files belong to feature 011 and are outside the skeleton's,
the test-coder's and the coder's write scope alike. Nothing in the source can make both assertions
true again without violating DoD-12. The two reds are therefore **inherited, not step-009 signal** —
the verifier must not read them as a coder fault.

**Suggested resolutions (tradeoffs).**

1. **Update the two assertions in place** (someone with test-file authority — orchestrator ruling, or
   a `/bug-fixer` pass against feature 011's `done` plan). `test_tools.py`: assert `web_search` is
   *present* with its args schema and callable, rather than that it is *alone*. `test_chat_turn.py`:
   assert the null-mode turn offers exactly `assistant_runtime.BASE_TOOL_NAMES` (which is what DoD-11
   means post-step-007) instead of the whole registry. **Cheapest and most truthful**; both tests keep
   their original intent and gain bite, and 011's DoD-3/DoD-11 stay covered. Recommended.
2. **Let the step-009 test-coder re-assert the clauses in `test_codex_tools.py` and let the two
   originals be deleted.** Loses feature 011's own coverage record and moves 011's DoD ids into a
   013 file — traceability cost for no gain.
3. **Leave both failing and annotate the verifier's expectation.** Keeps a red suite indefinitely and
   trains everyone to ignore two failures; a real regression would hide behind them. Not recommended.

Until it is resolved, the step-009 red gate should be read as: **`717 passed, 2 failed` is the
baseline**, and only failures outside those two names carry step-009 information.

### Step 009 (coder) — as-built notes

- Step 009: **a search hit whose authoritative row is missing or archived is dropped, not rendered.**
  The rendering needs the row anyway (the kind and the name are not in the index), so a stale hit has
  no kind to show; dropping it is also what keeps the two tools presenting the same world — the read
  tool refuses exactly those entries. A search whose every hit is stale therefore reads as the
  ordinary "nothing found" string, which is DoD-6's "empty **or stale** index" case.
- Step 009: **no de-duplication by entry.** Two chunks of one long entry can both hit and both render
  (each with its own matched passage), because the step words the output as "one block per hit" and
  the passages differ. If a later tune wants one block per entry, that is a formatting decision, not
  a contract change.
- Step 009: `limit` is re-clamped to `[0, MAX_SEARCH_LIMIT]` inside `codex_search` and re-applied to
  the rendered blocks, even though `CodexSearchArgs` already bounds it — the callable is reachable
  without the schema (a direct call), and the ceiling is a bounded-output property of the tool, not
  of its schema. **Still no minimum score anywhere**: UC-078's `_TBD:` (challenge C27) stays open.
- Step 009: the error strings are module constants with two deliberately distinct vocabularies —
  `"… error: …"` for a failure, a plain `No codex entries found for "<query>".` for the normal
  no-match outcome — so the model can tell "the codex has nothing" from "the codex could not be
  consulted" (`retrieval.md` → Failure modes, rows 1–4).
- Step 009: `codex_search` catches bare `Exception` around the embed, the sidecar query and the row
  reads (the `web_search` / step-008 `run_delegation` shape) rather than a named set. A raising tool
  aborts the whole parent loop and the error never reaches the model, so a failure mode nobody
  enumerated must still come back as a string. `asyncio.CancelledError` is a `BaseException` and
  still propagates, so a cancelled turn is not swallowed.
- Step 009: the read tool's not-found string embeds the **model-supplied** id verbatim and is
  identical for a malformed id, an unknown id and another book's entry — the three are
  indistinguishable from the model's side, so another book's entry is neither read nor confirmed to
  exist (US-085.AC-1). The archived refusal does name the state, but carries none of the entry's
  content.
- Step 009: the skeleton's flagged consequence stands unaddressed by design — `subagent_delegation.
  _delegate` still calls `build_tool_bindings` with **no** context, so a sub-agent selecting
  `codex_search` / `codex_read_entry` silently loses them (skipped and logged). Fixing it needs a
  `ToolContext` on `ParentTurn`, a step-008 signature change and a file outside this step's scope.
  **Resolved by step 010's skeleton** — see that step's `## Skeleton` block: `ParentTurn` gained a
  defaulted `tool_context` field, `run_turn` fills it and `_delegate` passes it through. Three
  mechanical lines, no behaviour change for any existing caller.

### Step 010 (skeleton) — one pre-existing test falsified, outside every role's write scope

**Step 010.** `TOOL_REGISTRY` gains its fourth entry (`write_codex_draft`), which the step file's
Interface intent requires ("one new bound `TOOL_REGISTRY` entry, `write_codex_draft`, mode-gated like
any other").

**What breaks.** `backend/tests/services/test_tools.py::test_registry_has_single_web_search_entry__DoD3`
asserts `{t.name for t in TOOL_REGISTRY} == {"web_search", "codex_search", "codex_read_entry"}` — the
pin step 009's test-coder wrote under the orchestrator's scope extension. It now fails. The file is
feature 011's coverage record; it is **not** in step 010's Test files
(`test_codex_canvas_tools.py` / `test_chat_turn_canvas.py`), so this step's test-coder may not touch
it, and the coder owns source only.

**Suggested resolution.** The same option 1 the step-009 collision took, for the same reasons: widen
the pinned set to the four names in place, keeping the test's intent (the catalogue is known and
pinned, not open-ended) and its other four assertions about `web_search` untouched. One line, granted
to whoever holds test-file authority. Options 2 and 3 from the step-009 entry carry the same costs
here.

Until it is resolved, the step-010 red gate baseline is **`733 passed, 1 failed`**, and only failures
outside that one name carry step-010 information.

### Step 010 (coder) — as-built notes

- Step 010: **a tool context carrying no `access` is not refused for collaboration mode.** The
  co-author/proposal branch needs both the role and the mode, and `ToolContext.access` is frozen as
  defaulted-`None`; refusing when it is absent would cost a legitimate draft and buy nothing, because
  the tool persists nothing and reveals nothing — the frame goes to the author's own editor and no
  farther. A real turn always carries one (`prepare_turn` puts it on the `TurnContext`), so the
  permissive reading is unreachable in production. The branch itself is `role == co_author` (not "not
  owner"), matching `services/codex.py:_require_writable_mode` exactly.
- Step 010: **a blank entry opened with no `codex_kind` at all** (kind `codex-entry`, no id, no mode
  key) has an *unknown* codex kind, so a `name` write is **allowed** — it is not a fact. The step
  refuses a name only for a fact, and refusing an unknown kind would block UC-076's blank
  character/location entry, which is the case the whole blank path exists for.
- Step 010: the whole callable sits inside one broad `except Exception` guard, so a **direct** call
  with an off-vocabulary `field` (which `WriteCodexDraftArgs` would have refused, but a direct
  caller bypasses) comes back as an error string rather than a `ValidationError` — the never-raise
  contract is absolute, and `CanvasFrame` construction is the one line inside the tool that can
  reject its input. `asyncio.CancelledError` is a `BaseException` and still propagates.
- Step 010: `_MODE_KEY_CODEX_KINDS` is a **local inverse** of
  `assistant_runtime._CODEX_KIND_MODES` rather than an import of it — `assistant_runtime` imports
  `services/tools.py`, which imports this module, so importing it back would be a cycle. Both maps
  are keyed by **wire value**, and both would have to be edited if a fourth codex kind ever arrives;
  that is the one drift risk the cycle forces.
- Step 010: two refusal/error vocabularies, as step 009 established for the search tool —
  `Codex draft refused: …` for a verdict that will read the same on every retry (not a codex entry,
  archived, proposal mode, a fact's name) and `Codex draft error: …` for a transport failure the
  model may reasonably retry (no emitter, a broken queue, an unexpected failure). The confirmation is
  neither and names the field written.

### Step 011 (skeleton) — three pre-existing frontend cases falsified, outside every role's write scope

**Step 011.** The three codex list routes stop rendering `SubjectPlaceholderPage`, which the step
file's Interface intent requires verbatim: "replace the three `SubjectPlaceholderPage` elements on
`/characters`, `/locations` and `/facts` with the list page bound to its kind".

**What breaks.** `frontend/tests/work/subjectRoutes.test.tsx` (feature `010.working-page`, DoD-5)
parameterizes one test over five list routes and asserts each renders, inside the content pane, an
empty state naming its owner folder. Three of its rows are now false by design:

- `["/bk-1/characters", /013\.codex/]`
- `["/bk-1/locations", /013\.codex/]`
- `["/bk-1/facts", /013\.codex/]`

They fail loudly at the red gate (the stub page throws on render) and would still fail once the coder
lands the real table, because the placeholder text they look for is gone for good. The file is
feature 010's coverage record; step 011's Test files are `frontend/tests/work/codexListPage.test.tsx`
only, so this step's test-coder may not touch it, and the coder owns source only.

**Suggested resolutions (tradeoffs).**

1. **Narrow the parameter table in place** — drop the three codex rows from `LIST_ROUTES`, leaving
   `/chapters` and `/variants` (both still placeholders). One edit, granted to whoever holds
   test-file authority (orchestrator ruling, or a `/bug-fixer` pass against feature 010's `done`
   plan). Feature 010's DoD-5 keeps its meaning — "a list route resolves into the content pane and
   does not 404" — for the routes it still owns, and the three codex routes' equivalent claim moves
   to step 011's own spec, where DoD-1 asserts something stronger (the right entries render).
   **Cheapest and most truthful; recommended.** The same file's `/codex/ce-1` item-route case stays
   untouched — that placeholder survives until step 012, which will falsify it in turn.
2. **Retarget the three rows** to assert the codex list surface instead of the placeholder. Keeps
   five rows but duplicates step 011's DoD-1 in feature 010's file, and re-breaks at step 012.
3. **Leave them failing and annotate the baseline.** Three permanent reds in the frontend suite; the
   step-009/010 entries above already argued why that trains everyone to ignore failures.

Until it is resolved, the step-011 frontend red-gate baseline carries **those three named failures**
in addition to the step's own reds, and only failures outside them carry step-011 information.

### Step 012 (skeleton) — one more pre-existing frontend case falsified, outside every role's write scope

**Step 012.** `/codex/:id` stops rendering `SubjectPlaceholderPage`, which the step file's Interface
intent requires verbatim: "point `/codex/:id` (already keyed `key={id}`) and the `/codex/new` route
reserved in step 011 at this page". Step 011's own note predicted this: "The same file's
`/codex/ce-1` item-route case stays untouched — that placeholder survives until step 012, which will
falsify it in turn."

**What breaks.** `frontend/tests/work/subjectRoutes.test.tsx` (feature `010.working-page`) still
carries one `/bk-1/codex/ce-1` case asserting the item route renders, inside the content pane, an
empty state naming its owner folder `013.codex`. That route now renders `CodexEntryPage`, whose stub
throws, and once the coder lands the real editor the placeholder text is gone for good. The file is
feature 010's coverage record; step 012's Test files are `frontend/tests/work/codexEntryPage.test.tsx`
only, so this step's test-coder may not touch it, and the coder owns source only. (`/codex/new` is
**not** at risk — step 011 added that route, so a feature-010 spec cannot reference it.)

**Suggested resolutions (tradeoffs).**

1. **Drop the `/codex/ce-1` row in place**, exactly as resolution 1 of the step-011 entry above did
   for the three list rows — one edit, granted to whoever holds test-file authority (orchestrator
   ruling, or a `/bug-fixer` pass against feature 010's `done` plan). Feature 010's claim ("an item
   route resolves into the content pane and does not 404") keeps its meaning for the routes it still
   owns (`/chapter/:id`, `/variants/:chapterId`), and the codex entry route's equivalent claim moves
   to step 012's own spec, where DoD-1 asserts something stronger (the entry's name and body render).
   **Cheapest and most truthful; recommended, and consistent with whatever was decided for step 011.**
2. **Retarget the row** to assert the entry-page surface. Keeps the row but duplicates step 012's
   DoD-1 in feature 010's file.
3. **Leave it failing and annotate the baseline.** One more permanent red; the step-009/010/011
   entries already argued why that trains everyone to ignore failures.

Until it is resolved, the step-012 frontend red-gate baseline carries **that one named failure** in
addition to the step's own reds (and whichever of step 011's three are still outstanding), and only
failures outside them carry step-012 information.

### Step 012 (coder) — as-built notes

- Step 012: **the server's refusal reason arrives NESTED at `details.detail`, not at `details`.**
  `src/api/client.ts:throwApiError` puts the **whole** JSON body into `ApiError.details`, and FastAPI
  wraps a handler's `detail` in a `{"detail": …}` envelope — so `routes/codex.py`'s
  `HTTPException(detail=CodexErrorDetail(reason=…, message=…))` reaches the client as
  `details.detail.reason` / `details.detail.message`. `serverRefusalText` therefore reads that nested
  object, and also handles the **plain-string** detail an authorization denial carries
  (`_map_authz_error`). The branch on the failure itself is on **`status`** only; no message text is
  parsed anywhere.
- Step 012: **Save is rendered disabled for an archived entry, not hidden.** The frozen `canSave`
  contract includes `!isReadOnly`, which would be dead code if the button were absent in exactly that
  case, so "the save action is unavailable" is implemented as a disabled control. The body and name
  inputs are `readOnly` (not `disabled`) so the text stays visible and selectable.
- Step 012: **a 409 leaves `saveStatus` at `"idle"` and `saveError` at `null`.** The reconciliation
  view *is* the warning (`frontend-workspace.md`: "the warning *is* the divergence view"), so raising
  a red save-error alert beside it would say the same thing twice and would survive into the editor
  after the author chose a side.
- Step 012: **a blank route with an unparseable or absent `?kind=` refuses the save locally**
  (`MISSING_KIND_MESSAGE`) rather than guessing a kind. Nothing in-app produces that address — the
  "New entry" button always supplies the kind — so it is a hand-edited-URL guard only.
- Step 012: the **name is not trimmed** before it is sent. Step 002's note records that the service
  stores a passing name exactly as supplied and only uses whitespace to decide presence/absence;
  local validation here trims only to *test* blankness. If the entry page should trim what it stores,
  that is still a later decision.
- Step 012: `resolveCodexConflict("draft")` re-enters `saveCodexEntry`, so a second 409 (a third
  author saved again in between) re-opens the reconciliation view rather than looping — the same path
  handles it, with `conflictEntry` refreshed.

### Step 013 (coder) — as-built notes

- Step 013: **the buffer fallback takes `body` frames only.** `restoreBuffer.ts`'s
  `BufferedDraft.draft` is a single string that `012.context.md` settled holds the **body**, so
  buffering a `field: "name"` frame's text would surface as the body when the author returns —
  corrupting the entry instead of restoring it. A targetless `name` frame is therefore dropped, the
  same way a targetless blank-entry frame is. This is one of the two behaviours the skeleton flagged
  as the coder's to settle. A `name` frame whose target **is** registered still applies normally.
- Step 013: **the fallback's `baseVersion` is inherited from whatever buffer already sits at that
  key**, and `""` when there is none — the dispatcher has no `modified_at` to hand and the registry
  carries none. In practice an entry created through step 002 always has a non-null `modified_at`,
  so a fallback write with no prior buffer reads as **stale** on return and routes the author into
  step 012's reconciliation view, which shows the buffered draft beside the server's text.
  `013.context.md` names that "the correct outcome, not a bug"; recorded here so it is not read as
  drift later.
- Step 013: the fallback key uses the literal `"codex-entry"` kind the step file and `013.context.md`
  both name, not `frame.subject_kind`. Every `canvas` frame this feature emits is about a codex entry
  (`write_codex_draft` is the only producer), and the buffer's semantics — a body draft versioned by
  `modified_at` — are codex-entry-specific. If a later feature emits a canvas frame for another
  subject kind, that mapping is a decision for the step that adds it.
- Step 013: **`canvasFrame` treats an ABSENT `subject_id` as malformed** and drops the frame, while an
  explicit `null` is UC-076's blank entry. Reading a missing id as `null` would silently route an
  existing entry's draft at a blank one.
- Step 013: `turnSubject()` is evaluated inside `sendChatTurn` / `retryChatTurn` at the call, not
  hoisted into a field or captured with the handlers, so a retry issued after the author navigated
  carries the subject they are on **now** — which is also why `ChatPaneState` still has no subject
  state of any kind.
