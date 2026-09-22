# Feedback — 023.chat-ux-revision

## Round 1 — 2026-08-08 — Chat pane vertical layout and message treatment

Delivered 2026-08-08, verifier PASS. This round is the author's DoD-18 visual review
(`[manual/live]`, previously outstanding) coming back negative. All three items are `reshape`:
the pane's functional behaviour is correct and must not move — what is wrong is the layout
implementation and the visual treatment.

**No repro tests in this round.** jsdom has no layout engine, so no automated test can observe a
flex-chain or a tint, and the delivered plan's `## Test plan` already excludes
"message bubble / divider / role-label styling" as pure presentation. The binding baseline is
therefore the existing suite: **706/706 frontend tests must stay green**, and the
`data-role="user"` / `data-role="assistant"` hooks — the plan's stated authorship contract —
must survive every change below. B2 skips the red gate for this round.

### F1 — Transcript does not fill the pane; composer floats mid-column   [kind: reshape]   [target: plan.md]
- Reported: "the chat now looks bad - vertically not aligned, uses only half of vertical space".
  Confirmed on the follow-up as the pane height chain alone — the message rows themselves are not
  the complaint here (see F2/F3 for those).
- Expected: the transcript region consumes all vertical space left over between the pane header and
  the composer, scrolling internally when the conversation is longer than the space available. The
  composer sits at the bottom edge of the pane regardless of transcript length. No dead space
  below the composer, at any pane height or any conversation length — including an empty chat.
- Evidence: `MessageList.tsx`'s scroll container is `<ScrollArea.Autosize mah={320} type="auto">` —
  a hard-coded 320px ceiling that **caps** rather than fills. Nothing in the chain declares
  `flex: 1` or `minHeight: 0`: `AppShell.Aside` is `position: fixed` and does have a real bounded
  height, and `ChatPane`'s root `<Stack gap="sm" h="100%">` correctly fills it, but no descendant
  is told to consume the remainder. `Composer` is simply the next sibling in that `Stack` with no
  `mt="auto"` and no sticky/absolute positioning, so it flows directly after whatever height the
  transcript produced and the rest of the column is left blank beneath it.
  **Provenance:** both the 320px cap and the root `h="100%"` pre-date 023 — `git diff HEAD` shows
  neither was touched by this feature. 023 removed the "Show archived" switch, the inline new-chat
  form, the in-pane `ChatList` and the Save-settings block, and that bulk had been masking the gap.
  The defect is 011-era; 023 made it visible and owns the repair because it owns the pane's
  current shape.
- Areas: `frontend/src/work/components/chat/ChatPane.tsx`,
  `frontend/src/work/components/chat/MessageList.tsx`,
  `frontend/src/work/components/chat/Composer.tsx` (only if pinning genuinely requires it).
  All inside the delivered plan's declared Source areas.
- Constraints: preserve every functional behaviour of the pane — streaming deltas and the thinking
  region, composer gating and read-only states, mid-stream abort, retry, the close-turn / canvas /
  content-selection wiring from features 013/015/016, and both header popovers driven by the single
  `openedPanel` discriminator. Preserve `data-role` on both row kinds. Signature: **frozen** —
  `MessageListProps`, `ComposerProps` and `ChatPaneProps` do not change. Note for the implementer:
  a `flex: 1` scroll child needs `minHeight: 0` on itself and its flex ancestors or it refuses to
  shrink below content size, trading this symptom for an overflow one.
- Out of scope: auto-scrolling to the newest message. The transcript does not do this today, and
  adding it is new behaviour, not feedback — worth a separate feature once the region actually
  scrolls. Also out: any change to the horizontal resize rail (fast/005) or to `AppShell` itself.
- STATUS: DONE
- Changes: `MessageList.tsx` root goes from `<ScrollArea.Autosize mah={320} type="auto">` to
  `<ScrollArea type="auto">` carrying `flex: 1` + `minHeight: 0`, so it fills the space between
  header and composer and scrolls internally; the 320px cap is gone. `ChatPane.tsx` root `Stack`
  gains `mih={0}` beside its existing `h="100%"`. `Composer.tsx` root `Stack` gains
  `flexShrink: 0` — the transcript grows from a zero flex basis and absorbs the shrinkage, so
  without this the composer would be squeezed first when the retry or read-only banner shows.
  All three props interfaces unchanged. Verified PASS 2026-08-08: the verifier judged the chain
  correct rather than symptom-moving, and established that `mih={0}` is **required**, not
  defensive — Mantine's `AppShell.css` already makes `AppShell.Aside` a flex column, so
  `ChatPane`'s root is already a flex item whose automatic minimum would otherwise be its content
  height. `minHeight: 0` is present on both links that need it; the resize handle is
  `position: absolute` and `ChatPaneSlot` adds no wrapper, so the chain has no undeclared link.
  No auto-scroll added (no `scrollIntoView`/`scrollTo`/`useEffect`/`useRef` anywhere in the three
  files); no `AppShell` or resize-rail change.

### F2 — User bubble does not read as a bubble in a narrow pane   [kind: reshape]   [target: plan.md]
- Reported: the user-bubble treatment from DoD-18's review needs changing. Direction chosen:
  "tighter cap, stronger tint".
- Expected: reduce the bubble's max-width from 85% to roughly 70% so a right-offset bubble is
  visibly narrower than the assistant's full-width body, and strengthen the fill so the tint alone
  carries authorship without help from a label or a rule. Assistant messages stay full-width —
  that is deliberate (design-note D9: bubbling the assistant would narrow the author's actual
  working content).
- Evidence: the chat pane is a narrow, resizable aside, so an 85% cap is nearly indistinguishable
  from full width — the bubble reads as a slightly-inset paragraph rather than a distinct
  authorship signal. Current markup:
  `<Paper bg="var(--mantine-color-blue-light)" px="sm" py={6} radius="md" style={{maxWidth:"85%"}}>`
  inside a `<Box data-role="user" style={{display:"flex", justifyContent:"flex-end"}}>`.
- Areas: `frontend/src/work/components/chat/MessageList.tsx`.
- Constraints: preserve `data-role="user"` and the right-offset flex mechanism. The tint must
  satisfy Mantine's light and dark schemes — use theme tokens, not a hard-coded colour. Text must
  stay legible against the stronger fill. Signature: **frozen**.
- Out of scope: none.
- STATUS: DONE
- Changes: `MessageList.tsx` — bubble `maxWidth` 85% → 70%; fill strengthened from
  `--mantine-color-blue-light` to `bg="var(--mantine-primary-color-filled)"` with
  `c="var(--mantine-primary-color-contrast)"`. Verified PASS 2026-08-08: both are theme tokens,
  not hard-coded colours, and `contrast` is the token Mantine itself pairs with `filled`, so the
  pairing tracks light and dark by construction rather than by a hand-picked value. The
  `data-role="user"` wrapper and its right-offset flex mechanism (`display: flex` +
  `justifyContent: flex-end`) are intact; the assistant row carries no width constraint and so
  remains full-width, honouring D9.

### F3 — Per-turn divider and "Assistant" label are redundant chrome   [kind: reshape]   [target: plan.md]
- Reported: the divider / role-label treatment from DoD-18's review needs changing. Direction
  chosen: "drop both".
- Expected: remove the `<Divider>` rendered before each new assistant turn and remove the dimmed
  "Assistant" text label above each assistant block. With F2's stronger bubble carrying authorship,
  both are redundant, and in a narrow column they cost vertical space that F1 is trying to reclaim.
  The assistant's markdown body and the thinking region are unaffected.
- Evidence: current assistant row is
  `<Stack gap={4} data-role="assistant">` containing `{index > 0 && <Divider mt="xs" />}`, then
  `<Text size="xs" fw={600} c="dimmed">Assistant</Text>`, then the optional `ThinkingBlock`, then
  the markdown `<Box className="chat-markdown">`.
- Areas: `frontend/src/work/components/chat/MessageList.tsx`.
- Constraints: **the wrapping `<Stack data-role="assistant">` must remain** — only its `Divider`
  and label children are removed. `ThinkingBlock` rendering and the markdown body are untouched.
  Signature: **frozen**.
  This supersedes the delivered plan's `## Interface` description of `MessageList.tsx`
  ("a role label, a `Divider` before each new turn") and narrows design-note D9. No `[test]`
  DoD item asserts either element — the plan's `## Test plan` puts this styling on the
  deliberately-not-tested list — so the delivered DoD does not regress. DoD-18 is re-exercised by
  the author after this round.
- Out of scope: any change to `ThinkingBlock`, to the markdown renderer, or to the user row
  (F2 owns that).
- STATUS: DONE
- Changes: `MessageList.tsx` — the per-turn `<Divider>` and the dimmed "Assistant" label are
  removed from the assistant row, along with the now-unused `index` map parameter and the `Divider`
  import that went dead with them. Verified PASS 2026-08-08: the wrapping
  `<Stack gap={4} data-role="assistant">` remains, and `ThinkingBlock`, the markdown body and the
  `hasReasoning`/`expanded`/`toggle` logic are byte-identical to the delivered version; dropping
  `index` did not disturb either branch's `key={msg.key}`. The verifier confirmed the supersession
  breaches nothing: no `[test]` item mentions either element, no `[verify]` item touches
  `MessageList`, `## Skeleton` froze nothing for it, and the two elements appear in the DoD only in
  DoD-18 — a `[manual/live]` review gate the author owns, which this round *is*. The obligation is
  paperwork: the plan's `## Interface` line for `MessageList.tsx`, design-note D9's
  role-label/divider clause, and DoD-18's own wording (which still names both removed elements) are
  now stale and are recorded for finalization in `outcome.md` → `## Observations`.

---

## Round 2 — 2026-08-08 — Composer send affordance

Author request: "remove 'send' button, make icon inside the texbox to save the space". Raised via
`/bug-fixer`, but 023 is an ultra-track feature (`docs/plans/<NNN>.<feature>/plan.md`, single plan,
no step files), and ultra's feedback mode is the flow that replaces `/bug-fixer` and `/rewrite` for
features delivered here — recorded and applied as feedback round 2 rather than switching pipelines.

**This is a `reshape`, not a bug.** Sending already works, by button and by `Ctrl`/`Cmd`+`Enter`
(DoD-6). The item relocates an existing affordance to reclaim vertical space, continuous with F1's
intent. No new behaviour, therefore no repro test and no red gate — same shape as round 1. The
delivered suite remains the baseline: **706/706 frontend and 1246 backend must stay green.**

### F4 — Send button costs a whole row below the textarea   [kind: reshape]   [target: plan.md]
- Reported: "remove 'send' button, make icon inside the texbox to save the space".
- Expected: the `<Group justify="flex-end">` row holding the Send/Stop `Button` is removed
  entirely, and its function moves to an icon control rendered **inside** the `Textarea`, anchored
  to the **bottom-right corner** and staying anchored as the textarea autosizes from `minRows={2}`
  to `maxRows={6}` (author's explicit choice over vertical centring). Stop takes the **same slot**,
  swapping with Send while streaming — leaving a button row behind for Stop alone would defeat the
  item. Net effect: one full control row of vertical height returned to the transcript.
- Evidence: `Composer.tsx` currently ends with
  `<Group justify="flex-end">{streaming && !closeReadOnly ? <Button color="red" variant="light"
  onClick={onStop}>Stop</Button> : <Button onClick={onSend} disabled={!state.canSend ||
  closeReadOnly}>Send</Button>}</Group>` — a full-width row whose only content is one button.
- Areas: `frontend/src/work/components/chat/Composer.tsx`.
- Constraints:
  - **Accessible names are the binding contract.** Harvest of the whole test tree found the Send
    control has **no test query at all** — not by role, name, text, label or placeholder — so it
    converts freely. But `Stop` and `Retry` ARE load-bearing: `ChatConversation.test.tsx` uses
    `getByRole("button", {name: /stop/i})` and `getByRole("button", {name: /retry/i})`. An
    icon-only Stop therefore **must** carry `aria-label="Stop"` (or a name matching `/stop/i`),
    since for an `ActionIcon` the aria-label *is* the accessible name. Give the send icon an
    explicit `aria-label` too — Mantine icon-only controls render no text.
  - **`getByRole("textbox")` must still resolve to exactly one element** (used in
    `Composer.test.tsx` and `ChatConversation.test.tsx`). An `ActionIcon` inside the input is a
    `button`, not a second textbox, so this holds — but nothing may be added that changes the
    textarea's own role or accessible-name resolution.
  - **Gating reproduced verbatim:** the send control keeps `disabled={!state.canSend ||
    closeReadOnly}`. Note `canSend` does **not** itself check `isComposerReadOnly` —
    `Composer.tsx` ANDs `closeReadOnly` in separately, and that must not be simplified away. The
    Stop/Send swap condition stays `streaming && !closeReadOnly`, preserving the delivered
    behaviour that during a close window the composer shows Send-disabled rather than Stop (the
    chapter page's own Stop owns that exit).
  - **`Ctrl`/`Cmd`+`Enter` (DoD-6) is untouched** — same handler, same `canSend`/read-only gate.
  - The retry `Button` inside the red `Alert` stays exactly as delivered; it is not part of this
    item.
  - Signature: **frozen** — `ComposerProps` (`state`, `onSend`, `onStop`, `onRetry`) unchanged.
  - Implementation note: Mantine 7.17.8's `rightSection` is `position: absolute` with `top` and
    `bottom` both pinned to 1px and `align-items: center`, so it **re-centres** as the textarea
    grows — it will not produce corner anchoring on its own. Bottom-right needs either
    `rightSectionProps` overriding the flex alignment or an absolutely-positioned overlay outside
    the `rightSection` mechanism. There is **no existing `rightSection` or icon-in-input usage
    anywhere in `frontend/src`** — this establishes the pattern. Match the chat pane's existing
    `ActionIcon` idiom (`@tabler/icons-react` at `size={18} stroke={1.5}`, explicit `aria-label`,
    `variant="light"` for an action trigger).
- Out of scope: the two `Alert` banners (read-only and retry) and their vertical cost; any change
  to `canSend`, `turnStatus`, `retryOffered` or `isComposerReadOnly` in `chatPaneState.ts`; tab-order
  or focus-management changes beyond what moving the control implies; auto-scroll (still deferred
  from F1).
- STATUS: DONE
- Changes: `Composer.tsx` — the `<Group justify="flex-end">` row is removed; Send and Stop now render
  in the `Textarea`'s `rightSection` as `ActionIcon`s (`IconSend` / `IconPlayerStop`,
  `size={18} stroke={1.5}`, `variant="light"`, Stop in red with `aria-label="Stop"`, Send with
  `aria-label="Send"`), swapping in one slot on the unchanged `streaming && !closeReadOnly`
  condition. Bottom-right anchoring took three settings: `rightSectionProps` overriding
  `align-items` to `flex-end` (plus a 4px `paddingBottom` nudge off the border),
  `rightSectionWidth={40}` (the default derives from `--input-height`, which an autosizing textarea
  has no fixed value for, and it also drives the text gutter), and `rightSectionPointerEvents="all"`.
  Verified PASS 2026-08-08 against the installed Mantine 7.17.8 package rather than from general
  knowledge — all three of the coder's load-bearing claims check out:
  (1) `rightSectionPointerEvents` really does default to `"none"` (`Input.mjs:30-35`), so without
  the override the control would have rendered visible and **completely inert to real clicks, and
  no test could have caught it** — Mantine's stylesheet is not loaded into jsdom, so `user.click`
  does not honour `pointer-events` there. The comment at `Composer.tsx:31-36` is the only guard on
  this and is load-bearing.
  (2) Disabled styling targets the input element only — every disabled rule hits `.m_8fb7ebe7`
  (the input), and **no `[data-disabled]` rule on the wrapper exists at all**; the section is a
  sibling of the input, so `opacity: .6` cannot cascade to it. Stop therefore stays live and
  undimmed inside a `Textarea` that is `disabled` mid-stream — **mid-stream abort is reachable**,
  which is what the whole change rests on.
  (3) The `alignItems` override survives because `getStyles` *merges* the caller's style into the
  emitted inline style rather than the later spread clobbering it.
  Preserved verbatim: `disabled={!state.canSend || closeReadOnly}` with `closeReadOnly` still ANDed
  in separately, the `Ctrl`/`Cmd`+`Enter` handler (DoD-6, byte-identical), the retry `Button` and
  both `Alert` banners, F1's `flexShrink: 0` on the root `Stack`, and `ComposerProps`.
  `getByRole("button", {name: /stop/i})` and `{name: /retry/i}` still resolve, and
  `getByRole("textbox")` still matches exactly one element.

---

## Round 3 — 2026-08-09 — Model change is invisible until the next send

Author report, raised while reviewing feature 024: "when i change model it doesn't change
immidiatelly in the interface, just after mesage post."

**Diagnosed before filing.** The code is faithful to the delivered plan — this item objects to a
**design decision**, not to a defect, and therefore supersedes part of it. Recorded here rather
than as a bug because no contract is being violated: `modelLabel` does exactly what
`plan.md:193-194` specifies.

**Direction is not yet chosen** — see the two options under F5. B2 must not be dispatched until
the author picks one, because they lead to materially different code.

### F5 — Header model label lags the author's pick until a message is sent   [kind: reshape]   [target: plan.md]
- Reported: "when i change model it doesn't change immidiatelly in the interface, just after
  mesage post."
- Expected: choosing a model in the header popover is reflected in the header **immediately**,
  without requiring a message to be posted first. Exactly *how* it becomes immediate is the open
  choice below.
- Evidence: **not a defect — designed, and implemented as designed.** The `<Select>`'s `onChange`
  writes only the draft (`ChatPane.tsx:131-140`, `state.settingsDraft.optionKey = value`), while
  the header label is a separate computed reading the **persisted** pair
  (`chatPaneState.ts:467-480`, `this.activeChat.llm_server_id` / `chat.model_name`, joined against
  `modelOptions` for display names; never `settingsDraft`). The popover's own `Select` *does*
  update instantly — `state` is observable and the component is an `observer` — so the author sees
  their pick inside the popover but not in the header, which is precisely the confusing part.
  023 removed the Save-settings block (`status.md:42-45`, `plan.md:214-217`: "No … 'Save settings'
  button anywhere in the tree"), so **`sendChatTurn`'s flush is now the only path in the whole app
  that persists a model change** (`chatPaneState.ts:1009-1017`, gated on `settingsDirty`).
  `saveChatSettings` then replaces the chat row with the server's response
  (`chatPaneState.ts:867-879`) — *that* row-replacement is what finally moves the label, at send
  time. The lag is the designed invariant, spelled out in the code's own doc-comment
  (`chatPaneState.ts:460-466`: "so the header always names the model the next turn will actually
  use") and in **design-note D8** (`plan.md:401-406`), which chose it because the backend's
  `prepare_turn` reads the chat's **stored** pair, not any client draft. D8's own recorded
  trade-off: "settings changed but never followed by a message are lost on reload — the literal
  spec'd behaviour."
- Options (**author must choose before B2**):
  - **(A) Label follows the draft.** `modelLabel` prefers `settingsDraft.optionKey` resolved
    through `modelOptions` while `settingsDirty`, falling back to the persisted pair when clean.
    Smallest change, one computed. **Cost:** the header would name a model the system cannot yet
    honour — if the flush later fails (`chatPaneState.ts:1011-1016` returns without opening the
    stream), the label keeps showing a pick that no turn will use. It also directly contradicts the
    `:460-466` doc-comment and D8's rationale, and leaves D8's lost-on-reload trade-off in place.
  - **(B) Persist on pick (recommended).** `onChange` calls `saveChatSettings` directly, so the
    stored pair moves at pick time and the label — unchanged — becomes immediate *and* stays
    truthful. **Also retires D8's lost-on-reload trade-off**, which is a genuine improvement rather
    than a swap. **Cost:** one API call per pick; needs the in-flight/error path thought through
    (what the header shows while the update is in flight, and on failure) and the send-time flush
    kept for the temperature control, which has no equivalent commit point.
- Areas: `frontend/src/work/components/chat/chatPaneState.ts` (`modelLabel`, and for (B) the
  `onChange` effect path), `frontend/src/work/components/chat/ChatPane.tsx` (the `Select` binding).
  Both inside the delivered plan's declared Source areas.
- Constraints: preserve the send-time flush for **temperature** either way — `settingsDirty` and
  `sendChatTurn`'s ordering are pinned by DoD-4 and by
  `frontend/tests/work/chatPaneSettings.test.ts` ("settings are flushed before the turn stream
  opens (DoD-4)", `:148`; "sending clears whichever popover is open (DoD-5)", `:217`). Under (B)
  a picked-and-persisted model must leave `settingsDirty` false so the send issues **no** second
  update call — DoD-4 clause 2 ("a pane the author has not edited issues no update call"). Preserve
  `NO_MODEL_LABEL` for a chat with no pair, and the existing fallback where a pair whose server is
  no longer offered still shows its bare `model_name` (`chatPaneState.ts:473-479`). Signature:
  `get modelLabel(): string` **frozen**; under (B) the `Select`'s `onChange` may become a call to
  an effect fn.
- Note on coverage: **no existing test asserts `modelLabel`'s value** — the only mentions under
  `frontend/tests` are doc-comment references to the frozen signature (`ChatPane.test.tsx:20`,
  `chatPaneSettings.test.ts:7`). So neither option breaks an existing assertion, and this item
  should gain one.
- Out of scope: the temperature control's own commit semantics beyond keeping the flush working;
  any change to `prepare_turn` or the backend's stored-pair contract; auto-scroll (still deferred
  from F1).
- STATUS: TBD
- Changes: —
