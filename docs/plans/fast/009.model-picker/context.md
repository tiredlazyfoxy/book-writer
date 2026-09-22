# fast/009.model-picker — Context

One-click model selection in the chat pane, with an immediate PATCH so the header label actually changes and the pick survives a reload. Closes `frontend-workspace.md`'s **feedback round 3 / F5** and its **known defect 1**.

## Why this exists

The author's report, verbatim:

> "let's rework the annoying bug of the selection of the model. How it works now: i click on model name, it opens popup with the selector, I click to open list, then select model"

and the target behaviour, verbatim — this is the contract every DoD item derives from:

> "how it must be: I click the model name, it immediately opens with the selectable list of models and focused search field on top. click selects model and CHANGES (now it's not working) name on top of the chat. enter selects first model in list (filtered by search). escape closes the popup and don't change the model"

## The two mechanisms behind the complaint

**Three clicks.** The header's model control is a controlled Mantine `Popover` whose *entire dropdown content is a single Mantine `<Select>`*. A `<Select>` is itself a collapsed combobox, so the popover is a dropdown containing a closed dropdown: click 1 opens the container, click 2 opens the list that was the container's only content, click 3 picks. Removing the nesting removes two clicks.

**The name never changes.** `modelLabel` is derived from the **active chat's persisted pair** (resolved through the loaded options), while the `<Select>`'s `onChange` writes only `settingsDraft.optionKey` — an in-memory draft. The only code path that persists a model change today is the send-time flush inside `sendChatTurn`, which PATCHes a dirty settings draft before opening the turn stream. So the label cannot move until a message is sent, and a pick never followed by a send is lost on reload. `frontend-workspace.md` records this as design-note D8's accepted trade-off and as **feedback round 3 / F5, open and unbuilt**.

## Files involved

**Source (the coder's scope):**

- `frontend/src/work/components/chat/ChatPane.tsx` — the pane's header; holds the model `Popover` + `<Select>` to be replaced, the settings `Popover`, the "+" instant-create, and the `togglePanel` / `dismissPanel` helpers over the `openedPanel` discriminator.
- `frontend/src/work/components/chat/chatPaneState.ts` — `ChatPaneState` plus every external `(state, args, signal)` effect function. Holds `modelOptions` / `modelOptionsStatus` / `modelOptionsError`, `activeChatId`, `openedPanel`, `settingsDraft`, `serverErrors`, `settingsStatus`; the computeds `activeChat`, `settingsDirty`, `modelLabel`; and `modelOptionKey`, `saveChatSettings`, `createChatInstant`, `sendChatTurn`, plus the module-private `seedSettingsDraft`.

**Read-only, deliberately untouched:**

- `frontend/src/work/components/chat/ChatSettingsPanel.tsx` — the temperature popover. It holds **no** model selector; an in-file comment already records that the model `<Select>` was moved out into `ChatPane`'s own popover. It stays exactly as it is.
- `frontend/src/api/chats.ts` — `listModelOptions` (`GET /api/books/{bookId}/chats/model-options`, unwraps `{ items }`) and the chat update call. Both already exist and need no change.
- `frontend/src/types/chats.d.ts` — `ModelOptionResponse { server_id; server_name; model_name }`, `UpdateChatRequest` (all fields optional: `title?`, `archived?`, `llm_server_id?`, `model_name?`, `sampling?`), `ChatResponse.llm_server_id` / `.model_name`. **No DTO change is needed and none may be made.**

**No backend change at all.** The endpoint, the DTOs and the model-options route already exist.

## Decisions locked by the author in the planning session

1. **The pick PATCHes the chat immediately.** Clicking a model (or pressing Enter) persists it via `PATCH /api/books/{book_id}/chats/{chat_id}` right away — that is *why* the header name changes, and it is what makes the pick survive a reload. On failure the header reverts to the previously persisted pair and an author-facing error is surfaced. **Temperature keeps its existing draft + flush-on-send path**; it is not made immediate.
2. **Known defect 1 is fixed in the same pass.** An option that does not resolve against the loaded `modelOptions` must **leave the chat's stored pair alone** rather than writing `{llm_server_id: null, model_name: null}`, and the header must keep showing the stored pair (it is a real pair; it is merely not currently offered). Immediate-persist makes this code path run more often, which is why the hardening belongs here and not in a later pass.

## Design decisions this plan makes

### The component: Mantine `Combobox`, not a hand-rolled list

`frontend.md` → Mantine inventory says *"use `Menu.Item` for a simple action, `Popover` when the content does not fit a menu item"*. The author's spec requires a **search field**, which does not fit a menu item — so a menu is out. The two remaining candidates:

- **Keep the `Popover`, hand-roll the content** — a `TextInput` plus a list of buttons. This needs hand-written highlight tracking, arrow-key movement, Enter-picks-highlighted and Escape, all of which already exist in a library primitive.
- **Mantine `Combobox` with `useCombobox`** — the primitive that `<Select>` itself is built on. It gives an always-open option list, an in-dropdown search slot, highlight handling, arrow navigation and option submission for free, and it is the direct de-nesting of what is there today: the `<Select>` unwrapped one level rather than a second widget added.

**Chosen: `Combobox`.** It is the smallest honest change — the existing control already *is* a combobox, just a collapsed one inside a popover — and it removes the hand-rolled keyboard code that the alternative would require.

### The `openedPanel` discriminator survives

`frontend-workspace.md` records that the single `openedPanel: "model" | "settings" | null` exists so that opening one header popover closes the other **by construction**, and that an accepted send clears it. That must not be traded away. The `useCombobox` store is therefore used in **controlled** mode: its open state is driven by `state.openedPanel === "model"`, and its close callback routes back into the pane's existing `dismissPanel`. `openedPanel` stays the single source of truth for which header surface is open.

`frontend.md`'s controlled-`Popover` rule applies transitively, because `Combobox` is built on `Popover`: **bind both directions or it becomes unclosable in one of them.** The target's own click handler owns the toggle; dismissal (click-outside, Escape) comes back through the open-change callback.

### Focus-on-open without a `useEffect`

`frontend.md` forbids `useEffect` in leaf components. Two mechanisms are available and neither breaks the rule:

- **`autoFocus` on the search input** — the dropdown content **mounts on open** (`keepMounted` stays off), so a fresh mount fires `autoFocus`. Zero hooks, zero refs, zero timing assumptions, and `document.activeElement` is assertable under jsdom.
- `useCombobox`'s `focusSearchInput()` driven from a store callback — also legal (calling a library's hook is not authoring one), but it depends on the dropdown being mounted at the moment the callback fires, which is exactly the timing assumption `autoFocus` avoids.

**Chosen: `autoFocus`**, with `focusSearchInput()` as the sanctioned fallback if `autoFocus` proves unreliable under Mantine's dropdown transition. Either way, no `useEffect` and no custom hook.

### Optimistic header, reverting on failure

The author's wording — the header "**reverts**" on failure — implies the label moves first. So the pick writes the new pair onto the active chat's row immediately, then PATCHes, then either confirms from the server's response or restores the remembered pair. A pessimistic "await the PATCH, then update" would make DoD-7 vacuous and would put a network round trip between the click and the visible response.

### Arrow keys are in scope, and lightly verified

The natural reading of *"enter selects first model in list (filtered by search)"* is: the highlight starts on the first filtered option, Enter picks the highlighted one, and arrows move the highlight. That is exactly what `Combobox` gives, so it is in scope rather than excluded. The load-bearing half — **Enter picks the first filtered option** — is a `[test]` item. Arrow movement itself is `[manual/live]`: it is Mantine-internal keyboard behaviour, and a jsdom test of it would mostly test the library.

### The mechanism is not the contract

Mantine's built-in combobox keyboard handling is expected to deliver Enter / arrows / Escape. If it does not, the coder adds an explicit key handler on the search input. The DoD items are phrased behaviourally for exactly this reason; the plan does not bind the coder to a particular Mantine API shape.

## Constraints the implementation must honour

- **`withinPortal` stays `false`.** The current `<Select>` passes `comboboxProps={{ withinPortal: false }}` and the replacement must keep the dropdown rendered inline. jsdom has no portal-aware layout, and React Testing Library queries are simplest when the dropdown is inside the rendered container.
- **The pane's vertical flex contract must not be disturbed** — transcript `flex: 1` **plus** `minHeight: 0`, composer non-shrinking, pane root `h="100%" mih={0}`. `frontend-workspace.md` warns that breaking this chain breaks it **silently**: jsdom has no layout engine, so no test catches it.
- **The send-time flush must survive intact.** `chatPaneSettings.test.ts` DoD-4 asserts that a dirty settings draft is PATCHed before the stream opens, that a **clean** draft issues **no** update call, and that a failed flush aborts the send. After an immediate model PATCH, `settingsDraft`'s **model half** must be re-seeded to the newly stored pair so `settingsDirty` reports **temperature-only** dirtiness — otherwise every send after a pick re-PATCHes a model that is already stored, and the "clean draft issues no update call" assertion fails. **This is the single most likely place for this feature to break an existing contract.** The temperature half of the draft must *not* be re-seeded, or an unsent creativity edit is silently discarded by a model pick.
- **No new fetch on open.** `listModelOptions` is called **once at mount** inside `loadChatPane`. Nothing re-fetches on popover open today and nothing may start.
- **`ChatPaneState` holds no book id** — the pane is book-scoped by remount (`key={bookId}`), not by a stored value. Every effect function takes the book id as an argument; the new pick function does too, using the same book id the pane already passes to `createChatInstant`.
- **Typing discipline:** no `any`. Pydantic/`.d.ts` contracts are unchanged.
- **`observer` on every component**, state in the state class, all effectful operations as external `(state, args, signal)` functions using `runInAction`, `signal` last.

## Test handles — a contract, not decoration

The test-coder never reads source, so the accessible names below are part of the interface, in the same way `frontend.md` treats the composer's `Send` / `Stop` names:

| Handle | Accessible name / text |
|---|---|
| The header model button (opens the dropdown) | `aria-label="Model"` — **unchanged from today** |
| The search input inside the dropdown | `"Search models"` |
| Each option row | `"<server_name> · <model_name>"` — the existing label shape, unchanged |
| No options loaded at all | `"No models available"` |
| Options failed to load | the value of `modelOptionsError` |
| A needle that matches nothing | `"Nothing found"` |

## Existing tests that touch this flow

- `frontend/tests/work/ChatPane.test.tsx` — its `"settings are editable on the active chat (011 DoD-8)"` case (`"changing the active chat's model + temperature calls update, and the pane reflects the new values"`) drives the **old** `<Select>` and will not survive the de-nesting. It must be repaired. The other cases in that file (instant-create default pair 023 DoD-9, create validation 011 DoD-6, no-options refusal 011 DoD-7, sampling round-trip 011 DoD-10) are expected to keep passing untouched.
- `frontend/tests/work/chatPaneSettings.test.ts` — `"settings are flushed before the turn stream opens (DoD-4)"` and `"sending clears whichever popover is open (DoD-5)"`. DoD-4's three cases are the contract most at risk; DoD-5's must still hold.
- **There is no component-level test anywhere that renders `ChatPane.tsx` and drives the model control through Testing Library** — no `getByLabelText("Model")` interaction test exists. The author's interaction spec needs one, and it goes in a new file rather than into the two above.

## External references

- `docs/architecture/frontend-workspace.md` → "Chat pane (feature 011, reshaped by feature `023.chat-ux-revision`)" — the `openedPanel` discriminator, the send-time flush, design-note D8's trade-off, feedback round 3 / F5, the vertical contract, and "Three known defects and one known gap" item 1.
- `docs/architecture/frontend.md` → Mantine inventory (`Popover` first use; `Menu.Item` vs `Popover`; the controlled-`Popover` binding rule), "React hook rules", "Effectful operations are external functions", "Testing".
- Product: UC-081 carries an open `_TBD:` about the lost-on-reload model change. **This plan does not edit `docs/product/`** — surfacing the reconciliation is the orchestrator's follow-up, closing it is `/product-spec`'s.
