# Product Folder

The product layer for BookWriter: **why** the system exists, **who** it's for, **what** it must do, and **how anyone knows it works**. This is the layer `/architect` and `/planner` read and cite before design or planning happens.

## Scope — three layers, three questions

| Layer | Question | Folder |
|-------|----------|--------|
| Product | why / who-for / what-for-whom | `docs/product/` (this folder) |
| Architecture | how | `docs/architecture/` |
| Plans | the work | `docs/plans/` |

The product layer sits **before or alongside** `/architect`, never after — architecture reads product ids to know what it's designing for, not the reverse.

**Never write a technical decision here.** No schema, no library choice, no layering, no endpoint path, no storage detail. If a requirement implies one, surface the requirement (the observable behavior) and leave the decision to `docs/architecture/`. The root `CLAUDE.md` states the same boundary from the other side: the domain is specified *here*, and its architecture is not designed anywhere yet. Product docs state *what the domain must do*, never *how it's implemented*.

A worked example, because this rule gets tested: in round 4 the user asked for codex entries that are "vector indexed and allowed using tools". Vector indexing and tool exposure are mechanisms — they were routed to `/architect`, and what `docs/product/` records instead is the need underneath (the codex outgrows what can be shown wholesale, so generation must reach entries without the author hand-picking them). No vector / index / embedding / tool / retrieval / storage language belongs in this folder.

## Who writes, who reads

- **Writer**: the product-spec-writer agent only. Everyone else — `/architect`, `/planner`, coders, verifiers — reads these files, never edits them.
- **Reviewer**: a product-spec-reviewer agent may check these files against the same rules below; it does not co-own them.

## File set

Small layout (default — use until a file nears the ~400-line budget):

- `vision.md` — the problem, who has it, what happens without a fix, success signals, scope & non-goals.
- `actors.md` — one block per `ACT-###`.
- `features.md` — the spine **and the canonical id registry, until escalation** (see Large layout below). One block per `FEAT-###`. **Never splits**, regardless of layout.
- `use-cases.md` — one entry per `UC-###`: preconditions, main flow, alternate/exception flows, postconditions.
- `stories.md` — one entry per `US-###`, each carrying its `US-###.AC-#` acceptance criteria.
- `glossary.md` — domain terms, one line each. Only created when terms are actually named.

Large layout (escalation once a file would exceed ~400 lines):

- `use-cases/<FEAT-###>.<slug>.md` — one file per feature.
- `stories/<FEAT-###>.<slug>.md` — one file per feature.
- `quick-reference.md` — the **sole canonical id registry** once large layout is in effect: every id, one-liner, status, owning feature/actor. Exempt from the line limit. `features.md` keeps only its FEAT blocks — no registry tables, no Relationships section.
- `relationships.md` — actor×feature matrix, depends-on edges, build order, accepted overlaps, conflicts. Holds what used to be `features.md`'s Relationships section. Never splits.

**Resolved 2026-07-23 (round 5).** `features.md` was closing on its ~400-line budget while bound by "never splits." Round 5 extracted the Relationships section into `relationships.md`, restoring headroom. `features.md` now holds FEAT blocks only; relationship data (actor×feature, depends-on, overlaps, build order, conflicts) lives solely in `relationships.md`.

Do not add a new top-level doc unilaterally — it must come from the writer's briefing.

## ID scheme

`ACT-###`, `FEAT-###`, `UC-###`, `US-###`, and acceptance criteria as `US-###.AC-#`. Zero-padded, 3 digits.

- **Flat** — ids do not encode ownership or hierarchy. Ownership (which actor, which feature) is a body field inside the block, never part of the id string.
- **Permanent** — never renumbered, never reused. A withdrawn id is tombstoned (`Status: withdrawn` + reason kept in place), not deleted, not recycled for something new.
- **Gaps stay** — a skipped or withdrawn number is never backfilled.
- **Allocation** — ids are allocated by the orchestrator (or the confirmed spec plan it hands down), never minted by the writer. The writer transcribes ids it's given; it never invents or renumbers one.
- **Registry** — the canonical list of every id lives in `features.md` (small layout, before `quick-reference.md` exists) or, once escalated, **solely** in `quick-reference.md` (large layout) — `features.md` then keeps only its FEAT blocks, not a registry copy and not the Relationships section (see `relationships.md`). `docs/.cache/` is never the registry.
- **Status lifecycle** — every id carries a status, tracked in the registry: `proposed` → `delivered` | `partially delivered` | `deferred` | `withdrawn`.
  - **delivered** — every realizing id shipped and was verified.
  - **partially delivered** — some realizing ids shipped; the rest name the plan that owns them.
  - **deferred** — specified, not built, a plan owns it.
  - **withdrawn** — tombstoned (`Status: withdrawn` + reason kept in place); `Superseded by:` where a replacement exists. Added 2026-07-30, the project's first finalization pass.

## Provenance — every requirement is tagged

- `[confirmed: user]` — the user said it directly (interview notes).
- `[confirmed: <scout-ref>]` — evidenced in existing code by a scout pass (brownfield), confirmed by the user; cite `path:line`.
- `[inferred]` — behavior assumed but never explicitly confirmed; state the basis. This is a debt marker — keep it rare.
- `_TBD: <reason>_` — unknown. Never invent a requirement to fill the gap; never assert intent by reading code.

## Acceptance criteria — the testable contract

Every `US-###.AC-#` is **Given / When / Then**:

- **Given** — starting state. **When** — the actor's action. **Then** — an observable, falsifiable outcome.
- One outcome per criterion — split "and"-joined outcomes that can fail independently into separate `AC-#` entries.
- No implementation in the Then clause — state the observable result ("order → `cancelled`"), never a call ("OrderService.Cancel() runs").
- Vague criteria ("fast", "intuitive", "robust") are not acceptance criteria — mark `_TBD:` and surface it instead of writing one.

This is the contract a planner turns into a `[test]` DoD item and a test-coder writes a test from, without reading source.

## Merge-fence protocol

```
<!-- product-spec:start -->
<auto-generated>
<!-- product-spec:end -->
```

- The writer edits **only** inside its own marker pairs. Content outside a fence is user-authored prose and is preserved byte-for-byte across every re-run.
- New file → wrap the whole generated body in one fenced block.
- Existing file with markers → replace inside the matching pair only.
- Existing file without markers → treat as fully user-authored; append one new fenced block at the end and say so in the hand-back — never rewrite unfenced content.
- A block is never stripped, and its id is never reused, even on withdrawal.
- `docs/product/CLAUDE.md` (this file) is orchestrator-maintained and is not itself under the fence protocol.

## Citation convention (how other layers cite this one)

- `docs/architecture/` design docs carry a header: `**Realizes:** FEAT-###, UC-###`.
- `docs/plans/` step files cite `US-###.AC-#` inline in Definition-of-done items (each `[test]` DoD item traces to one AC).
- `features.md` records delivery once a plan finalizes: `**Delivered:** docs/plans/<NNN>.<feature>/ (YYYY-MM-DD)`.

This is a convention product docs expose — it does not change how `docs/architecture/` or `docs/plans/` are owned or written.

## Working artifacts (disposable, not the registry)

- `docs/.cache/product/interview.md` — distilled Q&A with the user; evidence, not output.
- `docs/.cache/product/spec-plan.md` — the confirmed plan (ids + source refs) the writer transcribes from; primary source when it conflicts with interview notes.

Both are inputs the writer reads to produce `docs/product/*`. They are disposable scratch state — the durable, citable registry is `features.md` (small layout) or, once escalated, `quick-reference.md` alone (large layout), never `docs/.cache/`.

## Write-rules

- **Never invent a requirement.** Not in the spec plan → not in the doc. Unknown → `_TBD: <reason>_`.
- **Never assert intent** the source material doesn't state — tag `[inferred]` and say why, or leave it out.
- Keep each file under ~400 lines; `quick-reference.md` is the one exception. Over budget → escalate to the large layout, don't cram.
- Terse over prose: one requirement per entry, no marketing language, no restating a field label as a sentence.
- The domain is **no longer deferred** — it is specified here, across five interview rounds. The narrower rule survives and still binds: write only what the confirmed spec plan / interview actually cover, and don't extrapolate domain entities ahead of what's been confirmed.
