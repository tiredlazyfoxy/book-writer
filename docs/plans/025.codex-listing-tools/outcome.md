# Feature 025 — outcome

Intended documentation changes, to be applied by the **architect** at finalization. The planner does
not touch `docs/architecture/`; this file is the hand-off.

## `docs/architecture/assistant-config.md`

**Section: "Tool registry — code-defined, not a table"**
Change: the `ToolDef` sketch gains a **`group : str`** member — required, no default, positioned
after `args_schema` and before `callable` / `binder`. Record the reasoning: the group is declared at
the **definition site** rather than mapped in the frontend, so a tool added later cannot silently
miss a group, and so the contract stays typed on both sides (no free dicts backend, no `any`
frontend). Note the three stable machine keys `"codex"` / `"book"` / `"web"`, and that **display
labels never cross the wire** — the frontend owns them, following the `MODE_LABELS` precedent.
Reason: the registry shape is this document's, and the required-field decision is the part a future
tool author must not have to rediscover.

**Section: "Tool registry — code-defined, not a table" → registry membership**
Change: membership grows from 14 to **18** entries. The codex set is now `codex_search`,
`codex_read_entry`, `write_codex_draft`, `create_codex_entry` **plus** `codex_list_entries`,
`codex_list_characters`, `codex_list_locations`, `codex_list_facts` — four **context-bearing,
no-argument** listing tools returning a **short form** (id + name, or id + a 60-char body excerpt for
an unnamed entry), with the full text reached only through `codex_read_entry`. Record the two user
decisions: **four distinct names rather than one tool with a `kind` argument** (easier for a weak
model to pick), and **no cap and no pagination** (completeness chosen over the context-flooding
risk).
Reason: the catalogue inventory lives here and is currently stated as the `011`/`013` set.

**Section: "The admin route surface"**
Change: note that `ToolResponse` **widened by one field** (`group`), that `GET /tools` now carries it
for every tool in declaration order, and that the admin picker renders the catalogue **grouped by
that key** — headings are plain text, the grouping is purely visual, and an unrecognised group falls
into a trailing **Other** bucket rather than being dropped.
Reason: the DTO and endpoint taxonomy is this document's; `quick-reference.md` carries the table.

## `docs/architecture/assistant-runtime.md`

**Section: "Tool gating", case 1 (the seeded-defaults paragraph)**
Change: the seeded default tool set for `edit-character` / `edit-location` / `edit-fact` now also
includes the four `codex_list_*` tools, and `write-chapter`'s seeded set gains them too.
`close-chapter` is unchanged.
Reason: this paragraph names the seeded starting state tool by tool; leaving it at feature `024`'s
list would misdescribe a fresh install.

**Section: "A lore list resolves to its entries' mode" (or a new short subsection beside it)**
Change: record that the assistant can now **enumerate** the codex, not only search it — the gap that
made "who is in this book" unanswerable and made duplicate creation likely. Record the
**`seed_default_mode_tools()` consequence**: its idempotency unit is the **mode**, not the row, so on
an **existing** database the four tools are registered but selected in no mode until an admin ticks
them. This was chosen over a per-`(mode, tool)` additive backfill because a backfill could
**resurrect a tool an admin deliberately removed**.
Reason: a decision with an owner, and an operating step a reader of a live instance will otherwise
report as a bug.

**Section: system-prompt composition / seeded prompts (wherever the seeded mode prompts are
described)**
Change: note that `DEFAULT_MODE_SYSTEM_PROMPTS` for the three `edit-*` modes and `write-chapter` now
name the listing tools, and that — like the tool seeding — this reaches **fresh installs only**;
existing `AssistantMode` rows keep their stored prompt.
Reason: same fresh-install-only reach, same misreading risk.

## `docs/architecture/quick-reference.md`

**Section: the assistant-config DTO table**
Change: `ToolResponse` gains **`group: string`** alongside `name` and `description`. Its hand-written
frontend twin `AssistantTool` matches.
Reason: this file is where concrete DTO shapes live instead of being repeated into the design docs.

## Follow-up for `/product-spec` (not an architecture edit)

The codex **listing** capability has **no `US` / `UC` id**. It should be recorded in
`docs/product/`, following the precedent set after feature `024` (US-120 / US-121 / US-122 were
recorded to product once the feature shipped). The closest existing ids — FEAT-017/UC-071,
FEAT-013/UC-078, FEAT-018, FEAT-020/UC-095/UC-096/US-111 — are **context, not deliveries**, and this
feature does not claim them.

`docs/plans/roadmap.md` is stale (it lists neither `023` nor `024`) and was **deliberately not
edited** by this feature.

---

## Observations

Recorded during the ultra-track conversion (2026-09-15), when this feature was re-shaped from three
step files into one plan. Not new architecture decisions — findings that correct or sharpen the
original planning round; kept here so they are not lost with the deleted step files.

- **The step-track plan's "preserve verbatim" empty-catalogue strings were truncated.** It instructed
  preserving `"This mode will run with no tools."` / `"This sub-agent will run with no tools."` —
  those are substrings. The real literals, now the plan's contract, are `"No tools are available to
  select. This mode will run with no tools."` and `"No tools are available to select. This sub-agent
  will run with no tools."` A coder following the old wording literally would have truncated a
  user-visible message — a silent regression in the exact place the `ToolPicker` extraction was meant
  to protect against.
- **The "zero-field args schema" interface risk was void, not open.** The original plan carried a
  block-and-hand-back escape valve around giving `llm.pydantic_to_openai_tool` an empty `BaseModel`.
  It is already exercised in production: `ReadContinuityContextArgs`
  (`backend/app/services/close_tools.py:278`) is a genuinely zero-field schema registered for
  `read_continuity_context`, and `pydantic_to_openai_tool` does nothing more than call
  `schema.model_json_schema()`. The escape valve is struck from this plan.
- **The frontend test fixtures need a `group` too.** `AssistantModesPage.test.tsx` and
  `SubAgentsPage.test.tsx` build mock `AssistantTool` objects (`WEB_SEARCH`, `READ_CHAPTER`,
  `LIST_CODEX`). Once `AssistantTool` gains a required `group`, every one of those literals fails
  `tsc` under `npm run test:types`. Neither original step listed this as work; this plan's outline
  and test-file scope both carry it explicitly now.
- **`AssistantTool`'s doc comment will become false.** It currently states `ToolResponse` "carries
  **exactly two** fields" — that claim must be corrected to three when `group` lands, or the doc
  comment actively misleads the next reader.

_further build-time observations are appended below by the coder/fixer, if worth saying._

Appended during the build (2026-09-15):

- **The group vocabulary has a fourth key that never crosses the wire.** `ToolDef.group` being
  required means the synthetic delegation `ToolDef` in `services/subagent_delegation.py` also
  declares one — `"delegation"` — but a delegation tool is built per turn and is never in
  `TOOL_REGISTRY`, so it never reaches `list_tools()`, `GET /tools` or the admin picker. Possible
  impact: when `assistant-config.md` records the three stable keys `"codex"` / `"book"` / `"web"` as
  the wire vocabulary, say explicitly that they are the **registry's** keys, so a reader of
  `subagent_delegation.py` does not read `"delegation"` as a fourth catalogue group.
- **The picker's group display order is the frontend constant's key order.** `ToolPicker` walks
  `Object.keys(TOOL_GROUP_LABELS)` and appends the literal `"Other"` bucket, so adding a group is one
  edit in `api/assistantConfig.ts` and needs no change to the component. Possible impact: a sentence
  to that effect wherever `assistant-config.md` describes the grouped picker, so a future group is
  not added by editing the component.
