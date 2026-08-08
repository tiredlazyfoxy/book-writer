# Outcome — 023.chat-ux-revision

Intended doc changes, grouped by target file. Seeded from `plan.md` → Decisions taken. Applied by
the architect at finalization, not by the coder.

## `docs/product/` (via `/product-spec` — not this feature)

- **Section:** `US-095.AC-1`, `US-105.AC-3`, `UC-081` step 1.
- **Intended change:** these describe the chat list opening "in the chat pane" — behaviour this
  feature removes. They need rewriting to describe the content-pane `/chats` list page and a
  pane-controller open-without-navigate flow instead.
- **Reason:** D1 — the user was shown the conflict explicitly and chose to build now and reconcile
  later. This obligation is **not discharged by this feature**; the code is deliberately ahead of
  the product docs as of `023.chat-ux-revision`. Flag for `/product-spec`.

## `docs/architecture/frontend-workspace.md`

- **Section:** Route map (`/work/:bookId/chats` row, ~line 79) — currently "redirect only".
- **Intended change:** describe it as a real content-pane route rendering the chats list page.
- **Reason:** D1/D5 — the redirect-only design this row documents is inverted by this feature.

- **Section:** "`/work/:bookId/chats` is a redirect — resolving this document's own contradiction"
  block (~lines 85-93).
  - **Intended change:** rewrite or remove; the contradiction it resolved (list-in-pane vs.
    route-link) is resolved the opposite way now. Should record the *new* resolution: the list
    lives on its own route, the Chats navigator entry is an ordinary router link, and the pane
    opens a picked chat via the `chatPaneController` registry without a route change.
  - **Reason:** D1, D5.

- **Section:** Navigator (~line 177), "Chats is the one entry that does not render into the content
  pane."
  - **Intended change:** false as of this feature — Chats now renders the list page into the
    content pane like every other entry. Update the navigator table and prose.
  - **Reason:** D1.

- **Section:** Chat pane (feature 011) — the parts table and "the list lives in the chat pane"
  framing.
  - **Intended change:** `ChatList.tsx` moves out of the pane's parts table into the chats list
    page's; the pane's parts table should read as header + model/settings popovers + transcript +
    composer, no list, no new-chat form, no Save-settings button. Add: background titling
    (`chat_titling.py`), the `chatPaneController` registry, the `openedPanel` popover state
    machine, and the settings-flush-before-send contract.
  - **Reason:** D1, D2, D5, D6, D7, D8.

## `docs/architecture/domain-chat.md` / `docs/architecture/assistant-runtime.md`

- **Section:** new — background chat titling.
- **Intended change:** document `POST /{book_id}/chats/{chat_id}/title`, the derive-from-count
  trigger (exactly the 1st and 5th user message, no new column), the swallow-on-failure policy
  mirroring `_finalize_close_turn_if_needed`, and that it is bound to the chat's own configured
  model pair (no utility/small-model designation exists or was added).
- **Reason:** D2, D3, D4. Also worth recording explicitly: this is the **first non-streaming
  `llm` client `.chat()` call** in the backend (every prior call site uses `chat_with_tools` or
  `embed_batch`), and the **first policy-owning endpoint of its kind** — an endpoint whose entire
  job is "maybe do nothing," which nothing else in the route inventory does.

## `docs/architecture/frontend.md`

- **Section:** MobX hard rules / Components — the module-registry idiom.
- **Intended change:** record `chatPaneController` as a third instance of the module-registry
  pattern alongside `closeTurnController` and `contentSubject`/`turnSubject`, and generalize the
  pattern description ("a page reaches shell-owned state via a register/unregister module, not
  context") as an established idiom rather than leaving each instance to read as a one-off.
- **Reason:** D5 — three independent features now converge on the same shape.

- **Section:** Components / Mantine inventory.
- **Intended change:** record `Popover` as the codebase's first use (introduced by this feature for
  the model/settings controls), alongside the existing `Menu` note, so the next feature reaching
  for a dropdown knows both exist and when each applies (`Menu.Item` for simple actions, `Popover`
  when the content doesn't fit a menu item — e.g. a `NumberInput`).
- **Reason:** D7.

## Observations

- A **controlled** Mantine v7 `Popover` (an `opened` boolean passed in) deliberately does **not**
  attach its own `onToggle` to `Popover.Target`, and its click-outside handler treats both the
  target and the dropdown as "inside" — so the target's own `onClick` owns the toggle with no
  double-fire, and dismissal (click-outside / Escape) comes back through `onChange(false)`, never
  through `onClose` alone. Possible impact: fold into the planner's existing
  `frontend.md` → "Mantine inventory / `Popover` first use" item, so the next controlled-popover
  call site does not rediscover it.
- The `llm` client's non-streaming `chat()` takes its whole request as one positional
  `list[LLMMessage]`; the titler therefore carries its instruction as a trailing synthetic **user**
  turn in the request rather than as a `system=` layer, which keeps the call one positional
  argument and leaves the chat's persisted transcript untouched. Possible impact: mention alongside
  the planner's `domain-chat.md` background-titling item as the shape of a one-shot,
  non-streaming, non-persisted model call.
- **`saveChatSettings` nulls the model pair on an unresolvable `optionKey` — pre-existing 011
  defect, still reachable.** It resolves the draft's key against `modelOptions` and falls back to
  `llm_server_id: null, model_name: null` when nothing matches. 023's `settingsDirty` guard closes
  only the `optionKey === null` door; the other stays open — when a chat's stored pair names a
  server or model no longer in `modelOptions` (server deactivated, model removed) the draft seeds
  to that *non-null* key, so a temperature-only edit reads dirty and the flush PATCHes an empty
  pair, clearing the chat's own server/model right before the turn that depends on it. Reachable
  identically through 011's Save button, so 023 added a second route to it, not the defect.
  Possible impact: a follow-up feature making an unresolvable `optionKey` leave the stored pair
  alone rather than null it.
- **The shell's chat-pane controller loads the opened chat's messages, not just the pointer.**
  `plan.md` → Interface sketches it as the single call `{ openChat: (chatId) => pickChat(...) }`;
  the shipped controller calls `pickChat` **and** `loadChatMessages`, because moving the pointer
  alone opens a chat while the previous transcript is still on screen (DoD-7 requires the
  conversation). Possible impact: when `frontend-workspace.md` records the `chatPaneController`
  seam, describe it as pointer + transcript so the plan's one-call sketch is not read as
  authoritative later.
- **Opening an ARCHIVED chat from the list page shows an empty pane.** `loadChatPane` loads only
  non-archived rows into `ChatPaneState.chats`, while the list page loads both sets, so an archived
  pick points `activeChatId` at a chat the pane has no row for and `activeChat` stays `null`. Out
  of scope here — no DoD covers it and UC-082 / US-096 scope the archived view to restore. Possible
  impact: a follow-up item (either the pane refetches on an unknown id, or the archived view offers
  restore only).
- **The settings popover surfaces no temperature validation message.** `ChatPaneState.errors`
  derives its `temperature` message from `newChatDraft`, while its only remaining consumer edits
  `settingsDraft` — so an out-of-range temperature typed into the popover shows nothing.
  Pre-existing 011 behaviour, deliberately left alone (no covering test, and changing it would move
  delivered behaviour). Possible impact: record as a known gap and fix wherever the settings
  surface is next touched.
- **Feedback round 1 / F3 SUPERSEDES this plan's `MessageList.tsx` interface text and narrows D9.**
  The plan's `## Interface` says the assistant row carries "a role label, a `Divider` before each new
  turn"; the author's DoD-18 review had both removed as redundant chrome once F2's stronger user
  bubble carries authorship on its own, and because in a narrow column they spent the vertical space
  F1 reclaims. Shipped state: assistant rows are the `<Stack data-role="assistant">` wrapper, the
  optional `ThinkingBlock` and the markdown body — nothing else. Possible impact: reword that
  Interface line and design-note D9 (its "role label, divider between turns" clause only) so the
  plan text matches what shipped; D9's *asymmetry* rationale — user bubbled, assistant full-width
  because bubbling would shorten every line of the author's working content — is unchanged and
  still the reason the treatment is one-sided.
- **Feedback round 1 / F1's missing flex chain was an 011-era defect, not a 023 regression.** The
  320px `mah` on the transcript's scroll container and `ChatPane`'s root `h="100%"` both pre-date
  023 (`git diff HEAD` shows neither was touched); 011's in-pane chat list, new-chat form and
  Save-settings block had been occupying the slack that hid the gap, so removing them is what made
  it visible. Repaired in 023 because 023 owns the pane's current shape. Possible impact: when
  `frontend-workspace.md` records the pane's parts, state the vertical contract explicitly — the
  aside is fixed-height, the pane root fills it, the transcript is the single growing child
  (`flex: 1` + `minHeight: 0`) and the composer is non-shrinking — so the next pane change cannot
  silently break the chain again.
- **The transcript still does not auto-scroll to the newest message, and that is now conspicuous.**
  Before F1 the region was capped at 320px and rarely the thing that scrolled; now that it fills the
  pane and scrolls internally, a streaming turn writes below the fold with no follow. Explicitly out
  of scope for the feedback round (new behaviour, not a repair) and left unbuilt. Possible impact: a
  follow-up feature — `frontend.md` already sanctions the mechanism (one `autorun` in the pane-level
  mount effect, never a `useEffect` in the `MessageList` leaf).
- **Feedback round 2 / F4 establishes the repo's first icon-in-input control, and the recipe has
  three traps worth writing down.** There was no `rightSection` usage anywhere in `frontend/src`
  before this. (1) `rightSectionPointerEvents` defaults to **`"none"`** — an icon control placed in
  a section without `"all"` renders correctly and is completely dead to the pointer, and
  `fireEvent`-based tests will not catch it because they dispatch without hit testing. (2) The
  section is `position: absolute` spanning `top: 1px`/`bottom: 1px` with `align-items: center`, so
  it re-centres as an autosizing input grows; corner anchoring needs `rightSectionProps` to override
  the alignment. (3) The default section width derives from `--input-height`, which an autosizing
  `Textarea` has no fixed value for, so an explicit `rightSectionWidth` is what makes both the slot
  and the input's text padding deterministic. Also useful: Mantine's disabled-input styling targets
  the input element, not its sections, so a control in a section stays live and undimmed while the
  input itself is `disabled` — which is exactly what lets Stop sit inside a textarea that is
  disabled mid-stream. Possible impact: add to `frontend.md`'s Mantine inventory beside the
  `Popover` note, as the icon-in-input pattern with these four facts attached.
- **011's composer description is now stale.** The Send control is no longer a `Button` in a row
  below the textarea; Send and Stop are icons inside the input's bottom-right corner, swapping in
  one slot. Possible impact: wherever `frontend-workspace.md` describes the chat pane's composer
  parts, describe the control as in-input and note that the accessible names (`Send` / `Stop`) are
  the only handle on it, since an icon control renders no text.
