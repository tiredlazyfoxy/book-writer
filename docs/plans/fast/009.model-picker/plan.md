# fast/009.model-picker — One-click model selection that actually sticks

## Goal

Replace the chat pane's three-click model control (a `Popover` wrapping a collapsed `<Select>`) with a single-click dropdown that opens straight onto a searchable, keyboard-navigable option list, and make a pick persist to the chat immediately so the header label changes and the choice survives a reload. Harden the settings save so an unresolvable stored model pair is left alone instead of being cleared.

## Source files

- `frontend/src/work/components/chat/ChatPane.tsx` — the header model control: replace the `Popover` + `<Select>` nesting with a `Combobox` whose list is already open and whose search field is focused; wire the pick.
- `frontend/src/work/components/chat/chatPaneState.ts` — the model-search needle, the filtered-options computed, the `modelLabel` fallback, the immediate-pick effect function, and the `saveChatSettings` unresolvable-pair fix.

Nothing else. `ChatSettingsPanel.tsx`, `src/api/chats.ts` and `src/types/chats.d.ts` are read-only for this plan, and there is no backend change.

## Test files

- `frontend/tests/work/ChatModelPicker.test.tsx` — **new.** The component-level interaction spec: open, focus, filter, click-pick, Enter-pick, Escape-cancel, the empty/loading/error lines, popover mutual exclusion, needle reset, no refetch on open.
- `frontend/tests/work/chatPaneSettings.test.ts` — **existing, extended.** The state-level contracts: the immediate PATCH and its payload, the revert-on-failure, the settings-draft reconciliation (no re-PATCH on the next send), and the unresolvable-pair hardening. Its existing DoD-4 and DoD-5 cases must keep passing.
- `frontend/tests/work/ChatPane.test.tsx` — **existing, repair only.** Its `"settings are editable on the active chat (011 DoD-8)"` case drives the removed `<Select>` and must be rewritten against the new control. Do not otherwise rewrite this file; its other cases (023 DoD-9, 011 DoD-6, 011 DoD-7, 011 DoD-10) must keep passing unmodified.

Three files rather than the usual one or two, because two of them are existing specs that need repair rather than new coverage. All new coverage lands in `ChatModelPicker.test.tsx` and in new cases appended to `chatPaneSettings.test.ts`.

## Interface intent

Prose only — the `fast-skeleton` agent freezes the exact signatures.

### In `chatPaneState.ts`

**A model-search needle field** on `ChatPaneState`. An observable string holding the current filter text for the model dropdown. It is reset to empty whenever the model panel is opened, and again when the panel is dismissed, so a needle never survives a close/reopen.

**A filtered-model-options computed.** Returns the subset of `modelOptions` whose display label — the existing `"<server_name> · <model_name>"` shape — contains the needle, matched case-insensitively as a substring. An empty needle returns every option. The original `modelOptions` order is preserved; no re-ranking, no fuzzy matching.

**`modelLabel` gains an unresolvable-pair fallback.** When the active chat's stored pair resolves to a loaded option, the label is unchanged from today. When it does **not** resolve — the server was deactivated or the model was removed from the catalogue — the label falls back to the stored `model_name` alone rather than blanking or showing a placeholder, because the stored pair is a real pair that merely is not currently offered. The no-active-chat and no-stored-pair cases keep today's behaviour.

**An immediate-pick effect function.** Takes the state, the book id, the chosen option key, and an optional abort signal last, per the house convention. Its responsibility, in order:

1. Resolve the option key against the loaded `modelOptions`; if it resolves to nothing, do nothing at all (no request, no state change).
2. Remember the active chat's currently stored `llm_server_id` / `model_name` pair.
3. Write the picked pair onto the active chat's row optimistically, so `modelLabel` — and therefore the header — changes at once.
4. Close the model panel and clear the needle.
5. Clear any previous model error, and mark a chat-settings write in flight by reusing the existing `settingsStatus` trio rather than introducing a second one; `settingsStatus` already means "a chat-settings write is in flight" and its error surface is already wired.
6. Issue a chat update carrying **only** `llm_server_id` and `model_name`. No `sampling`, no `title`, no `archived` — a model pick must not smuggle a temperature draft to the server.
7. On success, replace the active chat's row with the chat the server returned, and re-seed **only the model half** of `settingsDraft` (its `optionKey`) to the picked key. `settingsDraft.temperature` is left untouched, so an unsent creativity edit is not discarded by a model pick.
8. On failure, and only when the signal did not abort, restore the remembered pair onto the row, restore `settingsDraft.optionKey` to the remembered pair's key, and record an author-facing message in the existing `serverErrors` map under a stable `"model"` key.

**`saveChatSettings` stops clearing an unresolvable pair.** When `settingsDraft.optionKey` resolves to a loaded option, the request is unchanged. When it does **not** resolve, the update request **omits `llm_server_id` and `model_name` entirely** — both are optional on `UpdateChatRequest` — so the chat's stored pair is left exactly as it is. It must never send a null pair. The `sampling` half with its temperature override is unaffected either way.

**`settingsDirty` must report the model half clean after a persisted pick.** Re-seeding `settingsDraft.optionKey` in the pick function is expected to achieve this with no change to the computed itself; the skeleton confirms that and widens the comparison only if it would still read dirty.

### In `ChatPane.tsx`

**The model control becomes a Mantine `Combobox`** driven by a `useCombobox` store in **controlled** mode. Its open state is `state.openedPanel === "model"`; its open-change callback, when closing, calls the pane's existing `dismissPanel`. `openedPanel` remains the single source of truth for which header surface is open, so opening the model dropdown still closes the settings popover **by construction** and an accepted send still clears whichever is open. The dropdown is **not** portalled.

**The target keeps its current identity** — the subtle, compact, max-width-160 button with `aria-label="Model"` rendering the truncated `state.modelLabel`. Its own click handler keeps calling the pane's `togglePanel("model")` and additionally clears the needle. Per `frontend.md`'s controlled-popover rule, the target owns the toggle and dismissal arrives through the open-change callback; both directions must be bound.

**The dropdown content**, in order: a search input whose accessible name is `"Search models"`, two-way bound to the needle field and carrying `autoFocus` so it is focused by the dropdown's own mount; then the option list, one row per filtered option, each row's value being the existing `modelOptionKey(option)` and its visible text the existing `"<server_name> · <model_name>"` label. Submitting an option — by click or by Enter — calls the pick function with the book id the pane already passes to `createChatInstant`.

**The keyboard contract.** Enter in the search field submits the **first option of the currently filtered list**. Escape closes the dropdown and changes nothing. Arrow Up/Down move the highlight, and the highlight resets to the first option whenever the needle changes. The coder relies on Mantine's built-in combobox keyboard handling where it delivers this and adds an explicit handler on the search input where it does not — **the behaviour is the contract, the mechanism is not**.

**Three labelled non-option states** replace the option list, with exactly this copy: `"No models available"` when the catalogue loaded but is empty, the value of `modelOptionsError` when `modelOptionsStatus === "error"`, and `"Nothing found"` when a non-empty catalogue is filtered to nothing. The dropdown still opens in all three cases — a dead button is worse than a labelled empty state — and Enter picks nothing.

**The model error is visible with the dropdown closed.** The failure message stored under `serverErrors["model"]` renders as an inline author-facing error in the header region, beside or below the model button, since the dropdown has already closed by the time a failed PATCH resolves.

**Nothing else in the pane moves.** The settings popover and `ChatSettingsPanel.tsx`, the "+" instant-create, the composer, the transcript and the pane's vertical flex chain (transcript `flex: 1` **plus** `minHeight: 0`, composer non-shrinking, root `h="100%" mih={0}`) are untouched.

## Definition of done

1. **DoD-1** `[test]` — A single click on the header model button (`aria-label="Model"`) opens the dropdown with the option list **already rendered** — no second click — and the search input (`"Search models"`) is the focused element.
2. **DoD-2** `[test]` — Typing in the search input filters the visible options to case-insensitive substring matches against the `"<server_name> · <model_name>"` label; non-matching options are no longer rendered, and clearing the needle restores the full list in its original order.
3. **DoD-3** `[test]` — Clicking an option closes the dropdown and the header model button immediately shows that option's label.
4. **DoD-4** `[test]` — Pressing Enter in the search input picks the **first option of the currently filtered list**, with the same effect as clicking it: dropdown closed, header updated, one update call issued.
5. **DoD-5** `[test]` — Pressing Escape closes the dropdown, leaves the header label on the previously stored pair, and issues **no** chat update call.
6. **DoD-6** `[test]` — A pick issues exactly **one** chat update call, without any message being sent, and its payload carries the picked `llm_server_id` and `model_name` and **no** `sampling`, `title` or `archived` field.
7. **DoD-7** `[test]` — When that update call rejects, the header label reverts to the previously stored pair and an author-facing error message is rendered in the pane with the dropdown closed.
8. **DoD-8** `[test]` — After a successful pick with no temperature edit, sending a message issues **no further** chat update call. After a successful pick **followed by** a temperature edit, sending a message issues exactly one update call whose `sampling` carries the new temperature and whose model pair is the picked one.
9. **DoD-9** `[test]` — When the active chat's stored pair matches no loaded option, a settings flush leaves the stored pair alone: the update request **omits** `llm_server_id` and `model_name` rather than sending nulls, and the header keeps showing the stored `model_name`.
10. **DoD-10** `[test]` — The three non-option dropdown states render their exact copy and accept no pick: `"No models available"` with an empty loaded catalogue, the `modelOptionsError` text when the options load failed, and `"Nothing found"` when the needle matches nothing. Enter in each case issues no update call.
11. **DoD-11** `[test]` — The `openedPanel` discriminator is intact: opening the model dropdown closes the settings popover, and opening the settings popover closes the model dropdown. The existing "an accepted send clears whichever popover is open" behaviour still holds.
12. **DoD-12** `[test]` — Opening the model dropdown always starts from an empty search needle; a needle typed before a close does not reappear on the next open.
13. **DoD-13** `[test]` — Opening the dropdown triggers **no** model-options fetch; the list renders from the options loaded once at pane mount.
14. **DoD-14** `[manual/live]` — Arrow Up/Down move the highlight within the filtered list, Enter picks the highlighted option rather than always the first, and the highlight resets to the first option whenever the needle changes.
15. **DoD-15** `[manual/live]` — The pick survives a reload: pick a model, do **not** send a message, reload the working page, and the chat header shows the picked model.

**Gates, in addition to the numbered items.** No test cites these; the verifier checks them by running the commands. `cd frontend && npm test`, `npm run build` and `npm run test:types` must all be clean, and **every spec under `frontend/tests/` outside this plan's Test files must pass unmodified**.

## Out of scope

- Any backend change — endpoint, service, DTO or route. None is needed.
- Refetching model options when the dropdown opens; the mount-time load stays the only fetch.
- Making **temperature** persist immediately. It keeps its draft + flush-on-send path, and `ChatSettingsPanel.tsx` is untouched.
- Known defect 2 — an archived chat picked from the list opens an empty pane.
- Known defect 3 — the settings popover surfaces no temperature validation message (its error computed still reads the *new-chat* draft).
- The known gap — the transcript does not auto-scroll to the newest message.
- Favourites, recently-used ordering, per-server grouping, multi-select, or any change to `modelOptionKey`'s shape.
- Recording this feature in `docs/plans/roadmap.md` — that is `/roadmap`'s job.
- Editing `docs/product/` to close UC-081's `_TBD:` — that is `/product-spec`'s job; the orchestrator surfaces it.
