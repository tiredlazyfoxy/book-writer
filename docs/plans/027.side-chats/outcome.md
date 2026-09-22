# 027.side-chats — intended doc changes after ship

Planner section: the architecture, roadmap and product follow-ups this feature owes once it ships.
**The architecture for side chats is not yet written anywhere in `docs/architecture/`** — the design
was locked in `context.md` (decisions D-A … D-F) per the user's practice, so finalization applies the
list below rather than reconciling a few lines. Grouped by target file. `docs/architecture/`,
`docs/product/` and `docs/plans/roadmap.md` are read-only from this plan; the architect, `/roadmap`
and `/product-spec` apply their parts.

## `docs/architecture/domain-chat.md`

- **Header** — extend `**Realizes:**` with `FEAT-022 — UC-110, UC-111, UC-112, UC-113, UC-114,
  UC-115; US-135..US-141`. Reason: the entities now carry the side-chat columns.
- **`## Chat` table** — add the row `active_side_chat_id` — **nullable** int, no FK; non-null means a
  side chat is active and every new row is stamped with it. Reason: D-A.
- **`## ChatMessage` table** — add the row `side_chat_id` — **nullable** int, no FK; `NULL` = main
  line; rows sharing an id form one side chat. Reason: D-A.
- **New section `## Side chats (feature 027)`** — record with reasoning: (1) two columns, no table,
  no FK, and why (a side chat has no attributes of its own — its id is a grouping key, and a table
  would exist only to be joined); (2) **"finished" is derived**, never stored — a side chat is finished
  iff rows carry its id and it is not the pointer, so there is no `finished_at` to keep in step; (3)
  **existence** = pointer equals the id **or** a row carries it, which is what lets an empty active
  side chat be finished cleanly; (4) **contiguity by construction** (D-B) — `position` stays one flat
  ordinal, stamping plus one level means groups are always contiguous runs, and nothing checks or
  repairs contiguity; (5) **the first hard delete in the chat family and the second sanctioned
  exception to archive-only** (after FEAT-011's destroy) — scoped to `chat_messages` rows only, which
  is why US-140.AC-4 holds structurally; positions are not renumbered after a delete; (6) **the
  detail response and titling stay unfiltered** — history shows finished groups collapsed
  (US-138.AC-2, US-095.AC-2), a title derives from the whole chat.
- **"Archived, not destroyed" paragraph** — qualify: side-chat delete is the named exception; a chat
  itself is still archived, never destroyed. Reason: a reader applying the rule by default would
  refuse the delete.

## `docs/architecture/assistant-runtime.md`

- **New subsection under the turn** — `### The transcript filter for side chats (feature 027)`:
  the active side-chat id is **captured once at turn start** and used for three things (user-row
  stamp, assistant-row stamp including the retry path, the `list_transcript` history load with
  `WHERE side_chat_id IS NULL OR side_chat_id = ?`). Record the accepted edge: a finish from another
  tab mid-turn leaves the in-flight turn's rows stamped with the id captured at its start — correct,
  because those rows were in that side chat. Reason: D-C, D-D.
- **"Out of scope — still deferred"** — add the sentence: *"Feature 027 removed nothing from this
  list. A side chat is a **transcript filter** on the chat's own stored rows by one column — no
  retrieval, no ranking, no truncation, no selection — and therefore is not context assembly; and it
  changed no frame, no `TurnRequest` field, no composition layer, no tool, no gating and no
  delegation (product D3)."* Reason: this is the likeliest thing to be misread as context assembly
  shipping, exactly as memos were.
- **"The SSE frame vocabulary"** — one sentence: still seven frames; `DoneFrame.message` gained a
  field through `ChatMessageResponse`, not through the frame. Reason: D-E.
- **Chat titling pointer** — note that `chat_titling.py` deliberately reads the unfiltered
  transcript. Reason: D-C.

## `docs/architecture/frontend-workspace.md`

- **"Chat pane" parts table** — add `MessageRow.tsx` (one rendered message, extracted from
  `MessageList`) and `SideChatGroup.tsx` (a contiguous side-chat run: bordered block, header label,
  expand/collapse for finished groups, Inject and Delete controls). Reason: D-F.
- **New paragraph — side chats in the pane.** Record: (1) **grouping is a computed**
  (`renderedTranscript` over `renderedMessages`), a discriminated union of `message` / `sideChat`
  items built from contiguous runs — the component branches on `kind` and holds no grouping logic;
  (2) the active group is always expanded, a finished group collapsed by default with per-id
  expansion state, following the `expandedToolCallRows` pattern; (3) **one swapping header slot**
  `Start side chat` / `Finish side chat`, the Send / Stop shape; (4) **product D1 is enforced
  client-side only** — `sideChatActionsEnabled` is false while streaming, while a close turn is
  active, and while an action is in flight, phrased per the no-book-id rule ("is X active at all");
  (5) the delete confirmation is a plain `@mantine/core` `Modal` (`@mantine/modals` not installed),
  the `ChapterPage` close-confirm precedent; (6) `Collapse` / `Accordion` deliberately **not**
  introduced — conditional rendering; (7) the composer has **no** side-chat gate — US-137.AC-3 holds
  by construction, with a one-line hint while a side chat is active; (8) **the active side chat is
  server state**, so UC-114 / US-141 hold with no client persistence and `activeChat.ts` is
  untouched. Reason: D-F.
- **"Icon-only accessible names are a test contract"** — extend the list with `Start side chat`,
  `Finish side chat`, `Expand side chat`, `Collapse side chat`, `Inject side chat`, `Delete side
  chat`, and the `role="group"` / `Side chat` container.
- **Header** — extend `**Realizes:**` with FEAT-022's ids.

## `docs/architecture/authorization.md`

- **"Chats, per-author prompts and memos — four row-ownership rules" → the Chats paragraph** —
  add: the four side-chat routes ride the same `Chat.author_id` ownership check through
  `_resolve_owned_chat`; another author's chat is **404, never 403** on all four; no `Capability`
  member, no matrix row. Note this family's **first `DELETE`** and that it is the sanctioned side-chat
  delete, not a chat delete. Reason: D-D.
- **Header** — extend `**Realizes:**` with FEAT-022 / UC-110..UC-113 (the routed ones).

## `docs/architecture/backend/persistence.md`

- **"The additive-column seam"** — record `ADDITIVE_COLUMNS` entries **two and three**:
  `("chat_messages", "side_chat_id")` and `("chats", "active_side_chat_id")` (feature 027), with the
  note that both are nullable-only as the seam requires. Reason: D-A.
- **"DB import/export" → "Column additions still owe codec changes even when no table is added"**
  — add feature 027 as the second instance: two columns, both codecs extended, `TABLE_REGISTRY`
  unchanged (still 20 entries); a legacy archive without the keys imports as `None`. Reason: D-A.

## `docs/architecture/quick-reference.md`

- **`/api/books/{book_id}/chats` route table** — add the four rows (method, path, success code,
  response DTO, error reasons) from `context.md` → D-D, with the notes: registered after the static
  `model-options` route beside `turn` / `title`; `side_chat_id` is the wire string id, non-numeric →
  404; `DELETE` answers 204 no body; start with an empty main conversation is allowed; finish /
  inject / delete of an empty active side chat clears the pointer.
- **Chat error taxonomy line** — add `side_chat_not_found` → **404**; `side_chat_already_active`,
  `side_chat_not_active` → **409**.
- **Chats DTO table** — `ChatResponse` gains `active_side_chat_id: str | None`;
  `ChatMessageResponse` gains `side_chat_id: str | None` (both required-nullable on the frontend
  twin; both filled by the single service mappers). `TurnRequest`, `DoneFrame` unchanged.
- **Tables & enums** — `Chat` gains `active_side_chat_id`; `ChatMessage` gains `side_chat_id`;
  `ChatErrorReason` gains three members.
- **The intro's "Current through …" line** — add feature 027.

## `docs/architecture/CLAUDE.md` and `docs/architecture/README.md`

- **"Covered now"** — add feature `027.side-chats`: the two columns and the derived "finished"
  state (`domain-chat.md`), the capture-once transcript filter (`assistant-runtime.md`), the pane's
  grouping computed and controls (`frontend-workspace.md`), the four routes (`quick-reference.md`).
- **"Still not covered — do not infer it"** — add the one-sentence guard that side chats are a
  transcript filter, not context assembly (mirroring the FEAT-021 memos sentence). Reason: D-C.
- `README.md` — no new document was added; update the per-file one-liners for the five files above.

## `docs/product/` — follow-ups for `/product-spec` (not applied by the architect)

- **FEAT-022 status** — `proposed` → `delivered` at finalization, with
  `**Delivered:** docs/plans/027.side-chats/ (YYYY-MM-DD)`; the same for UC-110..UC-115 and
  US-135..US-141 in `docs/product/quick-reference.md`.
- **The D7 `_TBD:`** (what the collapsed header shows to tell finished side chats apart) is **still
  open**: this plan renders a **neutral placeholder** — `Side chat` for an active group,
  `Side chat · N messages` for a finished one — and decided nothing. Product should either confirm
  the placeholder or specify the label (first message excerpt, a title, a timestamp …); the change
  is one string in `SideChatGroup.tsx`.
- **US-095.AC-2** — note that a reopened chat's history now includes finished side chats
  **collapsed**; the criterion still holds.
- **FEAT-013's hosting note** — already says "hosted by FEAT-013"; nothing to add unless product
  wants the four actions listed there.

## `docs/plans/roadmap.md` — for `/roadmap`

- Add a row for `027.side-chats` (multi-step, FEAT-022, UC-110..UC-115, US-135..US-141; depends on
  `023.chat-ux-revision` and `024.chat-agent-loop`, which shaped the pane and the message mapper it
  extends). This feature was planned without a brief; the roadmap row is the missing bookkeeping,
  not a missing decision.

## Operating notes to carry into the docs

- **Existing installs pick up the two columns only through the seam's callers** (`create_database`,
  `import_all`) **or feature 007's admin schema-sync page** — never at startup
  (`backend/persistence.md`). A running instance upgraded to this build must run the sync before the
  first chat message, or every `chat_messages` / `chats` write fails. Same as feature `024`'s
  `tool_trace`; say it again where an operator will read it.

## Observations

- Step 001: `backend/features.md:95` calls `db/llm_servers.py::clear_all_embedding` "the **one** sanctioned raw `sqlalchemy.update()`" inside `db/`; `db/chat_messages.py::clear_side_chat` / `delete_by_side_chat` are now a second bulk raw `update()` and the first bulk raw `delete()`, scoped by `chat_id` + `side_chat_id`. Possible impact: reword the features.md line (and the `persistence.md` seam/codec notes) to "the first sanctioned…" and record 027 as the second instance of the same D5 reasoning.
