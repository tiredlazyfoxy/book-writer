# Outcome — fast/001.snowflake-ids

Intended documentation reconciliations this feature delivers, for a later
`/architect` finalization. **Not applied here** — plans never edit
`docs/architecture/`.

## `docs/architecture/backend.md`

- **Section: "Conventions — entity ID strategy" → "Known deviation — scoped
  migration".** Intended change: flip the framing from "`User` currently uses an
  autoincrement integer PK … not yet migrated" to migrated/delivered — `User`'s
  PK is now an application-generated 64-bit snowflake (`app/ids.py` `generate_id`,
  `default_factory` / db-on-None per the frozen mechanism), and the import codec
  now serializes `id` as a string with number-or-string back-compat. Reason: this
  feature implements the migration, so the "not yet migrated" language is stale.
  Note the remaining touch-point still open: the `user_id` token claim
  (deferred to feature 004).

- **Section: "Conventions — entity ID strategy" (Generator location / Node id /
  Assignment point).** Intended change: mark these as realized in code —
  `app/ids.py` exists with `generate_id()` and the pinned `EPOCH_MS`
  (`1704067200000`); `Settings.node_id` (env `BOOKWRITER_NODE_ID`, default 0) is
  the node source; record which assignment mechanism was frozen
  (`default_factory=generate_id` vs. db-layer-on-`None`). Reason: the spec was
  design intent; it is now shipped and the doc should reflect the concrete choice.

- **Section: "DB import/export" → "Entity id serialization".** Intended change:
  confirm the `users` codec now realizes string-out / number-or-string-in id
  handling (was stated as the rule; now implemented). Reason: keep the doc's
  "realized vs. intended" status accurate.

- **Section: "Domain models — User" (the `id` field row) and the "Deliberate
  divergences" paragraph.** Intended change: update the `id` row from "Currently
  autoincrement integer … not yet migrated" to snowflake (app-generated,
  string-in-JSON), and drop the id-type divergence from the open-migration
  framing. Reason: the divergence is resolved by this feature.

- **Section: "Decision history" (2026-07-22 entries).** Intended change: append a
  short note that the settled snowflake design is now implemented for `User`
  (fast/001), with the `user_id` token-claim serialization remaining for feature
  004. Reason: close the loop between the decision and its realization.

- **Any lingering "decision 6 / autoincrement" references** in `backend.md` (and
  the `User` model docstring reconciliation noted above): intended change is to
  retire the autoincrement wording wherever it described `User.id`. Reason: it no
  longer matches the code.

## Observations

_populated by the coder_

---
Status: Applied 2026-07-22
Applied items: 7 (backend.md items 1–6 + quick-reference.md)
Rejected items: 0

Notes: All intended reconciliations applied. `User.id` docs flipped from
"pending migration" to realized (app-generated snowflake via
`default_factory=generate_id`, `EPOCH_MS=1704067200000`, node id from
`BOOKWRITER_NODE_ID`, codec string-out / legacy-number-in). The one remaining
touch-point — the `user_id` JWT token claim (still int, deferred to
**feature 004**) — is preserved as an explicit caveat in backend.md
(Known deviation, User model, Decision history) and quick-reference.md.
`## Observations` was empty at finalization.
