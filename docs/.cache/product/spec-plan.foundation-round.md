# Product-spec plan — BookWriter admin / foundation layer

Confirmed with the user (2026-07-20). Writer's primary source alongside `interview.md`.
Greenfield / Workflow A. Layout: **small (single)**. All ids allocated here — the writer transcribes, never allocates.

## File plan (`docs/product/`)

| File | Purpose |
|---|---|
| `CLAUDE.md` | product-layer contract (written first, bootstrap mode) |
| `vision.md` | problem, users, success at 6 months, scope & non-goals |
| `actors.md` | ACT-### |
| `features.md` | feature spine + the id registry (never splits) |
| `use-cases.md` | UC-### flows (main / alternate / exception) |
| `stories.md` | US-### + US-###.AC-# (Given/When/Then) |
| `glossary.md` | domain + platform vocabulary (≥8 terms) |

## Provenance
- `[confirmed: user]`: the four decisions — roles (admin+author), disable-only, create+import bootstrap, report+remediate DB page — and the ordered four-capability scope.
- `[inferred]`: behaviour carried from `LLMRPTextOnlyProject` not explicitly confirmed (auth mechanics, secret-masking specifics, probe/health-check semantics). Writer tags; user confirms at review.
- Unknowns → `_TBD:`.

## Actors
| id | name | one-liner | interview ref |
|---|---|---|---|
| ACT-001 | Administrator | Sets up & operates the platform: bootstrap, users, LLM servers, DB health. | features |
| ACT-002 | Author | A book-writing account; in this layer only logs in (authoring deferred). | features, FEAT-003 |
| ACT-003 | First-run operator | Pre-auth actor who bootstraps an unconfigured instance and becomes the first admin. | FEAT-001 |

## Features (spine + registry)
| id | name | provenance | interview ref |
|---|---|---|---|
| FEAT-001 | First-run bootstrap | [confirmed: user] | FEAT-001 first-run bootstrap |
| FEAT-002 | Authentication & session | [inferred] | FEAT-002 |
| FEAT-003 | User management | [confirmed: user] | FEAT-003 |
| FEAT-004 | LLM server connections | [confirmed: user] | features, reference mapping |
| FEAT-005 | Database consistency & management | [confirmed: user] | FEAT-005 |

## Use cases
| id | title | feature | notes |
|---|---|---|---|
| UC-001 | Create DB + first admin | FEAT-001 | main; exc: DB already exists |
| UC-002 | Import DB to bootstrap | FEAT-001 | main; exc: invalid/corrupt export |
| UC-003 | Log in | FEAT-002 | alt: signing-key rotation; exc: bad credentials / rate-limited |
| UC-004 | Log out / session expiry | FEAT-002 | |
| UC-005 | List users | FEAT-003 | admin-gated |
| UC-006 | Create user | FEAT-003 | exc: duplicate username |
| UC-007 | Reset user password | FEAT-003 | re-enables a disabled account |
| UC-008 | Change user role | FEAT-003 | exc: cannot change own role |
| UC-009 | Disable user | FEAT-003 | exc: cannot disable self |
| UC-010 | Register LLM server | FEAT-004 | fields incl. backend_type, base_url, api_key |
| UC-011 | Test connection / probe models | FEAT-004 | exc: server unreachable |
| UC-012 | Enable models | FEAT-004 | from probed list |
| UC-013 | Edit / delete LLM server | FEAT-004 | |
| UC-014 | Designate embedding server + model | FEAT-004 | single embedding provider |
| UC-015 | View consistency report | FEAT-005 | per-table ok/drift/missing |
| UC-016 | Create missing table | FEAT-005 | remediation |
| UC-017 | Sync table schema | FEAT-005 | remediation |
| UC-018 | Export database | FEAT-005 | |
| UC-019 | Import database (admin) | FEAT-005 | distinct from first-run bootstrap import |
| UC-020 | Rebuild vector index | FEAT-005 | LanceDB rebuilt from source rows |

## Stories (each carries Given/When/Then AC as US-###.AC-#)
| id | title | feature | key AC seeds |
|---|---|---|---|
| US-001 | First-run: create DB + admin | FEAT-001 | success; reject if DB exists; password confirm/min-length |
| US-002 | First-run: import DB | FEAT-001 | success restore; reject invalid export |
| US-003 | Log in | FEAT-002 | valid → session; invalid → rejected; rate-limit after N attempts |
| US-004 | Log out / session expiry | FEAT-002 | logout ends session; expired token → re-auth |
| US-005 | Admin lists users | FEAT-003 | response excludes secrets; shows role & last-login |
| US-006 | Admin creates user | FEAT-003 | admin/author role; duplicate username rejected |
| US-007 | Admin resets password | FEAT-003 | sets new credentials; re-enables disabled user |
| US-008 | Admin changes role | FEAT-003 | role updated; cannot change own role |
| US-009 | Admin disables user | FEAT-003 | credentials nulled; cannot disable self |
| US-010 | Register LLM server | FEAT-004 | required fields; backend_type ∈ {llama-swap, openai} |
| US-011 | Test connection / probe models | FEAT-004 | reachable → model list; unreachable → error surfaced |
| US-012 | Enable models | FEAT-004 | subset of probed models persisted |
| US-013 | Edit / delete LLM server | FEAT-004 | update fields; delete removes server |
| US-014 | Designate embedding server | FEAT-004 | one embedding server+model; re-designation replaces prior |
| US-015 | View consistency report | FEAT-005 | per-table status + missing/extra columns |
| US-016 | Create missing table | FEAT-005 | missing table created from model |
| US-017 | Sync table schema | FEAT-005 | missing columns added; extras reconciled |
| US-018 | Export database | FEAT-005 | downloadable export produced |
| US-019 | Import database (admin) | FEAT-005 | UPSERT/idempotent restore |
| US-020 | Rebuild vector index | FEAT-005 | index rebuilt from source rows |
| US-021 | API-key $ENV indirection & secret masking | FEAT-004 | `$VAR` stored/resolved at use; responses expose only has_api_key |

## Per-file outline
- **vision.md** — problem (authors need LLM-assisted long-form fiction tooling; but first the platform must stand itself up); users (admin, author); success at 6 months (an admin can bootstrap an instance, manage accounts, wire up LLM servers, and keep the DB healthy — with zero authoring domain yet); scope (the four capabilities) & non-goals (the fiction-authoring domain, explicitly deferred).
- **actors.md** — ACT-001..003 with goal + context each.
- **features.md** — the spine (FEAT-001..005), each with description, actor(s), realizing UC/US ids; hosts the canonical id registry (actors, features, use cases, stories).
- **use-cases.md** — UC-001..020, each: actor, preconditions, main flow, alternate + exception flows, postconditions.
- **stories.md** — US-001..021, each: "As a <actor> I want … so that …" + numbered Given/When/Then AC.
- **glossary.md** — admin, author, first-run bootstrap, JWT per-user signing key, LLM server (provider), backend_type (llama-swap/openai), $ENV API-key indirection, embedding server, schema drift, consistency report, UPSERT JSONL import/export, LanceDB vector index, disable (vs delete).

## Guardrails for the writer
- Stay in the product layer: describe **what/why**, never **how**. No schema names, table names, library choices, endpoint paths, or layering in requirement text (those belong to `/architect`). Reference API paths in `interview.md` are context for understanding behaviour, not to be transcribed as requirements.
- Do not spec the authoring domain. If a requirement needs a domain entity, stop and mark `_TBD:`.
- Every FEAT has ≥1 UC and ≥1 US. Every AC is checkable.
