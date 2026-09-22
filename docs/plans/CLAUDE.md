# Planning files — layout, lifecycle, and contracts

Every planning and coding agent reads this file first and treats it as authoritative. Two tracks live here: multi-step features and fast features. Bug fixes run against an already-completed plan in either track. Above both tracks sits the **roadmap** layer (`roadmap.md` + per-feature `brief.md`, written by `/roadmap`), which defines *which* features exist and in what order before `/planner` decides *how* one is built — see "Roadmap and briefs" below.

## Roadmap and briefs

Above planning sits the **roadmap** layer, written by `/roadmap` (never by a planner or coder). It decides *which features exist and in what order*; planning decides *how one is built*. `/roadmap` allocates every folder number in both counters — the planner never mints one.

### `roadmap.md`

`docs/plans/roadmap.md` is the **stage index**: the milestone map. It lists each stage (a coherent, shippable stopping point), the features in it, their track/size, the product ids each delivers, and the dependency order. It has **no status column** — status is derived from folder state, never stored here.

### `brief.md`

Each roadmapped feature gets a `brief.md` at the root of its folder — `<NNN>.<feature>/brief.md` (multi-step) or `fast/<NNN>.<name>/brief.md` (fast). A brief is the *definition* of a feature, not its plan: Stage / Track / Size, `Delivers:` (product ids; omitted when there is no product layer), `Depends on:`, a behavioural Definition, Scope In/Out, and Open questions for the planner. It **never** contains steps, a Definition of done, signatures, or file lists — those are the planner's, produced later. The writer edits only inside `<!-- roadmap:start -->` / `<!-- roadmap:end -->` fences; content outside is preserved across re-runs.

Brief shape:

```markdown
# 003.checkout — Checkout flow
<!-- roadmap:start -->
- **Stage:** 001.mvp · **Track:** multi-step · **Size:** M
- **Delivers:** FEAT-003, US-014, US-015
- **Depends on:** `002.catalog`

## Definition
<3–6 sentences, behavioural — what it lets someone do that they couldn't.>

## Scope
**In:** <bullets>
**Out:** <bullets>

## Open questions for the planner
- <what the planner must resolve> — or "None."
<!-- roadmap:end -->
```

### The roadmapped state

A feature folder containing **only `brief.md`** — no `status.md` — is **roadmapped**: defined but not yet planned. The **absence of `status.md` is the signal**; `/roadmap` never seeds one. `/planner` (multi-step) or `/fast-feature` (fast) then reads the brief, harvests fresh evidence, and expands it into `context.md`, step files / `plan.md`, `outcome.md`, and a **seeded `status.md`**. Once `status.md` exists, the feature is **planned**. Lifecycle:

```
/roadmap  → brief.md only             (roadmapped)
/planner  → + context/steps/status    (planned)
/coder …  → status rows → done + PASS  (delivered)
```

An agent listing `docs/plans/` must treat a brief-only folder as **roadmapped, not broken**, and read `brief.md` as the feature definition that `context.md` builds on — never as a missing or malformed plan.

## Tracks — when to use fast vs multi-step

- **Multi-step** (`<NNN>.<feature>/`) — work spanning more than one coherent change: cross-layer coordination, dependencies between sub-parts, design ambiguity needing mid-flight decisions, or more than ~300 LoC of source change. Decomposed into ordered steps by `/planner`.
- **Fast** (`fast/<NNN>.<name>/`) — a single coder pass: one logical change, one or two test files, roughly 50–300 LoC, no internal step boundaries. Planned by `/fast-feature`. If you catch yourself writing "Phase 1 / Phase 2" or "first the schema, then the UI", it is multi-step — promote it.
- **Bug fix** — `/bug-fixer`, run against a `done` plan in either track. Adds no new scope; repairs the existing contract.

The two counters are independent: `fast/001` and `001.<feature>/` are unrelated.

## Layout

```
docs/plans/
  roadmap.md                    # stage index (milestone map) — /roadmap
  <NNN>.<feature>/              # multi-step
    brief.md                    # roadmapped definition — /roadmap (present before planning)
    context.md                  # feature-wide context
    <SSS>.<name>.md             # one step file per step
    <SSS>.context.md            # one per step (never skipped)
    outcome.md                  # intended doc changes, applied at finalization
    status.md                   # step table + lifecycle sections
  fast/
    <NNN>.<name>/               # fast feature
      brief.md                  # roadmapped definition — /roadmap
      context.md
      plan.md                   # the single plan (the step file's equivalent)
      outcome.md
      status.md
  backlog/                      # rough idea seeds; planner input, not executed directly
```

`NNN` / `SSS` are 3-digit zero-padded. Letter suffixes (`001b`) are for splits/rework after the fact, not initial planning.

## Step file / plan.md structure

A multi-step `<SSS>.<name>.md` and a fast `plan.md` carry the same behavioral contract:

- **Goal** — one or two sentences.
- **Source files** — explicit source paths, one per line. This list *is* the coder's scope; the coder touches nothing else.
- **Test files** — explicit test paths, one per line. This list *is* the test-coder's scope. **Must be disjoint from Source files** — neither role crosses into the other's list.
- **Interface intent** — each function / class / type / endpoint the work adds or changes, named with its responsibility and inputs/outputs **in prose**. No exact type signatures — the skeleton agent freezes those.
- **Definition of done** — a numbered checklist (DoD-1, DoD-2, …) of verifiable criteria. Tag each item `[test]` (the test-coder must cover it with a test citing the id) or `[manual/live]` (no automated test; the verifier records it as requires-live-run). The set of `[test]` items is the coverage contract.
- **Dependencies** (multi-step) — earlier steps relied on, or "none".
- **Out of scope** (fast) — short list of deliberate exclusions to bound creep.

Multi-step size budget: 50–200 LoC of source change per step (test volume isn't counted). Fast: 50–300 LoC total.

## Pipeline and ownership — the air gap

Plans run through a chain of single-purpose agents with a strict separation between who writes tests and who writes code:

1. **planner / fast-planner** — writes the plan (sections above). Owns the plan file and the seeded `status.md`.
2. **skeleton / fast-skeleton** — reads Interface intent + code, writes compilable stubs (unimplemented bodies), and **freezes the exact signatures** into a `## Skeleton` record in `status.md`. Owns `## Skeleton`.
3. **test-coder / fast-test-coder** — writes tests from the spec ALONE, bound to the `## Skeleton` signatures, each tagged to a `[test]` DoD id. **Never reads source.** Owns `## Tests` and the Test files.
4. **verifier (red-gate run)** — runs the new tests against the stubs: confirms they compile, cover every `[test]` item, and fail for the right reason.
5. **coder / fast-coder** — fills the stub bodies, **blind to the tests**, runs build/typecheck only. Owns `## Files Changed` and the Source files. May not change a frozen signature (re-route to skeleton if it must).
6. **verifier (verify run)** — the **only** role that runs the tests as a gate. Emits PASS/FAIL plus a **Fault**: `CODE` (back to coder), `TEST` (back to test-coder, then re-red-gate), or `SPEC` (back to the user — the plan itself is wrong). Failure summaries are by-DoD-clause and never quote test internals, so the air gap holds.

The invariant: **expected values come from the spec, never from code; the interface tells you only how to call, never what to expect.** The test-coder never sees the implementation; the coder never sees the tests; the verifier is the sole bridge and relays results, never code or test source.

## status.md

Seeded by the planner. Multi-step:

```
# Feature <NNN> — <name>

| Step | File            | Status  | Verifier | Date |
|------|-----------------|---------|----------|------|
| 001  | `001.<name>.md` | pending | —        | —    |

## Files Changed

_populated by the coder as steps complete_

## Notes & Issues

_populated by the coder when worth saying_
```

Fast:

```
# Fast feature <NNN> — <name>

| Status  | Verifier | Date |
|---------|----------|------|
| pending | —        | —    |

## Files Changed

_populated by the coder when implementation lands_

## Notes & Issues

_populated by the coder when worth saying_
```

As the pipeline runs, agents append their own sections (below `## Files Changed`): `## Skeleton` (frozen signatures, skeleton), `## Tests` (test inventory, each tagged to a DoD id, test-coder), and `## Bug Fixes` (one entry per bug fix against a `done` plan, coder/fixer).

### Status lifecycle

A feature is **roadmapped** (brief only, no `status.md`) → **planned** (planner seeds `status.md`) → then its steps run the status machine below. `pending` → `wip` (coder may set mid-step) → `done` (orchestrator, on verifier PASS) or `blocked` (skeleton/coder escape valve, or Fault: SPEC). Only these four values. A bug fix never un-completes a `done` plan — its record is the `## Bug Fixes` and `## Tests` entries.

## Ownership summary

| File / section               | Written by                    | Everyone else          |
|------------------------------|-------------------------------|------------------------|
| `roadmap.md`                 | `/roadmap` (roadmap-writer)   | read-only              |
| `brief.md`                   | `/roadmap` (roadmap-writer)   | read-only              |
| plan / step file             | planner / fast-planner        | read-only              |
| context.md, `<SSS>.context`  | planner / fast-planner        | read-only              |
| outcome.md (top)             | planner; applied by architect | read-only              |
| outcome.md `## Observations` | coder / fixer                 | read-only              |
| status.md row                | orchestrator                  | —                      |
| `## Skeleton`                | skeleton                      | read-only ground truth |
| `## Tests`                   | test-coder                    | coder never reads      |
| `## Files Changed`           | coder / fixer                 | —                      |
| `## Bug Fixes`               | coder / fixer                 | —                      |

`docs/architecture/` is the architect's domain — plans reference it, never edit it.
