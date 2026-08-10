# Outcome — fast/007.codex-create-from-chat

Intended `docs/architecture/` changes, for `/architect` to apply at finalization. Seeded from
`docs/.cache/fast/007.codex-create-from-chat/design-notes.md` (D1–D8) and `plan.md`. Nothing
here is applied by the coder — `docs/architecture/` stays read-only through this feature, and
`docs/product/` is never edited from here at all.

**The headline item is a retraction, not an addition.** Two documents currently state, as a
structural guarantee, that no chat → codex write path exists. This feature creates one, on
purpose. Both passages must be rewritten with the reasoning, not merely corrected.

## `docs/architecture/assistant-runtime.md`

- **Section "The shared-canvas write for codex, as built" — the structural claim is
  retracted.** It currently reads: "**There is no chat → codex write path, by
  construction.** US-086.AC-2 / US-087.AC-2 / US-088.AC-2 hold **structurally, not by a
  check**: no code path exists from a chat turn to the `codex_entries` table… 'Nothing
  persists until saved' is normally an assertion about a check; here it is a structural
  property, **and that is worth more than the check would be** — a check can be bypassed by a
  later code path, an absent dependency cannot." Rewrite to say that there is now **exactly
  one deliberate chat → codex write path**, `create_codex_entry`, and to carry all of:
  - it is a **create only** — the canvas draft path (`write_codex_draft`) is unchanged and
    still persists nothing, so "nothing persists until saved" remains true of *that* path and
    of every edit;
  - the guard is **prompt-level by the author's explicit decision** (D1) — the tool's
    `description` instructs the model to call it only on the author's direct request, and mode
    gating bounds where it exists. **Nothing in the system verifies that the author commanded
    it**; the model decides whether it was asked. State that plainly, as a decision with an
    owner, the same category as feature `024`'s seeding reversal;
  - the alternatives rejected by the author and why they were structural: propose-and-confirm
    (a card in the transcript with a Create button, ~400–500 LoC — the recommendation, refused
    as one click after asking) and arm-the-turn (a composer flag on `TurnRequest`, ~300 LoC —
    refused as one click before asking);
  - the **structural backstops that replace the absent dependency**: a per-turn creation cap
    of 3 held on `ToolContext`, and a duplicate-name refusal for `character` / `location`
    over `list_by_book(..., include_archived=True, needle=…)` plus an exact trimmed
    case-insensitive comparison. Record **why** they exist: archiving is not built
    (`017.codex-archive-restore` is unbuilt, `013.codex` shipped no `DELETE`), so the failure
    mode is not "a wrong entry" but "a wrong entry that stays";
  - the accepted limits: **facts cannot be de-duplicated** (a fact has no name, and comparing
    bodies is not a duplicate test), and **an already-open codex list page does not refresh**
    (`frontend.md` forbids cross-page callbacks and a shared store; the entry appears on the
    list's next visit).

  Reason: the retracted sentence is the single most load-bearing claim in this section, and a
  reader who trusts it will build the next feature on a guarantee that no longer holds.

- **Same section — the "two implementations, deliberately" paragraph needs a boundary
  sentence.** `_refuse_write` is the assistant's server-side mirror of the frontend's
  editability rule, and its first link refuses a non-codex subject. Record that
  `create_codex_entry` **deliberately does not reuse that chain** (D7): it is the first codex
  tool whose target is the **book** (`ToolContext.book_id`) rather than the resolved subject,
  because running while the subject is a chapter is the entire point of the feature. It has
  no second implementation of the write rules either — it delegates to
  `services/codex.py:create_entry`, so the capability check, the proposal-mode refusal, the
  name/fact rule and the vector indexing stay in one place (D4).

- **Section "Tool gating" → case 1.** The sentence listing the codex modes' seeded default
  set — "the codex modes (`edit-character` / `edit-location` / `edit-fact`) resolve by
  default to `web_search`, `codex_search`, `codex_read_entry` and `write_codex_draft`" — is
  now four tools out of five. Update it, and note that `write-chapter`'s seeded set grows by
  the same entry while `close-chapter`'s is unchanged. **The gating rule itself is unchanged**
  — a mode an administrator has edited down to zero rows still gets an empty allowlist.

- **Same section — record that seeded defaults reach fresh installs only, as a general
  fact.** Both seeding functions are idempotent **per mode, not per row**
  (`seed_default_modes` writes a mode row only if none exists; `seed_default_mode_tools`
  skips a mode with any row), so a newly defaulted tool never reaches an already-seeded
  database. `create_codex_entry` therefore **ships unreachable on every existing
  installation** until an administrator adds it to the four modes in
  `012.assistant-config-editor` (D3). Record the rejected alternative — topping each mode up
  with missing default tools on boot — and why: it would restore a tool an admin deliberately
  removed, on every restart, which is the property the current design exists to protect. This
  is the general shape of the roadmap's "Delivered is not the same as reachable", and it will
  recur for the next defaulted tool.

- **Section "The as-built modules" / the `services/codex_tools.py` row.** It reads "the first
  mode-gated tools, including the shared-canvas write". Widen it to name the create tool as
  well — this module now holds the system's **first tool that writes a database row**, a
  category no tool occupied before.

- **Section "The close-chapter procedure, as built" (or "Tool gating", wherever it reads
  best) — why `close-chapter` is excluded** (D6). A close run is the least supervised turn in
  the system: it already drafts summaries, may replace the book's live note set, may raise
  flags and may end with the chapter `closed`. Giving it a tool that mints codex entries is
  the runaway case the per-turn cap exists to bound, so the tool is **not** seeded there.
  Record it as a bounded exclusion, so the next reader does not "fix" the omission.

- **Section "Tool-call visibility (feature `024`)" — one sentence.** No SSE frame was added
  (D8): the generic wrapper already emits `tool_call` / `tool_result` around every bound tool
  and persists the pair to `ChatMessage.tool_trace`, so the author's audit trail of what was
  created, with which arguments, exists for free and survives a reload. This is the first
  feature to *rely* on that property rather than merely benefit from it — a database write
  whose only author-facing record is the generic trace.

- **`ToolContext` gained a seventh field.** The document records the sixth
  (`active_notes_proposal`, feature `016`) with the reasoning that `ToolContext` is
  constructed once per turn in `run_turn` and is therefore the natural home for per-turn
  state. Add the creation counter on the same reasoning, and note that `chat_turn.py` needed
  no change because the field is additive and defaulted.

## `docs/architecture/domain-codex.md`

- **Section "Codex authoring from the chat (FEAT-018)" — the same retraction, from the domain
  side.** It currently ends: "Because there is no code path from a chat turn into
  `codex_entries`, 'nothing persists before the save' is a **structural property, not a check
  that could be forgotten**." Rewrite to record that a **second, deliberate** chat-side path
  now exists — an author-commanded **create** — while keeping the FEAT-018 statement intact
  for the path it describes: the canvas draft still persists nothing, and a *draft* still
  becomes an entry only through UC-069 / UC-070. Carry the domain-side facts: collaboration
  mode applies unchanged (a co-author in a `proposal`-mode book is refused, via the same
  `services/codex.py` rule), the name/fact rule applies unchanged (US-078.AC-2), the create
  writes **no** version row (as every create does not), and the duplicate-name refusal is a
  **tool-level** rule only — the human-facing `POST /books/{book_id}/codex` is unchanged and
  no DB constraint was added.
- **Section "Archiving itself is not built" — add the consequence this feature depends on.**
  Because an entry cannot be archived or deleted, a model-created entry that should not exist
  can be edited but never removed. That is the stated reason the cap and duplicate refusal
  exist, and it is a reason that **expires** when `017.codex-archive-restore` ships — worth
  writing down so the next reader knows which constraint is permanent and which is temporary.
- **Header `**Realizes:**` line.** FEAT-018's entry currently reads "(UC-076, UC-077 — the
  save path only)". This feature adds a flow with **no product id at all** — see the
  product-layer note below. Do not invent one; if the header needs a marker, name it as
  unmapped and point at that note.

## `docs/architecture/assistant-config.md`

- **Section "Tool registry — code-defined, not a table" → "Registry membership as
  shipped".** It lists `web_search` plus the codex three. Add `create_codex_entry` as a
  fourth codex tool defined in `services/codex_tools.py`, **context-bearing** (it needs the
  book and the access from the per-turn `ToolContext`), and note what makes it different from
  every entry before it: it is the **first registry tool that performs a database write**.
  The registry shape, the `ToolDef` fields and the "only selections persist" stance are
  unchanged.
- **Section "Validation at the config edge"** — no change of rule, but worth one clause: a
  tool added to `TOOL_REGISTRY` becomes selectable in the admin editor immediately (`GET
  /tools` reads the live catalogue), which is precisely the mechanism D3's manual step uses.

## `docs/architecture/backend/features.md`

- **Section "The codex route family".** The route surface is unchanged — no endpoint was
  added, and the four endpoints and their status taxonomy stand. Add a short record that the
  family gained an **assistant-side writer**: `services/codex_tools.py`'s
  `create_codex_entry`, which reaches `services/codex.py:create_entry` — the same function
  `POST /books/{book_id}/codex` calls — so the capability check, proposal-mode refusal,
  name/fact rule and vector indexing have one implementation and the HTTP taxonomy is
  unaffected (the tool answers in strings, never statuses). Note the two tool-only rules that
  do **not** exist on the route: the per-turn cap and the duplicate-name refusal.
- **Section "The chapter writing surface" → the "four `TOOL_REGISTRY` additions" sentence and
  the "Deliberate absences" list** — leave both as they are; this feature adds no endpoint,
  no table, no codec and no migration. State that explicitly in the new record so a reader
  does not go looking for an `ADDITIVE_COLUMNS` entry: **no new column, no new table.**

## `docs/architecture/quick-reference.md`

- **`/api/books/{book_id}/codex` (feature 013) section** — add a bullet in the shape the
  chapter and close families already use ("Four chapter tools joined `TOOL_REGISTRY`…",
  "Five close tools joined `TOOL_REGISTRY`…"): **`create_codex_entry` joined
  `TOOL_REGISTRY`** (`services/codex_tools.py`), mode-gated, seeded onto `edit-character` /
  `edit-location` / `edit-fact` / `write-chapter` **on fresh installs only** and **not** onto
  `close-chapter`; the **first registry tool that writes a row**; guarded by its description
  plus a per-turn cap of 3 and a duplicate-name refusal for named kinds. Point at
  `assistant-runtime.md` for the reasoning.
- **`ToolContext` field count.** The feature-016 bullet records "`ToolContext` gained a
  **sixth** field, `active_notes_proposal`". Add the seventh — the per-turn codex-creation
  counter, mutated in place, defaulted to zero, scoped to a turn because `run_turn` builds
  one context per turn.
- **No frame table change and no DTO table change** — no SSE frame was added and no wire DTO
  was reshaped. Worth stating in the applied record so the absence reads as deliberate.

## `docs/architecture/CLAUDE.md`

- The "Covered now" paragraph names the shipped features and the assistant split. If it is
  updated for this feature at all, the only substantive change is that
  **`assistant-runtime.md` no longer claims a structural absence of a chat → codex write
  path** — that is the sentence a reader of the index would otherwise carry away wrong.

## Product-layer note for `/product-spec` (planner-owned; **not** an architecture change)

Placed here rather than in `## Observations` because it is known at planning time, not
discovered during implementation. `## Observations` below stays the coder's.

**Nothing in `docs/product/` specifies creating a codex entry directly from a chat turn.**
FEAT-018 (UC-076, UC-077; US-086, US-087, US-088) specifies the **canvas draft** path and
states the opposite postcondition for it — nothing is added to the codex before the save
request. Read strictly, **US-088.AC-2 is scoped to "a drafted or rewritten entry shown in the
chat"**, so an author-commanded create is a **new flow rather than a contradicted
criterion**. Two things are nevertheless owed to the product layer:

1. **A use case and a story are missing** for author-commanded codex creation from a chat
   turn — including what "directly commanded" means as an acceptance criterion, which is
   exactly the thing this feature's guard cannot verify.
2. **FEAT-018's structural language needs revisiting** in the light of a shipped chat → codex
   write path.

**Never edit `docs/product/` to close this.** Surfacing it is the orchestrator's follow-up;
closing it is `/product-spec`'s. The architecture retraction above is the only doc change
this feature owns.

## Accepted limitations to record wherever they land best

1. **The open codex list page does not refresh.** A newly created entry appears on the list's
   next visit. Fixing it would need a cross-page refresh mechanism that `frontend.md`'s
   stated conventions forbid, for a case the author resolves by navigating.
2. **Facts cannot be de-duplicated.** A fact has no name (US-078.AC-2) and comparing bodies
   is not a duplicate test.
3. **The tool is unreachable on existing databases** until an administrator selects it for
   the four modes — the per-mode seeding idempotency above.

## Observations

- A bound tool's enum-typed argument can arrive as the **plain wire string**: the `llm` client
  decodes the tool call's JSON and dispatches `func(**kwargs)`, validating only the parameter
  *names* against `inspect.signature`, so the `args_schema` never actually runs on the way in.
  `create_codex_entry` therefore normalizes `kind` to `CodexKind` itself before comparing it or
  filtering on it. Possible impact: state this once in `assistant-runtime.md` (tool-callable
  binding) as a rule for every bound tool with a non-`str` argument — the schema is what the
  model is *told*, not what the callable is *guaranteed*.
- `services/codex.py:create_entry` returns a `CodexEntryResponse` DTO, not the `CodexEntry`
  row, so the tool's confirmation string carries the DTO's already-stringified id — which is
  the same id form `codex_search` / `codex_read_entry` speak, so the model can read the created
  entry straight back. Possible impact: a clause in `assistant-runtime.md`'s create-tool
  paragraph, noting the id vocabulary is consistent across the four codex tools.
- `db/mode_tools.py:DEFAULT_MODE_TOOL_NAMES` keeps each mode's tuple in
  `services/tools.py:TOOL_REGISTRY` order; the new entry was placed to preserve that. Possible
  impact: one sentence in `assistant-config.md` under the registry section, so the next
  defaulted tool is inserted rather than appended.
