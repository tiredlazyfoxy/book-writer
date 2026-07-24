# Outcome — Feature 008 data-domain

Intended documentation changes once this feature ships, for the architect to
apply at finalization. Grouped by target architecture file. The coder appends
`## Observations` at the bottom as steps complete.

## `docs/architecture/backend/book-domain.md`

- **"The book-domain table registry"** — mark the `TABLE_REGISTRY` order as
  **as-shipped** (was "designed"): all 16 new codec pairs (5 FEAT-020 config +
  11 book-domain) are registered in the canonical FK order, appended after
  `users` / `llm_servers`. Reason: the registry is now realized in code, not
  just specified.
- **"Vector registry"** — this section states `VECTOR_SOURCE_REGISTRY` "is no
  longer empty — `CodexEntry` registers at Stage 2". **Correct it to record the
  deferral**: `CodexEntry`'s vector-source registration was **deferred to
  `013.codex`** by user decision; feature 008 creates the `codex_entries` table
  as an ordinary data class only and registers **no** vector source. Reason:
  keep the architecture honest about what shipped — the table exists, the vector
  indexing does not yet.
- **"Stage-4 columns land at Stage 2"** — confirm as-shipped: `Chapter.state =
  closing`, `Chapter.summary_status`, `Book.moderation_reason` / `moderated_by`
  / `moderated_at`, and the `chapter_note_changesets` table + `status` all land
  now, nullable and unused. Reason: verifies the design intent was realized.
- **"Schema drift — no new code"** — confirm as-shipped: the new tables are
  covered by the FEAT-005 drift report with no change to FEAT-005 code (each
  step's drift-clean DoD verifies it). Reason: records the payoff was realized.

## `docs/architecture/backend/persistence.md`

- **"DB import/export"** — note that `TABLE_REGISTRY` now carries 18 entries
  through `chat_messages`, and that `AssistantMode` is the first codec whose PK
  is a natural key emitted/parsed **verbatim** (not `int()`-coerced). Reason:
  the id-serialization section currently describes only snowflake string ids;
  the natural-key exception is now realized and worth recording beside it.
- **"Vector storage — LanceDB sidecar"** — this section says "`CodexEntry` is
  the first vector-backed model and registers at Stage 2". **Align with the
  deferral**: registration deferred to `013.codex`; the sidecar registry remains
  empty after feature 008. Reason: same honesty correction as above, from the
  persistence side.

## `docs/architecture/assistant-config.md`

- **"Persistence and registry obligations"** — mark the five config tables,
  their codecs, their global-config-block registry positions, and the
  natural-key seed as **as-shipped**; the `seed_default_modes()` seed is wired
  into `services/setup.py::create_database` (idempotent, converges with the
  import UPSERT). Reason: the config-model persistence is now realized; the
  runtime slice remains unbuilt (features 013/020).

## `docs/architecture/domain-model.md`

- **"Two registry obligations"** — the import/export obligation is now met for
  the whole domain; the vector-source obligation for `CodexEntry` is **deferred
  to `013.codex`** (record the deferral so the "first vector source at Stage 2"
  wording does not read as shipped). Reason: single source of truth for what the
  data floor actually delivered.

## `docs/architecture/domain-codex.md`

- **`CodexEntry` field table** — add `author_id` (FK → `users.id`, **required**,
  the entry's original creator) and `modified_by` (FK → `users.id`, **nullable**,
  author of the last version / most recent editor, maintained by the feature-013
  service). Reason: the data floor now carries creator attribution and
  last-editor history that the current `CodexEntry` field table does not yet
  list; this is a divergence to reconcile at finalization.
- **`CodexEntryVersion` field table** — add `generation` (non-null `int`, 1-based
  sequence/generation number of the version within its entry, maintained by the
  service). Reason: the data floor now carries an explicit per-entry version
  ordinal the current `CodexEntryVersion` field table does not yet list.

## `docs/architecture/domain-chat.md`

- **`ChatMessage` field table** — add `position` (non-null `int`, the message
  number / order of the message within its chat, an explicit ordinal alongside
  `created_at`). Reason: the data floor now carries explicit message ordering the
  current `ChatMessage` field table does not yet list; a divergence to reconcile
  at finalization.

<!-- coder appends ## Observations below -->
