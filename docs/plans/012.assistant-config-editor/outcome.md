# 012.assistant-config-editor — intended documentation changes

Written by the planner; applied by the architect at finalization. The coder appends
`## Observations` at the bottom.

---

## `docs/architecture/assistant-config.md`

### 1. Close the product-open `_TBD:` on default tool state

- **Section:** "Out of scope — still deferred" (the last bullet: *"`_TBD:` whether a mode's tools
  default on or off before the admin configures it"*), and a matching sentence under "Tool gating".
- **Change:** Remove the bullet from the deferred list and record the settled rule: **an
  unconfigured mode grants no tools — zero `mode_tool` rows is an empty allowlist, not the whole
  registry.**
- **Reason:** User-confirmed during planning (`context.md` → scope decision 1). The reasoning to
  carry across: there must be a representable way to say *"this mode gets no tools"*, and
  overloading empty to mean *all* both makes that state unexpressible and points the default in the
  unsafe direction. The product `_TBD:` on FEAT-020 remains product's to close — see the follow-up
  at the bottom of this file.

### 2. Name the `resolve_tools(None)` seam explicitly

- **Section:** "Tool gating".
- **Change:** Record that `services/tools.py:resolve_tools`'s `None ⇒ whole registry` branch is the
  seam mode-gating replaces, that **FEAT-020's config layer does not touch it**, and that `013` is
  the owner of that replacement (as `docs/plans/011.chat-panel/context.md` already states from the
  other side).
- **Reason:** Two features now depend on the same seam staying put; the doc should say who moves it
  and when, so neither a coder nor a future planner reads the surviving `None` branch as a
  contradiction of decision 1 above.

### 3. Confirm replace-set save semantics as built

- **Section:** "The three link tables".
- **Change:** State that a selection save is **delete-all-then-recreate for that owner**, with the
  four concrete operations (`mode_tools.delete_by_mode`, `mode_subagents.delete_by_mode`,
  `subagent_tools.delete_by_sub_agent`, `mode_subagents.delete_by_sub_agent`), and that requested
  sets are de-duplicated before recreate so the natural-key unique constraints hold.
- **Reason:** The doc implies replace-set; the implementation fixes the exact shape, and the
  two-editors-over-one-row-set property (US-112.AC-2) depends on each bulk delete touching only its
  own slice.

### 4. Record the write-edge validation rules

- **Section:** "Tool registry" (the skip-and-log paragraph) and "SubAgent".
- **Change:** Add that the **config edge refuses** an unknown tool name, an unknown or `disabled`
  sub-agent, an unknown mode key, a blank name (400), a duplicate name (409) and a half-set model
  pair (400) — while the **runtime** still skips-and-logs a selection whose tool has since left the
  registry. Note the accepted consequence that deactivating an `LlmServer` after the fact leaves
  stored sub-agent assignments unusable at runtime, with no re-validation sweep.
- **Reason:** The two behaviours look contradictory read side by side; they address different
  moments and the doc should say so once, with the reasoning (`context.md` → "Planner-derived
  decisions").

### 5. Record the admin route surface and DTO names

- **Section:** new subsection under "Persistence and registry obligations" or alongside the module
  placement paragraph.
- **Change:** Record the frozen surface — `routes/admin/assistant_config.py`, prefix
  `/api/admin/assistant-config`, the eight endpoints (`GET /tools`, `GET /modes`,
  `PUT /modes/{mode_key}`, `GET /sub-agents`, `POST /sub-agents`,
  `PUT /sub-agents/{sub_agent_id}`, `POST /sub-agents/{sub_agent_id}/disable`, `.../enable`) — plus
  the reason→status map, the DTO names frozen by the skeleton, and the two deliberate absences:
  **no single-mode GET** and **no DELETE anywhere** (disable-not-delete).
- **Reason:** The doc currently says only "an admin config service (`services/assistant_config.py`)
  holding the CRUD"; the route and DTO layer is now real and is the contract the frontend and `013`
  bind to.

### 6. Full-replace `PUT` rather than partial `PATCH`

- **Section:** the same route subsection.
- **Change:** Record that both save endpoints are full-replace `PUT`s, so the model pair is always
  explicitly present and `null` + `null` means *inherit*; note that this deliberately does not
  mirror `services/chats.py:update_chat`'s partial-PATCH re-validation quirk, and why.
- **Reason:** Two adjacent features now handle the same `(llm_server_id, model_name)` invariant with
  different update semantics; without the note the difference reads as an inconsistency.

## `docs/architecture/backend/features.md`

### 7. Add the FEAT-020 as-shipped record

- **Section:** a new top-level section alongside "LLM server connections" and "Database consistency
  & management".
- **Change:** Record the assistant-configuration subsystem as shipped: the four layers it spans
  (`db/{assistant_modes,sub_agents,mode_tools,subagent_tools,mode_subagents}.py`,
  `services/assistant_config.py`, `models/schemas/assistant_config.py`,
  `routes/admin/assistant_config.py`), the route family, the error→status taxonomy (**400 / 404 /
  409**, 403 from `require_role`), and that the **409 for a duplicate sub-agent name** follows the
  `services/admin.py` `username_taken` precedent. Cross-link `assistant-config.md` for the model
  rather than duplicating it.
- **Reason:** This file is the route/DTO inventory for shipped backend features; FEAT-020 adds the
  fourth admin route family and the first **409** outside user administration.
- **Note for the architect:** `backend/features.md:72` refers to a `quick-reference.md` for "the
  endpoint and DTO table". `docs/architecture/README.md` lists no such architecture file (the
  `quick-reference.md` that exists is `docs/product/`'s id registry). Resolve where the endpoint
  table actually belongs before adding one — the planner is deliberately not choosing.

### 8. The first-run bootstrap description

- **Section:** wherever the setup/bootstrap paths are described — check `backend/persistence.md`
  ("the deferred-schema startup lifecycle") as well as this file.
- **Change:** Record that **both** first-run paths now seed the five `AssistantMode` rows:
  `services/setup.py:create_database` (as before) **and** `import_database` (added by this feature's
  step 001). State that the seed is idempotent by `key`, so an archive already containing configured
  modes converges instead of colliding — the property the natural-key PK exists to provide. Note
  that the **admin** import surface (`services/db_admin.py` → `routes/admin/db.py`) is unaffected
  and still does not flip `set_db_ready`.
- **Reason:** Before this feature, an instance bootstrapped by DB import had no modes and would show
  an empty editor. That is a bootstrap-lifecycle fact, not an implementation detail.

## `docs/architecture/system-overview.md`

### 9. Admin SPA route map

- **Section:** the frontend route map.
- **Change:** Add the two flat admin routes `/assistant-modes` and `/sub-agents` beside the existing
  Users / LLM Servers / Database entries, and the `/api/admin/assistant-config` REST family.
- **Reason:** The route map is the index of what the SPAs expose; two new admin pages belong in it.

## `docs/architecture/authorization.md`

### 10. Nothing to change — stated so the omission is not ambiguous

The section "Global assistant configuration (FEAT-020) — admin only" already states exactly what
this feature implements: `require_role(admin)`, the same configuration class as LLM servers, never a
`BookAccess` capability, authors never reach it. The implementation matched the written rule with no
divergence and no new failure mode.

**No edit is required.** Recorded explicitly so a reviewer does not read the absence of an
authorization entry as an oversight.

## `docs/architecture/domain-chat.md` and `docs/architecture/README.md`

### 11. Optional pointer refresh

- **Change:** If either file describes FEAT-020 as designed-but-unbuilt, adjust the wording to
  reflect that the **config half is now built** while the **runtime slice remains `013`'s**.
- **Reason:** Keeps the "what is still uncovered" boundary honest. The architect judges whether the
  current wording already reads correctly.

## Follow-up that is NOT ours

- **`docs/product/features.md`** — the
  `**Delivered:** docs/plans/012.assistant-config-editor/ (YYYY-MM-DD)` marker for FEAT-020 is
  **`/product-spec`'s to write**, per `docs/product/CLAUDE.md` → "Citation convention". Do not add
  it from the architecture or planning side.
- **The product-side `_TBD:` on FEAT-020** ("whether a mode's tools default on or off") is likewise
  product's to close. This plan settles the *architectural* answer; surfacing it to `/product-spec`
  is the orchestrator's follow-up.

---

## Observations

- Step 003: id parsing is deliberately **tolerant**. `_parse_sub_agent_id` (and the server-id branch
  of `_validate_model_pair`) is a bare `int()` in a `try/except (ValueError, TypeError)`, so
  surrounding whitespace, a leading `+` and PEP-515 underscores all parse — `" 12 "`, `"\n7\t"`,
  `"+12"` and `"12_000"` resolve to real row ids, while `"1e3"` and `"0x10"` refuse
  (`sub_agent_not_found` / `unknown_or_inactive_server`). This is byte-for-byte
  `services/chats.py:133 _parse_chat_id`, the precedent the step-003 freeze mandated mirroring, and
  is a recorded decision rather than an accident of `int()`. Consequence for step 005: a padded or
  `+`-prefixed path id resolves to the row and answers 200, not 404 — the 404 contract covers
  well-formed-but-absent and genuinely unparsable ids. Possible impact: if the API surface should
  ever reject cosmetically-odd ids, that is a change to the shared `_parse_chat_id` idiom in
  `docs/architecture/backend/features.md`, not a local one here.
- Step 007: `docs/architecture/frontend.md` carries a per-section "Admin SPA — <area> (feature NNN)"
  paragraph for LLM servers (006) and Database (007) but none for assistant configuration, and its
  Mantine component inventory predates this step — the mode editor introduces the repo's **first
  `Textarea`** and the first use of the `ScrollArea.Autosize` + `Checkbox` multi-select idiom
  outside `components/llm-servers/ModelsModal.tsx`. Possible impact: add an "Admin SPA — Assistant
  configuration section (feature 012)" paragraph to `docs/architecture/frontend.md` naming
  `admin/pages/AssistantModesPage.tsx` + `assistantModesPageState.ts` (the repo's first **three-trio**
  page state) and `admin/components/assistant-config/`, alongside the planner's
  `system-overview.md` route-map item.
