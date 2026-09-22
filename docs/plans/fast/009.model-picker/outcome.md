# fast/009.model-picker — Intended documentation changes

Applied at finalization by the architect. Grouped by target file.

## `docs/architecture/frontend-workspace.md`

### 1. Chat pane — the parts table and the popover description

- **Section:** "Chat pane (feature 011, reshaped by feature `023.chat-ux-revision`)" — the parts table row for `ChatPane.tsx`, and the surrounding prose that calls the model control a popover.
- **Change:** Record that the model control is no longer a `Popover` wrapping a `<Select>`. It is a **Mantine `Combobox`** whose option list is open as soon as the control is, with a focused search field above it: one click opens, typing filters, click or Enter picks. The settings control remains a `Popover`. Add the accessible-name contract — the target keeps `aria-label="Model"`, the search input is `"Search models"`, options read `"<server_name> · <model_name>"`, and the three labelled non-option lines are `"No models available"`, the loaded options error, and `"Nothing found"`.
- **Reason:** The pane's parts table is where a reader learns what each header control is. Left as-is it describes a widget that no longer exists, and the accessible names are a test contract (the same reasoning the document already applies to the composer's `Send` / `Stop`), so they belong in the architecture rather than only in a plan.

### 2. Chat pane — the `openedPanel` discriminator is unchanged, and why it survived a widget swap

- **Section:** "One `openedPanel` discriminator drives both header popovers."
- **Change:** Keep the paragraph, and add that the model control's `useCombobox` store is used in **controlled** mode precisely so `openedPanel` stays the single source of truth — opening one surface still closes the other by construction, and an accepted send still clears whichever is open. Note that `frontend.md`'s controlled-`Popover` binding rule applies transitively because `Combobox` is built on `Popover`: the target owns the toggle, dismissal returns through the open-change callback, and both directions must be bound.
- **Reason:** The obvious way to adopt `Combobox` is to let its store own its own open state, which would silently drop the by-construction mutual exclusion. Recording why it was kept prevents the next widget swap from losing it.

### 3. Chat pane — the send-time flush is no longer the only path that persists a model change

- **Section:** "**A consequence worth stating plainly.**" (the paragraph beginning "With the Save-settings button gone, that send-time flush is **the only path in the whole app that persists a model change**").
- **Change:** Rewrite it. A **model** pick now persists immediately through the chat update endpoint, which is why the header label moves at once and why the pick survives a reload; the header is written optimistically and reverts with an author-facing error if the update fails. Design-note **D8's accepted trade-off now applies to temperature only** — a creativity change made and never followed by a message is still lost on reload. **Feedback round 3 / F5 is closed** by feature `fast/009`: the header no longer lags the author's pick. Record that the send-time flush itself is unchanged and still mandatory — the backend's turn preparation reads the chat's **stored** pair (`assistant-runtime.md`), a dirty draft is still flushed before the stream opens, and a failed flush still aborts the send — and that the pick re-seeds only the **model half** of the settings draft, so a pick followed by a send issues no redundant update.
- **Reason:** This paragraph is the document's record of a known, accepted defect. Half of it is now false and the other half is still true, and the distinction between the two halves (model immediate, temperature still deferred) is exactly what a later reader needs.

### 4. Chat pane — known defect 1 is fixed

- **Section:** "#### Three known defects and one known gap", item 1 ("An unresolvable saved model option silently clears the chat's model pair").
- **Change:** Remove item 1 and renumber the remaining two; retitle the section to **"Two known defects and one known gap"**. Replace the removed item with a short line in the settings prose: an option that does not resolve against the loaded catalogue now causes the update request to **omit** `llm_server_id` and `model_name` entirely rather than send a null pair, so a stored pair naming a deactivated server or a withdrawn model is left alone; and `modelLabel` falls back to the stored `model_name` so the header keeps showing the real pair instead of blanking.
- **Reason:** The list exists so defects are recorded once rather than rediscovered; leaving a fixed one in it is worse than never listing it. The *replacement* line matters because "why does this request omit the pair instead of sending it" is a question the next reader of `saveChatSettings` will ask, and the answer is a deliberate design choice, not an oversight.

### 5. Product reconciliation owed — UC-081's `_TBD:`

- **Section:** the same "A consequence worth stating plainly" area, or wherever the document records open product questions.
- **Change:** Note that `docs/product/`'s open `_TBD:` on **UC-081** — recording that a model change made and never followed by a message is lost on reload — is now **half stale**: it holds for temperature and no longer holds for the model. Flag it as owed to `/product-spec`.
- **Reason:** `docs/architecture/` is read-only toward `docs/product/` and must never close a divergence by editing product. Recording the debt is the only correct action from this side.

## `docs/architecture/frontend.md`

### 6. Mantine inventory — `Combobox` is new, and so is the focus-on-open idiom

- **Section:** the Mantine inventory, immediately after the `Popover` entry ("**`Popover` — first use in the repo (feature `023.chat-ux-revision`)**").
- **Change:** Add an entry for **`Combobox` + `useCombobox` — first use of the raw primitive in the repo (feature `fast/009.model-picker`)**, beside the existing `Select` (which is a wrapper over it). Record three things:
  - **When to reach for it:** a `Popover` whose only content is a `<Select>` is a dropdown containing a closed dropdown and costs three clicks to make one choice. Unwrap it to `Combobox` rather than adding a second widget.
  - **Controlled mode:** the store is driven by the owning state class's own open flag when that flag also arbitrates against a sibling surface, so the exclusion stays by-construction rather than by a handler that remembers to close its sibling.
  - **Focusing the search input on open without a `useEffect`:** `autoFocus` on the search input is sufficient and preferred, because the dropdown's content **mounts on open** (`keepMounted` off), so the mount does the focusing. No ref, no effect, no custom hook — which is what keeps the leaf-component rules intact. `useCombobox`'s `focusSearchInput()` from a store callback is the fallback, and it is a fallback because it depends on the dropdown already being mounted when the callback fires.
- **Reason:** The inventory is where the repo records which Mantine component answers which shape of problem. A focus-on-mount answer that does not need an effect is exactly the kind of thing the next feature will otherwise re-derive by reaching for a forbidden `useEffect`; and `withinPortal: false` plus jsdom's lack of hit-testing makes the testable configuration non-obvious enough to write down.

## Observations

- Mantine's `Combobox` defaults `keepMounted` to **`true`** (unlike a bare `Popover`, which defaults to `false`), so the "`autoFocus` works because the dropdown content mounts on open" idiom only holds if `keepMounted={false}` is passed **explicitly**; a kept-mounted dropdown mounts once at first render and never re-fires `autoFocus`. Possible impact: add the explicit-`keepMounted={false}` caveat to the `Combobox` entry planned for `frontend.md`'s Mantine inventory (outcome item 6).
- Mantine's built-in Enter handling only clicks an option that is **already highlighted** (its selected index starts at `-1`), and Mantine's own `Select` highlights the first option after a needle change from a `useEffect` — which leaf components here may not use. "Enter picks the first filtered option" is therefore implemented as an explicit `onKeyDown` on the search input that fires **only while nothing is highlighted**, leaving arrow-key navigation and Enter-picks-the-highlighted-option to Mantine and avoiding a double submit. Possible impact: record this split in the same `frontend.md` `Combobox` inventory entry, since the next `Combobox` use will hit the identical `useEffect` temptation.
- A side effect of that split: after typing in the search field, **no** option is visually highlighted until an arrow key is pressed (the highlight is dropped rather than moved to the first option, because moving it would read a stale DOM list). Enter still picks the first filtered option, and ArrowDown still lands on it. Possible impact: worth a sentence in `frontend-workspace.md`'s model-control description if DoD-14's live check finds the missing highlight confusing.
