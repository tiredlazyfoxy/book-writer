# 027.side-chats — feature context

Feature-wide context. Step-specific facts live in each `<SSS>.context.md`; nothing is repeated
between the two files.

**This feature has no `brief.md`, and none is to be written.** `brief.md` is `/roadmap`'s file and
this feature was not roadmapped — `docs/plans/roadmap.md` carries no row for it either, which is
`/roadmap`'s to add (recorded in `outcome.md`). `context.md` is therefore the feature definition as
well as the shared context.

**Unlike `026.memos`, the architecture for this feature is NOT yet written in `docs/architecture/`.**
The design was settled in an `/architect` discussion with the user on **2026-09-20** and is locked
**here**, in the decisions below; `docs/architecture/` is reconciled at finalization from the list in
`outcome.md`. The user's practice on this project is exactly that — decisions bind from the plan, the
docs catch up after the ship. Every decision below is therefore **binding**, not a proposal. Where an
architecture document is cited it is cited for the rule it already carries (privacy, layering, the
additive-column seam), never for side chats, which it does not yet mention.

## Goal

**FEAT-022 — Side chats.** Let an author take a side task inside a composition chat — the brief's
example: creating a location while writing a chapter — with the whole conversation so far in view,
and return to the main task without the detour following them.

Backend: two nullable columns (no new table), a filtered transcript load in the turn, and four routes
in the existing chat family — start, finish, inject, delete — behind the existing chat-ownership rule.

Frontend: the chat pane groups a side chat's messages into one visibly set-apart block, collapses a
finished one to a header, and grows a Start / Finish control, per-group Inject / Delete controls, and
a delete confirmation.

## Product ids

**Delivered here:** FEAT-022 — UC-110, UC-111, UC-112, UC-113, UC-114, UC-115; US-135, US-136,
US-137, US-138, US-139, US-140, US-141 (18 acceptance criteria). Also touched, not owned:
**US-095.AC-2** (FEAT-013 — a reopened chat shows its full history; finished side chats appear in it,
collapsed) and **US-061** (FEAT-013 chat privacy — inherited unchanged, no new rule; product D6).

Two product `_TBD:`s sit on FEAT-022. **D7 — what the collapsed header shows to tell finished side
chats apart** — is **not decided here**: this plan renders a neutral placeholder, `Side chat · N
messages`, and `outcome.md` hands the question to `/product-spec`. **CS7 — the workaround's cost is
asserted, not evidenced** — needs nothing from a plan.

## Citation convention in this plan's DoD items

Every `[test]` DoD item cites the `US-###.AC-#` it verifies. Three kinds of item cannot, and say so
inline instead (the `026.memos` convention, kept):

- items realizing a **use-case step or postcondition with no separate AC** cite the `UC-###`;
- items enforcing a **decision below with no product criterion** (a `409` reason, a `404` for a
  foreign id, the capture-once rule) name the decision (`D-A` … `D-F`);
- items discharging an **infrastructural obligation** (the additive-column seam, the JSONL codec)
  name the root `CLAUDE.md` rule or `backend/persistence.md`.

## Vocabulary

| Term | Meaning |
|---|---|
| **Side chat** | a contiguous group of messages inside one chat, set apart from the **main line**. Never "subchat" |
| **Active side chat** | the one side chat currently receiving messages — at most one per chat (product C2, one level) |
| **Finished side chat** | a group that is no longer active; collapsed in the history, readable, not resumable (product C7) |
| **Inject** | its messages become ordinary main-line messages, in place, keeping order — one-way (product C6) |
| **Delete** | its messages are removed permanently (product C4, D8) — see D-D for why this is sanctioned |
| **Main line** | every message whose `side_chat_id` is `NULL` |

## Design decisions — binding (from the /architect discussion, 2026-09-20)

### D-A. Storage: two nullable columns, no new table, no FK

- `ChatMessage.side_chat_id: int | None` — a snowflake-shaped id minted with the existing `generate_id`,
  stored as `int` like every other id, serialized as a **string** on the wire. `NULL` = main line.
  Rows sharing an id form one side chat.
- `Chat.active_side_chat_id: int | None`. Non-null = a side chat is active and **every new row is
  stamped with that id**. `NULL` = main line.
- A side chat is **finished** iff rows carry its id and it is **not** the chat's
  `active_side_chat_id`. **No `finished_at`, no status column** — "finished" is derived.
- A side chat **exists** (for 404 purposes) iff `chat.active_side_chat_id == sid` **or** at least one
  message row of that chat carries `side_chat_id == sid`. The service combines the two; the `db/`
  helper answers only the row half.
- Both columns go through **`db/engine.py`'s `ADDITIVE_COLUMNS` seam** (`backend/persistence.md` →
  "The additive-column seam"): append `("chat_messages", "side_chat_id")` and
  `("chats", "active_side_chat_id")`, each with a `# feature 027` comment. Without this, **every
  INSERT on an existing install fails** — the outage feature `024` had. The seam compiles the SQL type
  from the model and is nullable-only, which these columns are.
- Both columns join the JSONL codecs in `services/db_import_export.py` **in the same step as the
  model change** (root `CLAUDE.md`): export `str(x) if x is not None else None` (the `llm_server_id`
  nullable-id pattern), restore via `data.get(...)` with `int(...)` when present — so an archive
  written before this feature imports as `None`. **No new `TABLE_REGISTRY` entry**: no new table.

### D-B. Contiguity by construction

`position` stays one flat ordinal per chat. While a side chat is active every new row — user and
assistant — is stamped with its id, and one level means no main-line row can land inside a group.
Groups are therefore **always contiguous runs** in the position-ordered array. The frontend groups by
contiguous runs of equal `side_chat_id`; **nothing anywhere checks or repairs contiguity.**

### D-C. Transcript filter in the turn (UC-115) — NOT context assembly

In `services/chat_turn.py::run_turn` the active side-chat id is **captured once at turn start** from
the resolved chat and used for exactly three things:

1. stamped on the **user row** insert;
2. stamped on the **assistant row** insert (the retry path — `prompt is None`, no user row — stamps
   the assistant row with the **same captured id**);
3. passed to the history load, which becomes the new
   `chat_messages.list_transcript(chat_id, active_side_chat_id)` — rows
   `WHERE chat_id = ? AND (side_chat_id IS NULL OR side_chat_id = ?)` ordered by `position`; with
   `None` it returns main-line rows only. The `{"role", "content"}` mapping after it is unchanged.

**State this plainly, because a reader will conflate the two: this is a transcript filter, not
context assembly.** `assistant-runtime.md` → "Out of scope — still deferred" keeps context / content
assembly, token-level streaming and token budgeting exactly where they are. Nothing here retrieves,
ranks, truncates or selects — it filters the chat's own stored rows by one column. **No change to
`TurnRequest`, to any SSE frame, to prompt composition, to tools, to tool gating or to sub-agent
delegation** — product D3 says a side chat changes what the assistant is told about the conversation
and nothing else, and the implementation is literally that.

Two callers keep the **unfiltered** transcript, deliberately:

- `services/chat_titling.py` (and `count_by_chat_and_role`) — a title derives from the whole chat,
  side chats included.
- `services/chats.py::get_chat` — the history shows finished groups collapsed, so the detail response
  carries **all** rows (US-138.AC-2, US-095.AC-2).

### D-D. Four routes, in `routes/chats.py` + `services/chats.py` — not a new module

Kept in the chat family so there is one `ChatError` / `ChatErrorReason` / `_CHAT_ERROR_STATUS`
taxonomy. All under `Depends(authz.book_access)`; ownership through the existing
`_resolve_owned_chat` → `chat_not_found` → **404 for another author's chat, never 403**
(`authorization.md` → "Chats, per-author prompts and memos"; `domain-chat.md` → privacy).

| Method | Path | Success | Errors |
|---|---|---|---|
| `POST` | `/api/books/{book_id}/chats/{chat_id}/side-chats` | `201` `ChatResponse` (pointer set) | `409 side_chat_already_active` if the pointer is not null |
| `POST` | `/api/books/{book_id}/chats/{chat_id}/side-chats/{side_chat_id}/finish` | `200` `ChatResponse` (pointer cleared; rows untouched) | `404 side_chat_not_found`; `409 side_chat_not_active` if it exists but is not the active one |
| `POST` | `/api/books/{book_id}/chats/{chat_id}/side-chats/{side_chat_id}/inject` | `200` `ChatDetailResponse` (rows' `side_chat_id` set `NULL`; pointer cleared if it was the active one) | `404 side_chat_not_found` |
| `DELETE` | `/api/books/{book_id}/chats/{chat_id}/side-chats/{side_chat_id}` | `204` no body (rows deleted; pointer cleared if it was the active one) | `404 side_chat_not_found` |

- **Three new `ChatErrorReason` members:** `side_chat_already_active` (409), `side_chat_not_found`
  (404), `side_chat_not_active` (409), added to `_CHAT_ERROR_STATUS`. The `409` idiom is the project's
  (`routes/books.py` archive / unarchive).
- `side_chat_id` is the wire **string** id; the service parses it. A **non-numeric** id is
  `side_chat_not_found` → 404 (the codex `entry_not_found` precedent), never FastAPI's 422.
- **Declaration order:** the four are static suffixes under `/{chat_id}/…`; register them alongside
  `turn` and `title`, after the static `model-options` route.
- **Start with an empty main conversation is allowed** (UC-110 alternate). Finish / inject / delete
  of an **active side chat with zero rows** just clears the pointer (inject `200`, delete `204`).
- **This is the first hard delete in the chat family and the second sanctioned exception to
  archive-only** (`docs/product/glossary.md`; FEAT-022 note, CS4, alongside FEAT-011's destroy).
  Delete touches **`chat_messages` rows only** — no other table is written, so anything saved during
  the side chat (a codex entry, a chapter change, a memo) is untouched **structurally** (US-140.AC-4).
  **Positions are not renumbered after a delete**; `next_position` = max+1 tolerates gaps (the
  chapters-DELETE precedent).
- **Every side-chat mutation goes through `db/chats.update(row)`**, which bumps `Chat.modified_at`
  itself — including inject / delete of a *finished* side chat where the pointer does not move, so
  the chat rises in the most-recently-modified list.
- **Product D1 (actions unavailable while the assistant is answering) is enforced client-side
  only**, like the close-turn read-only rule; the server holds no in-flight-turn state. **Accepted
  edge, recorded:** a finish reaching the server from another tab mid-turn leaves the in-flight turn's
  rows stamped with the id captured at its start (D-C), which is the correct outcome — those rows
  *were* in that side chat.

### D-E. DTOs

- `ChatResponse` gains `active_side_chat_id: str | None` (filled in `_to_chat_response`).
- `ChatMessageResponse` gains `side_chat_id: str | None` (filled in `_to_message_response` — the
  **single mapper** behind both the `done` frame and the reload, so the in-flight bubble and the
  reloaded row agree).
- The frontend `.d.ts` twins gain the same two fields as **required-nullable** (`string | null`), the
  file's convention.
- **No change to `TurnRequest`, `DoneFrame` or any SSE frame.**

### D-F. Frontend — the chat pane, `frontend/src/work/components/chat/`

- **`api/chats.ts`** gains four functions: start (POST, no body → `ChatResponse`), finish (POST, no
  body → `ChatResponse`), inject (POST, no body → `ChatDetailResponse`), delete (DELETE → `204`,
  resolves `void`). Trailing `signal?: AbortSignal`, through `client.ts`'s `request<T>`.
- **`ChatPaneState`** stays observables + computeds; every effect is an external
  `(state, args, signal?)` function using `runInAction`. New observables: `expandedSideChats:
  Record<string, boolean>`, `sideChatActionStatus: 'idle' | 'busy' | 'error'`, `sideChatActionError:
  string | null`, `sideChatDeleteConfirm: string | null` (the id awaiting confirmation). New computeds:
  `activeSideChatId` (from the active chat's `active_side_chat_id`), `canStartSideChat`,
  `canFinishSideChat`, `sideChatActionsEnabled` — all **false** while `turnStatus === "streaming"`,
  while `closeTurnActive !== null`, while `sideChatActionStatus === 'busy'`, or with no active chat
  (D1). Per `frontend-workspace.md`'s no-book-id rule, these are phrased "is X active at all", never
  "does X's book match".
- **Grouping is a computed, not component logic.** `renderedTranscript` over `renderedMessages`
  yields a discriminated union — `{ kind: "message", message }` for main-line rows and
  `{ kind: "sideChat", sideChatId, messages, active, expanded }` for each contiguous run sharing a
  `side_chat_id` (D-B). The active group is always `expanded: true`; a finished group reads
  `expandedSideChats[id] ?? false` — **collapsed by default** (US-137.AC-1).
- **Rendering.** The existing per-message JSX moves into `MessageRow.tsx` so the main line and a
  group render one component unchanged; `SideChatGroup.tsx` is the bordered block with a header
  (label, expand/collapse for finished groups, Inject and Delete icons); `MessageList.tsx` maps
  `renderedTranscript` and branches on `kind`.
- **Header control.** One slot before `New chat` showing **either** `Start side chat` **or** `Finish
  side chat` — swapping, like Send / Stop. Disabled by the matching computed.
- **Delete confirmation** is a plain `@mantine/core` `Modal` (`@mantine/modals` is **not**
  installed). Buttons: `Keep it` (dismiss) and `Delete side chat` (confirm).
- **Mantine inventory rule:** use only components already imported somewhere in the repo (`Paper`,
  `Box`, `Group`, `Stack`, `Text`, `ActionIcon`, `UnstyledButton`, `Tooltip`, `Badge`, `Modal`,
  `Button`, `Alert`). **Do not introduce `Collapse` or `Accordion`** — no in-repo precedent;
  conditional rendering is enough.
- **Icon-only `aria-label`s are test contracts**, as `Send` / `Stop` / `New chat` already are. This
  feature's names: `Start side chat`, `Finish side chat`, `Expand side chat`, `Collapse side chat`,
  `Inject side chat`, `Delete side chat`. The group container is `role="group"` with `aria-label`
  `Side chat` so a spec can find it by role and name, never by test id.
- **Label placeholder (product D7, undecided):** an active group's header reads `Side chat`; a
  finished group's reads `Side chat · N messages`. Neutral on purpose — see "Product ids".
- **`Composer.tsx` needs no gate change**: US-137.AC-3 holds by construction — a message lands in
  the active side chat or the main line, and a finished group has no composer of its own. The plan
  adds a one-line hint above the input while a side chat is active (`Replying in the side chat`), kept
  tiny.
- **`frontend/src/work/activeChat.ts`** (the per-book localStorage active-chat pointer) is
  **untouched and unrelated**: the active side chat is **server state on `Chat`**, which is exactly
  what makes UC-114 / US-141 hold across leave-and-return with no client persistence.

## Shared backend facts (steps 001–003)

- **Four-layer separation is enforced** (root `CLAUDE.md`, `backend.md`): `routes/` HTTP only;
  `services/` never touches `session` / `select()` / `session.exec()` / `session.add()`; `db/` is
  session-free, one module per entity, sessions created internally, ORM rows may be returned (the
  existing shape); `models/` has no logic. Namespace imports: `from app.db import chat_messages`.
- **Ids are minted by the model's `default_factory` / `generate_id`**, never by `db/`. The side-chat
  id is minted in the **service** at start (`generate_id()`), since no row is created for it.
- **Typed errors only.** `ChatError(reason, message)` from `services/chats.py`;
  `routes/chats.py::_map_chat_error` → `HTTPException(status_code=_CHAT_ERROR_STATUS[reason],
  detail=err.message)`.
- **Ownership:** `services/chats.py::_resolve_owned_chat(access, chat_id: int) -> Chat` raises
  `ChatError(ChatErrorReason.chat_not_found, "Chat not found.")` when the chat is missing, belongs to
  another book, or belongs to another author. `_parse_chat_id` turns the wire string into an int.
  Both are used unchanged by every new service function.
- **`db/chats.update(row: Chat) -> Chat`** takes the mutated ORM row, sets `modified_at` itself, and
  add / commit / refreshes. It is the single write path for the pointer.
- **New `db/chat_messages.py` functions** (defined in step 001, consumed in 002 and 003):
  `list_transcript(chat_id, active_side_chat_id)`, `side_chat_exists(chat_id, side_chat_id) -> bool`,
  `clear_side_chat(chat_id, side_chat_id) -> int`, `delete_by_side_chat(chat_id, side_chat_id) -> int`.
  Responsibilities are in `001.side-chat-columns.md` → Interface intent.
- **Pydantic `BaseModel` for every DTO; every id is `str` on the wire**; DTOs are built by the service
  mappers, never dumped from the ORM.

## Shared frontend facts (steps 004–007)

- **MobX only** (`frontend.md`): `observer` on every component; state = observable data + `get`
  computeds; effects are external `(state, args, signal?)` functions with `runInAction` before and
  after each await; **no custom hooks, no `useCallback` / `useMemo` / `useReducer`, no React
  context, no `useForm`**. `useState` only for a stable state instance; `useEffect` only at page
  level — `MessageList`, `SideChatGroup`, `MessageRow`, `ChatPane` hold **none**.
- **The backend is the source of truth**: after any side-chat write the pane shows what the server
  returned (patch `state.chats` by id with the returned chat; swap `state.messages` whole from the
  response or a `getChat` reload). `ApiError` is swallowed into `sideChatActionError`; anything else
  rethrows.
- **All HTTP in `src/api/`**; `.d.ts` in `src/types/` is wire-exact `snake_case`, ids `string`, no
  `any`.
- **`ChatPaneState` seeding in specs**: `runInAction` over `chats`, `activeChatId`, `messages`,
  `messagesStatus`, `turnStatus` — the existing pane specs' idiom. `activeChat` is a computed over
  `chats[]` + `activeChatId`, so setting the active chat's `active_side_chat_id` in `chats[]` is how a
  spec makes a side chat active.

## Testing facts shared by every step

**Backend (001–003)** — `asyncio_mode="auto"`; `backend/tests/conftest.py` provides `db` and
`http_client`. **No shared factory module** — every test module defines its own local helpers, copied
from a sibling. Route tests use real JWTs: `backend/tests/routes/test_chats.py` is the sibling to copy
from — `_seed_author(username) -> (User, token)`, `_seed_private_book(owner_id)`, `_add_co_author`,
`_chats_url(book_id)`, `_create_chat(http_client, token, book_id, **body) -> dict`,
`_auth_header(token)`; a message is seeded with
`chat_messages.create(ChatMessage(chat_id=int(chat["id"]), role="user", content="hi", position=0))`.
**No network in any test** — the LLM client is faked: `backend/tests/services/test_chat_turn.py`'s
`_install_client(monkeypatch, fake)` monkeypatches `app.services.llm_servers.create_model_client`,
and `_FakeClient.chat_with_tools` captures the outgoing message list in `fake.call["messages"]`.
**That capture is how every "a fact stated only in X is / is not available to the turn" criterion is
tested** (US-136, US-138, US-139): seed rows, run a turn, assert on the captured messages' contents.
Naming: `test_<behaviour>__DoD<N>`. **All new backend tests go in new files** so existing specs are
untouched and Test files stay disjoint from Source files.

**Frontend (004–007)** — `frontend/vitest.config.ts` is jsdom with `globals: false`: import
`describe` / `it` / `expect` / `vi` from `"vitest"`. Specs **mock the `api/` module wholesale, never
`fetch`** — `vi.mock("../../src/api/chats", () => ({ …every export…: vi.fn() }))`; **any spec that
imports the chats api module must list the four new functions in that factory object**, or the
import is `undefined` at call time. Render through `renderWithProviders` from
`frontend/tests/support/render.tsx`. Query **by role and accessible name only; never test ids**.
`ApiError` is imported real from `../../src/api/client`. Existing pane specs live in
`frontend/tests/work/` (`ChatPane.test.tsx`, `ChatConversation.test.tsx`, `Composer.test.tsx`,
`chatStreaming.test.ts`); **new specs go in new files there.**

## Build and test gates (root `CLAUDE.md` — referenced, not duplicated)

- **Backend steps 001–003:** `cd backend && .venv/Scripts/python -m pytest`. No separate backend
  typecheck exists — do not invent one.
- **Frontend steps 004–007:** `cd frontend && npm run build` (= `tsc && vite build`),
  `cd frontend && npm test`, `cd frontend && npm run test:types` (the only program covering `tests/`).

## Steps

| Step | File | Layer |
|---|---|---|
| 001 | `001.side-chat-columns.md` | backend — two columns, the additive seam, four `db/` functions, the JSONL codec |
| 002 | `002.turn-filter-start-finish.md` | backend — DTO fields, capture-once transcript filter in the turn, start + finish routes, the three error reasons |
| 003 | `003.side-chat-inject-delete.md` | backend — inject + delete routes |
| 004 | `004.side-chat-api-and-grouping.md` | frontend — `.d.ts` fields, four api functions, `RenderedMessage.sideChatId`, `renderedTranscript` grouping, expand/collapse state |
| 005 | `005.side-chat-actions-state.md` | frontend — action status, the three `can…` computeds, the four effect functions, delete-confirm state |
| 006 | `006.side-chat-group-rendering.md` | frontend — `MessageRow.tsx` extraction, `SideChatGroup.tsx`, `MessageList.tsx` branch |
| 007 | `007.side-chat-pane-controls.md` | frontend — Start / Finish slot, delete `Modal`, error `Alert`, composer hint |

Dependency order is the numeric order. Steps 004 and 005 both edit `chatPaneState.ts`, forward-only:
004 adds the grouping half, 005 adds the action half on top of it. Step 006 renders 004's computed and
binds 005's action functions; step 007 binds 005's `can…` computeds and confirm state.

**Deviation from the briefing's suggested seven, recorded:** the briefed "DTO + turn filter" step
was ~30 LoC (under the 50-line floor) and is merged into start/finish as step 002; the briefed
"api + state" step was ~180 LoC (at the ceiling) and is split into 004 / 005. Still seven steps.

## Out of scope — state it, do not build it

| Excluded | Owner |
|---|---|
| Context / content assembly, token budgeting, token-level streaming | still deferred — `assistant-runtime.md` → "Out of scope"; D-C is a transcript filter, not this |
| Any change to `TurnRequest`, any SSE frame, prompt composition, tools, tool gating, delegation | nobody — product D3, decision D-C |
| Nested side chats (a side chat inside a side chat) | nobody — product C2, one level |
| Resuming a finished side chat | nobody — product C7; a new topic is a new side chat |
| A `finished_at` / status column, a `side_chats` table, an FK | nobody — decision D-A |
| Contiguity checks or repair, position renumbering after delete | nobody — decisions D-B, D-D |
| Server-side "assistant is answering" gating of side-chat actions | nobody — D1 is client-side (D-D) |
| Filtering the titling transcript or the detail response | nobody — decision D-C |
| Deciding the collapsed header label (product D7) | `/product-spec` — placeholder used |
| A `Capability` member or `_CAPABILITY_MATRIX` row | nobody — rides `Chat.author_id` ownership |
| `Collapse` / `Accordion` from Mantine, `@mantine/modals` | nobody — no in-repo precedent |
| Editing `docs/product/`, `docs/architecture/` or `docs/plans/roadmap.md` | `/product-spec`, `/architect`, `/roadmap` |
