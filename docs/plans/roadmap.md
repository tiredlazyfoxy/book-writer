# Roadmap

BookWriter is a greenfield build (zero source). Foundation (FEAT-001..005) has
architecture; the book domain (FEAT-006..018) does not. **Each domain stage
(2–6) carries an `/architect` gate — its slice must be designed before
`/planner` can plan it.**

No status column below — status is derived from folder state: `brief.md`
only = roadmapped, `+ status.md` = planned, all steps `done` + PASS =
delivered.

<!-- roadmap:start -->
## Stage map

| Stage | Goal | Exit criterion |
|---|---|---|
| 0 · Scaffold | Runnable walking skeleton through the whole stack | App boots; `npm run build` + `pytest` green; a health call flows browser→api/→FastAPI→layers |
| 1 · Foundation platform | The admin/auth platform stands | Operator bootstraps DB+admin; users log in; admin manages users, LLM servers, DB consistency |
| 2 · Writable book + codex (MVP) | Write a book in free mode, backed by a codex | Create books, manage co-authors/visibility, author codex entries, build a chapter skeleton, write chapters in blocks (free mode) referencing the codex |
| 3 · Variants | Revise a chapter as variants | Fix a reopened chapter keeping every variant readable/recoverable; owner selects the active variant |
| 4 · Continuity & integrity | The book carries continuity state and is checked | Summaries + state notes drafted on chapter close (gating close); consistency check surfaces contradictions as flags |
| 5 · Assisted composition + full codex | LLM-assisted authoring; codex reaches full power | Compose blocks by chatting with the LLM over continuity+codex; author/rewrite codex entries from the chat; codex gains history/restore + cross-book copy |
| 6 · Advanced collab & branching | The collaboration story reaches final form | Book cloning; admin moderation; proposal-mode review (FEAT-010 last) |

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

## Stage 2 — Writable book + codex (MVP, free mode)  ⛔ architect gate

Briefed after `/architect` designs this slice. Numbers indicative (008+),
allocated when briefed.

| Feature (indicative) | Size | Delivers | Depends on |
|---|---|---|---|
| `008.book-lifecycle` | M | FEAT-006 | `005.user-management` |
| `009.membership-visibility` | M | FEAT-007 | `008.book-lifecycle` |
| `010.codex` (core) | M/L | FEAT-017 (part) | `008.book-lifecycle`, `009.membership-visibility` |
| `011.chapter-skeleton` | M | FEAT-008 | `009.membership-visibility` |
| `012.chapter-writing-free-mode` | L *(planner splits)* | FEAT-009 | `011.chapter-skeleton` (integrates `010.codex`) |

## Stage 3 — Variants  ⛔ architect gate

| Feature (indicative) | Size | Delivers | Depends on |
|---|---|---|---|
| `013.chapter-variants` | M/L | FEAT-014 | `012.chapter-writing-free-mode` |

## Stage 4 — Continuity & integrity  ⛔ architect gate

| Feature (indicative) | Size | Delivers | Depends on |
|---|---|---|---|
| `014.continuity` (summaries + state notes) | L | FEAT-012 | `012.chapter-writing-free-mode`, `010.codex` |
| `015.consistency-check` | M/L | FEAT-016 | `013.chapter-variants`, `014.continuity`, `006.llm-server-connections` |

## Stage 5 — Assisted composition + full codex  ⛔ architect gate

| Feature (indicative) | Size | Delivers | Depends on |
|---|---|---|---|
| `016.composition-chat` | L | FEAT-013 | `014.continuity`, `012.chapter-writing-free-mode`, `006.llm-server-connections`; soft: `021.proposal-mode` |
| `017.codex-from-chat` | M | FEAT-018 | `016.composition-chat`, `010.codex` |
| `018.codex-history-copy` | M/L | FEAT-017 (rest) | `010.codex` |

## Stage 6 — Advanced collab & branching  ⛔ architect gate

| Feature (indicative) | Size | Delivers | Depends on |
|---|---|---|---|
| `019.book-cloning` | L *(late: carries codex/continuity/variants)* | FEAT-015 | `008.book-lifecycle`, `009.membership-visibility` |
| `020.moderation` | M | FEAT-011 | `008.book-lifecycle` |
| `021.proposal-mode` | M/L *(builds last — C6)* | FEAT-010 | `012.chapter-writing-free-mode` |

## Build order (topological)

`001 → 002 → 003 → 004 → 005 → 006 → 007 →` *(architect gate)* `→
008.book-lifecycle → 009.membership-visibility → 010.codex →
011.chapter-skeleton → 012.chapter-writing-free-mode → 013.chapter-variants →
014.continuity → 015.consistency-check → 016.composition-chat →
017.codex-from-chat → 018.codex-history-copy → 019.book-cloning →
020.moderation → 021.proposal-mode`

Numbers 008+ are **indicative only** — allocated when each domain stage is
briefed.

## Graph notes

- **Codex precedes writing:** `010.codex` (FEAT-017 core) is built before
  `012.chapter-writing-free-mode` (FEAT-009) — user priority: no real book
  writing without the codex. Codex hard-deps only book (008) + membership (009).
- **FEAT-017 split** across `010.codex` (create/edit/browse/search) and
  `018.codex-history-copy` (archive/history/restore/cross-book copy).
- **Close-gate seam:** `014.continuity` (FEAT-012) amends the chapter-close
  behaviour first shipped in `012` (FEAT-009): Stage 2 close is ungated; Stage 4
  adds the approved-continuity requirement. Explicit seam, not a scope change.
- **Soft edge:** `016.composition-chat` → `021.proposal-mode` (C6) — composition
  runs free-mode-only until proposal mode exists; not a build gate.
- **Cloning placed late:** `019.book-cloning` after the things a complete clone
  carries — codex (010/018), continuity (014), variants (013).
- **Moderation** (020) needs only 008; late by user choice.
- **Proposal mode** (021) builds last (C6).
- Acyclic; the only forward edge (016→021) is soft. No cycles.
<!-- roadmap:end -->
