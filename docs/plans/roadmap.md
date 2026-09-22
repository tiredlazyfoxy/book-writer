# Roadmap

**Stages 0–5 are delivered as of 2026-07-31.** Every feature through
`016.chapter-close-continuity`, plus `021.per-author-system-prompt`,
`fast/001` and `fast/002`, has all steps `done` + PASS. The free-writing
path — bootstrap → auth → users → LLM servers → DB consistency → data
domain → books → working page → chat → assistant config → codex → chapter
skeleton → chapter writing → chapter close & continuity — exists end to end
in code. Stage 6 (`017`, `018`, `019`) and Stage 7 (`022`) are roadmapped and
unbuilt; `022.reader-mode` is the one to be built next.

The book domain (FEAT-006..019) was designed at the 2026-07-24 architect
pass (`docs/architecture/domain-*.md`, `authorization.md`, `retrieval.md`,
`frontend-workspace.md`), so domain stages carry no `/architect` gate. The
FEAT-020 slice of the assistant subsystem (config model + runtime: prompt
composition, the tool/function-call protocol via `chat_with_tools`,
sub-agent delegation, sub-agent model resolution) is designed
(`docs/architecture/assistant-config.md`). Of the once-undesigned
**FEAT-013** internals, the SSE shared-canvas write protocol and web-search
wiring were designed and delivered in `011`/`013`/`015`; what is still
undesigned — general context/content assembly, main-chat model selection,
token budgeting — is resolved during planning of the features that touch it
(`018`, `019`) and reconciled back to `docs/architecture/` after.

**Delivered is not the same as reachable.** The five assistant modes seed
with empty prompts and no tool or sub-agent assignments
(`backend/app/db/assistant_modes.py`), so every registered tool — codex,
chapter-write, and the five close tools — ships unreachable until an
administrator configures each mode in `012.assistant-config-editor`. That
configuration, plus one live run, is an operating step no feature owns; it
is what UC-047's deferral in `docs/product/` is waiting on.

No status column below — status is derived from folder state: `brief.md`
only = roadmapped, `+ status.md` = planned, all steps `done` + PASS =
delivered.

<!-- roadmap:start -->
## Stage map

| Stage | Goal | Exit criterion |
|---|---|---|
| 0 · Scaffold | Runnable walking skeleton through the whole stack | App boots; `npm run build` + `pytest` green; a health call flows browser→api/→FastAPI→layers |
| 1 · Foundation platform | The admin/auth platform stands | Operator bootstraps DB+admin; users log in; admin manages users, LLM servers, DB consistency |
| 2 · Data foundation & admin polish | Every book-domain entity is persisted and portable; the admin SPA nav is coherent | All FEAT-006..018 tables round-trip through gzipped JSONL export/import; codex registered as the first vector source; admin SPA left-menu / logout / switch-to-main-site work |
| 3 · Books, workspace & assistant config | An author manages books and works inside the two-pane workspace with chat, and the admin configures the assistant that powers it | Create/manage books + co-authors/visibility; open the working page (navigator, book-state landing, content pane, restore buffer); manage chats and converse with the assistant (web search); admin configures assistant modes, sub-agents & tools; the book owner sets the book-wide system prompt |
| 4 · Codex | The codex is authorable, searchable, and reachable by the assistant | Author/browse/search codex by kind; entries incrementally embedded; assistant reaches and writes codex from chat |
| 5 · Chapters (free mode) | Write a book chapter by chapter in free mode | Build a chapter skeleton and set a chapter's system prompt, write chapters in blocks referencing the codex, close a chapter drafting its summary/notes/flags |
| 6 · Archive & history | Content is recoverable and its history is browsable | Archive/restore codex; browse chapter variants (view/compare/apply) and codex version history, surfaced in the content pane and via history tools |
| 7 · Reader | ACT-006 becomes real — a logged-in non-member can read a public book | A logged-in non-member opens the reader page, sees the table of contents of the book's closed and open chapters, follows a link, and reads that chapter's text read-only; a private book and a logged-out visitor are both refused |

## Stage 0 — Scaffold (briefed)

| Feature | Track | Size | Delivers | Depends on | Definition |
|---|---|---|---|---|---|
| `001.backend-scaffold` | multi-step | M | — | none | FastAPI backend as a runnable, testable 4-layer skeleton. |
| `002.frontend-scaffold` | multi-step | M | — | `001.backend-scaffold` | Vite MPA skeleton (3 entries) with MobX/Mantine/api-layer wired. |

## Stage 1 — Foundation platform (briefed)

| Feature | Track | Size | Delivers | Depends on | Definition |
|---|---|---|---|---|---|
| `003.first-run-bootstrap` | multi-step | M | FEAT-001 | `001.backend-scaffold`, `002.frontend-scaffold` | Bring an unconfigured instance to a usable state (create-DB+admin or import). |
| `004.authentication-session` | multi-step | M | FEAT-002 | `003.first-run-bootstrap` | Log in, hold a session, log out; expired/invalidated sessions force re-auth. |
| `005.user-management` | multi-step | M | FEAT-003 | `004.authentication-session` | Admin-gated account lifecycle: list, create, reset, role, disable. |
| `006.llm-server-connections` | multi-step | M/L | FEAT-004 | `005.user-management` | Admin registers/tests/manages LLM servers; probes models; designates embedding server+model. |
| `007.database-consistency` | multi-step | M/L | FEAT-005 | `006.llm-server-connections` | Schema-drift report + remediation; DB export/import; rebuild vector index. |

## Stage 2 — Data foundation & admin polish (briefed)

| Feature | Track | Size | Delivers | Depends on | Definition |
|---|---|---|---|---|---|
| `008.data-domain` | multi-step | L | — | `007.database-consistency` | Persist every book-domain entity + the five FEAT-020 assistant-config tables: one db module + JSONL codec per table; register codex as first vector source. |
| `fast/002.admin-ui-retune` | fast | S | — | `005.user-management` | Retune admin SPA nav: fix left menu, wire logout, add switch-to-main-site link. |

## Stage 3 — Books, workspace & assistant config (briefed)

| Feature | Track | Size | Delivers | Depends on | Definition |
|---|---|---|---|---|---|
| `009.books` | multi-step | L | FEAT-006, FEAT-007 | `008.data-domain` | Create/own/list/archive/transfer a book; manage co-authors and visibility. |
| `010.working-page` | multi-step | L | FEAT-013 (workspace shell) | `009.books` | Working-page SPA shell: navigator, book-state landing, draft-until-saved content pane with restore buffer. |
| `011.chat-panel` | multi-step | L | FEAT-013 (chat + assistant + web) | `010.working-page` | Live chat pane + assistant-loop scaffold: create/list/continue/archive chats; converse with the assistant; web search; `TOOL_REGISTRY` / `chat_with_tools` / prompt-composition framework. |
| `012.assistant-config-editor` | multi-step | L | FEAT-020 | `008.data-domain` | Admin-only editor: five mode prompts + tool/sub-agent selection; sub-agent CRUD, disable, model assignment, tool selection. |
| `021.per-author-system-prompt` | multi-step | M | FEAT-019 (book half): UC-098, US-115 | `009.books`, `011.chat-panel` | Each member sets their **own** book-level system prompt, applied to their own chats in that book; composition switches from the book-wide field to the per-author one. |

`fast/003.book-system-prompt` is **retired** — see "Retired features" below.

## Stage 4 — Codex (briefed)

| Feature | Track | Size | Delivers | Depends on | Definition |
|---|---|---|---|---|---|
| `013.codex` | multi-step | L | FEAT-017 (core), FEAT-018, FEAT-020 (mode runtime) | `010.working-page`, `011.chat-panel`, `012.assistant-config-editor` | Author/edit/browse/search codex entries; incremental embedding; assistant reaches and writes codex from chat; FEAT-020 mode runtime (mode determination, tool gating, sub-agent delegation). |

## Stage 5 — Chapters (free mode) (briefed)

| Feature | Track | Size | Delivers | Depends on | Definition |
|---|---|---|---|---|---|
| `014.chapter-skeleton` | multi-step | M/L | FEAT-008, FEAT-019 (chapter half): UC-099, US-116 | `009.books` | Build a chapter skeleton: add/reorder/edit-sketch/remove a planned chapter; any member sets/clears their own chapter system prompt. |
| `015.chapter-writing-free-mode` | multi-step | L | FEAT-009 | `014.chapter-skeleton`, `010.working-page` | Open/write/close/reopen a chapter in free mode via the edit write path; 409 concurrency + restore-buffer reconciliation. |
| `016.chapter-close-continuity` | multi-step | L | FEAT-012, FEAT-016 (flags + the check) | `015.chapter-writing-free-mode` | Close as an assistant turn that drafts the summary and state-note changeset and runs the consistency check; view state notes/changeset; raise/resolve flags. **As built, close succeeds on a clean run with no owner-approval gate** — UC-048/US-050/US-051 stay deferred. |

## Stage 6 — Archive & history (briefed)

| Feature | Track | Size | Delivers | Depends on | Definition |
|---|---|---|---|---|---|
| `017.codex-archive-restore` | multi-step | M | FEAT-017 (UC-072) | `013.codex` | Archive/restore a codex entry; archive removes it from the vector index. |
| `018.chapter-history-variants` | multi-step | M/L | FEAT-014 | `015.chapter-writing-free-mode`, `010.working-page` | List/compare/apply a chapter's variants and prior revisions via the Variants navigator entry. |
| `019.codex-history` | multi-step | M | FEAT-017 (UC-073, UC-074) | `013.codex`, `010.working-page` | View a codex entry's edit history and restore an earlier version. |

## Stage 7 — Reader (briefed)

| Feature | Track | Size | Delivers | Depends on | Definition |
|---|---|---|---|---|---|
| `022.reader-mode` | multi-step | M | FEAT-007 (reader half): UC-029, US-030 | `009.books`, `015.chapter-writing-free-mode` | Read a public book as a logged-in non-member: table of contents of written chapters, chapter text read-only; no other surface. |

This stage's `closed` + `open` chapter-visibility scoping for the table of
contents is this stage's own decision, not a product requirement — UC-029
does not specify which chapter states a reader sees.

## Build order (topological)

`001 → 002 → 003 → 004 → 005 → 006 → 007 → 008 → fast/002.admin-ui-retune →
009 → 010 → 011 → 012.assistant-config-editor → 013 → 014 →
021.per-author-system-prompt → 015 → 016 → 022.reader-mode → 017 → 018 → 019`

That is the order as **actually built** through `016`, plus `022.reader-mode`
placed next. All dependencies point backward; acyclic. `fast/002.admin-ui-retune`
depends only on delivered foundation (`005.user-management`), so its position
after `008` is a sequencing choice, not a hard edge. `021.per-author-system-prompt`
depends on `009.books` and on `011.chat-panel`'s `prompt_composition.py`; it
shipped between `014` and `015` as a sequencing choice, not a hard edge.
`012.assistant-config-editor` depends only on `008.data-domain`; its position
after `011` is the user's sequencing decision — the mode prompts must be
authorable before codex and chapter work — not a hard edge. `022.reader-mode`
depends only on delivered work (`009.books`, `015.chapter-writing-free-mode`)
and has **no edge** to `017`/`018`/`019`; its position ahead of Stage 6 is
likewise a sequencing choice, not a hard edge. Numbers 008–019, `021`, `022`
and `fast/002` are **allocated**, not indicative.

## Retired features

- **`020`** — the feature that held the number is now
  `012.assistant-config-editor`. No folder exists.
- **`fast/003.book-system-prompt`** — retired 2026-07-31, superseded by
  `021.per-author-system-prompt`. It was scoped to expose the *book-wide*
  `Book.system_prompt` (UC-093/US-108), and FEAT-019 subsequently pivoted to
  **per-author** prompts: UC-093 and US-108 are tombstoned in
  `docs/product/quick-reference.md` (`withdrawn → UC-098` / `→ US-115`), and
  `021` delivered the replacement on 2026-07-29. The folder still holds a
  stale `brief.md` and no `status.md`; it is retired, not roadmapped, and must
  not be picked up by `/fast-feature`.

## Mapped later (numbers 023+ when mapped)

- **FEAT-010 proposal mode** — out of the free-writing MVP by definition.
  Blocks `US-053.AC-2` (a co-author's state-note edit in a proposal-mode book
  is refused today, not held as a proposal).
- **FEAT-011 content moderation** (priority *must*) — quarantine, destroy,
  removal notice, moderation view. Nothing built.
- **FEAT-015 book cloning** (priority *must*) — nothing built.
- **FEAT-016, the remaining check surfaces.** The consistency check itself is
  **no longer unmapped**: `016.chapter-close-continuity` pulled it in (design
  note D2) as the `close-chapter` mode's own work — `raise_check_flag` /
  `read_continuity_context`, gated behind the mode/tool configuration above.
  What is still unmapped is the **on-demand** run (UC-064/US-072) and the
  codex-gap warning (UC-080/US-091, US-092).
- **UC-088 / US-102 scoped consistency check in chat** — the in-chat surface;
  its sub-agent delegation plumbing landed in `013.codex`.
- **FEAT-013 context breadth** — `US-057` (the mode-dependent baseline),
  `UC-085/US-099` (assistant pulls a named chapter into context),
  `UC-086/US-100` (semantic search over the book's material: the vector corpus
  is **codex-only** today — chapters, summaries and state notes are not
  embedded), main-chat model selection and token budgeting.
- **UC-075** codex cross-book copy · **UC-025/US-026** admin ownership
  reassignment of a disabled owner's book (explicitly out of `009.books`).
- **The serving layer** (no product id) — `nginx/` and both
  `docker-compose*.yml` do not exist. Nothing can be deployed until they are,
  and they must carry static roots for `/work` and `/read` as well as `/`,
  `/admin` and `/login`.

`UC-054/055` (composing chapter edits via chat) has **left** this list:
`011.chat-panel` delivered UC-054/US-058, and `015.chapter-writing-free-mode`
delivered the chapter canvas write path and the assistant's chapter tools.
Note that `015`'s DoD items for that half deliberately **cite no product id**
— because this roadmap still parked UC-054/055 under "Mapped later" when the
plan was written — so the delivery is recorded through the stories
(US-059, US-103, US-117) rather than through an AC citation on the UC.

**UC-029/US-030** (the reader SPA) has also **left** this list: `009.books`
shipped the access-controlled backend projection, and the surface that
consumes it is now mapped as `022.reader-mode` in Stage 7.

## Graph notes

- **Codex depends on chat:** `013.codex` depends on `011.chat-panel` because
  its chat-authoring half (FEAT-018) needs the assistant loop.
- `018.chapter-history-variants` and `019.codex-history` still carry what is
  left of the **undesigned FEAT-013 assistant subsystem** — general
  context/content assembly, main-chat model selection, token budgeting — as a
  planner open question; resolved during planning and reconciled to
  `docs/architecture/` after. No architect gate is placed on this. Three items
  have left this set: the tool/function-call protocol and sub-agent model
  selection (designed in `assistant-config.md`, FEAT-020), the SSE
  shared-canvas event protocol (designed and built in `011`/`013`/`015`,
  recorded in `assistant-runtime.md`), and web search (built in `011`).
- The FEAT-020 mode runtime lands in `013.codex` (the first mode-bearing
  subjects — codex entries), not `011.chat-panel`; seeded modes plus the
  code-defined `TOOL_REGISTRY` let it run before `012`'s editor exists.
  FEAT-020 delivery spreads across `008` (config tables), `012` (editor) and
  `013` (mode runtime), with the loop scaffold laid in `011` and the runtime
  extended for chapter modes in `015`/`016`.
- `013.codex` depends on `012.assistant-config-editor` because the
  codex-editing mode prompt must be authorable before codex editing is usable;
  the same reasoning applies to the chapter modes needed by `015`/`016`, which
  sit far downstream of `012` already.
- FEAT-019 (author-facing system prompts) is not a single placeholder
  feature, and it is **per author**, not per book. The book half is
  `021.per-author-system-prompt` (UC-098/US-115), which replaced the retired
  `fast/003.book-system-prompt`; the chapter half (UC-099/US-116) rides with
  `014.chapter-skeleton`, which had to build the chapter
  service/route/schema/authz column anyway. Each half owns its own
  `*_author_prompt` table; `Book.system_prompt` is no longer the composed
  source.
- `fast/002.admin-ui-retune` is foundation polish (fixes the delivered admin
  SPA), grouped into Stage 2 for milestone purposes though it depends only on
  `005.user-management`; booked fast on the expectation it is one
  nav/logout pass.
- The book-domain architecture (`domain-*.md`, `authorization.md`,
  `retrieval.md`, `frontend-workspace.md`) is designed as of 2026-07-24; the
  old ⛔ architect gates on Stages 2–6 are dropped. Only the FEAT-013 assistant
  internals remain undesigned, handled as planner open questions per feature
  above.
<!-- roadmap:end -->
