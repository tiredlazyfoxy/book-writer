# Backend — Authentication & Entity IDs

Part of the backend architecture — see `../backend.md` for the index.

This file covers the per-user-key JWT + bcrypt authentication scheme and the system-wide snowflake entity-ID strategy. It is the canonical home of the "Conventions — entity ID strategy" convention that other docs link to.

## Authentication — per-user JWT key + bcrypt

- Passwords are hashed with **bcrypt**.
- Tokens are **JWT, HS256**, but signed with a **per-user signing key** rather than one global application secret. Each user record carries its own signing key; a token is verified against the key of the user it claims to be. There is no shared global secret to leak or rotate app-wide.
- The per-user key is **rotated roughly every 30 days on login**: when a user logs in and their key is older than the rotation window, a fresh key is generated, which transparently invalidates that user's older tokens.
- Tokens are stateless and carried in `Authorization: Bearer <token>`; both SPAs share the same login flow and token. Role information (user vs admin) is carried in the token / user record and gate-checked in `routes/` (or a shared dependency) before delegating to services.

### What feature 003 delivers (minimal subset)

Feature 003 ships only the **minimal** auth primitives needed for first-run bootstrap, not the full scheme above:

- bcrypt `hash_password` / `verify_password`;
- per-user `generate_signing_key`;
- `create_token(user)` — an HS256 token signed with the user's **own** `jwt_signing_key`, payload `user_id` / `username` / `role` / `exp` (≈ +30 days).

Token **verification**, **rotation-on-login**, and **logout** are **not** in 003 — they remain **feature 004**. Until 004 lands, the described per-user-key verification and 30-day rotation are design intent, not shipped behavior.

## Conventions — entity ID strategy

**Realizes:** (system-wide convention)

**The system-wide standard for entity primary-key ids is Snowflake ids, used universally ("anywhere"), with no permanent exceptions.** Rationale: node-aware, globally-unique, time-ordered ids keep cross-instance import/export identity unambiguous as the system grows and as archives move between instances — chosen over autoincrement integers, whose values collide across instances and force id remapping on import. Every new persistent entity uses snowflake ids.

### Concrete Snowflake spec

- **64-bit, Twitter-style layout.** A snowflake id is a 64-bit integer partitioned as **41-bit millisecond timestamp** (since a fixed custom epoch) + **10-bit node id** (0–1023) + **12-bit per-millisecond sequence** (0–4095). The **high bit stays 0** so every id is positive. This yields ~69 years of timestamp range, up to 1024 nodes, and 4096 ids per millisecond per node — chosen because it is the well-understood, proven partitioning that satisfies globally-unique, roughly time-ordered ids within a 64-bit signed range.
- **Custom epoch.** Timestamps are measured from a **fixed project epoch**. The constant is **realized in code** as `EPOCH_MS = 1704067200000` (`2024-01-01T00:00:00Z`) in `app/ids.py`. It is **fixed once and never changed** — moving the epoch re-collides historical ids, so it is a permanent constant of the system, not a tunable.
- **Node id from config.** The 10-bit node id comes from the **`node_id` setting** — realized as `Settings.node_id`, sourced from env **`BOOKWRITER_NODE_ID`** (default `0`, range 0–1023 via `ge`/`le` validation) through the existing pydantic-settings config — the same override pattern as `BOOKWRITER_DB_PATH`. `generate_id()` reads the node id at call time. A distinct node id per instance is what keeps ids unique across instances that generate concurrently.
- **Generator location.** A single cross-cutting utility module **`app/ids.py`** exposes **`generate_id() -> int`** — realized in code (`fast/001.snowflake-ids`) as a monotonic per-millisecond snowflake with a lock-guarded sequence, spin-wait on sequence overflow, and a backwards-clock clamp; the frozen bit-layout constants (`TIMESTAMP_BITS=41`, `NODE_ID_BITS=10`, `SEQUENCE_BITS=12`, `NODE_ID_SHIFT=12`, `TIMESTAMP_SHIFT=22`, `MAX_NODE_ID=1023`, `MAX_SEQUENCE=4095`) live alongside it. It is deliberately **not one of the four layers** — it is a shared helper (like a stdlib utility), called at the entity-construction site. This is the **sanctioned exception** to the "one `db/` module per entity" rule, justified because ids are domain-agnostic and shared by every entity; a per-entity id module would be meaningless duplication.
- **Assignment point — application-generated.** Ids are **generated in the application at entity construction, before insert** — they exist prior to persistence and do **not** rely on DB autoincrement or a post-insert `refresh()` to learn the id. This is **locked**: app-generated, not DB-assigned, because cross-instance uniqueness and time-ordering come from the generator, not the database. The mechanism is now **settled and realized** as a model field with `default_factory=generate_id` — `User` declares `id: int = Field(default_factory=generate_id, primary_key=True)` (`fast/001.snowflake-ids`). The earlier db-layer-on-`None` alternative was **not** chosen.

### 64-bit id JSON serialization convention (system-wide)

**This applies to every entity, not just `User`.** Entity ids are **64-bit ints in Python but are serialized as strings at every JSON boundary** — the export/import JSONL codecs, API request/response DTOs, and the frontend `.d.ts` types. Reason: snowflake ids exceed JavaScript's `Number.MAX_SAFE_INTEGER` (2^53), so a JSON *number* would **silently lose precision** when parsed by any JS/JSON consumer. A JSON **string** preserves the full 64 bits exactly. The frontend therefore types entity ids as `string` (see `frontend.md`).

**Import back-compat.** `from_dict` codecs must accept **both a JSON string and a legacy JSON number** for `id`, parsing via `int(...)`, so **pre-snowflake export archives** — which carry small autoincrement int ids as JSON numbers — still import. Legacy small ints will not collide with time-based snowflakes (which sit far above them in value), so mixed archives are safe.

**Realized migration — one caveat remaining.** The first shipped entity, `User` (feature 003), now uses an **application-generated 64-bit snowflake PK**, delivered by `fast/001.snowflake-ids`. Two of the three migration touch-points are complete: the PK column (`id: int = Field(default_factory=generate_id, primary_key=True)`) and the import codec (string-out, string-or-legacy-number-in). The **one remaining touch-point** is the `user_id` **JWT token claim**, which is **still an int** and **deferred to feature 004** — so `User` is fully conformant except on that single token-claim serialization point. Do **not** read the token claim's current int form as the convention; the convention is snowflake, string-serialized at every JSON boundary. See the Decision history entries (2026-07-22) in `../backend.md`.

**Migration stance — fresh-install, model-only.** The `User`→snowflake migration assumed **no deployed `User` data** (fresh-install stance), so it was a **model-only** change: the PK moved from DB-autoincrement to app-generated snowflake, with **no in-place PK data migration**. This is fortunate — `create_all` cannot alter an existing PK, and there is no Alembic, so an in-place PK-type conversion has no seam here anyway. Fresh installs get the new schema directly from `create_all`; any pre-existing dev DB must be **recreated or re-imported from an archive**, and import stays back-compatible with legacy int-id archives per the serialization convention above.
