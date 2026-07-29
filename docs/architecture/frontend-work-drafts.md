# Frontend Work Drafts — the restore buffer and the module-state tier

**Realizes:** FEAT-013, FEAT-018; UC-076, UC-077, UC-092; US-041, US-088, US-095, US-103, US-107

The working page's **device-local draft tier**: the restore buffer, the module-state modules that live beside it, the canvas target registry, and the reconciliation view they feed.

This was carved out of `frontend-workspace.md` when features 011 and 013 built it out. What began as one section — a buffer design table and a stale-version rule — is now a cohesive subsystem with three modules, two writers, two entrances to reconciliation, and a set of exclusions that need sanctioning as explicitly as its inclusions. Keeping it inside the workspace topology doc would have pushed that doc past the folder's ~400-line rule and buried the tier inside a document about routes and panes.

Read alongside:

- **`frontend-workspace.md`** — the Vite entries, the route maps, the working page's navigator / content pane / chat pane.
- **`frontend.md`** — the MobX state ladder this tier is a sanctioned exception to, and the `localStorage`-not-URL reasoning in short form.
- **`domain-chapter.md` → "Concurrency"** and **`domain-codex.md` → "Concurrency"** — the server side of the version-token contract this buffer consumes. The buffer stores what those sections define; it does not define it.
- **`assistant-runtime.md`** — the server side of the `canvas` frame the registry below dispatches.

## Draft-until-saved and the restore buffer

Edits in the content pane are **drafts until explicitly saved**. Nothing reaches the server, and nothing reaches a co-author, until the author saves (US-103.AC-3, US-107.AC-4).

### Buffer design

| Property | Decision |
|---|---|
| Storage | **`localStorage`** — device-local browser storage |
| Scope | one buffer **per item**, keyed `(bookId, subjectKind, subjectId)` |
| Contents | the draft text, the `Chapter.version` (or codex entry `modified_at`) it forked from, and when it was written |
| Privacy | private to the author, on that device; **invisible to co-authors** (US-107.AC-3) |
| Lifetime | survives navigating away, a full reload, and closing the browser (US-107.AC-1/AC-2) |
| Loss | **lost if browser data is cleared** — accepted and stated to the author |
| Status | **never a substitute for saving** |

**`localStorage`, not `sessionStorage`**, because product requires the buffer to survive a full reload and be there "next day" — `sessionStorage` dies with the tab. **Not the server**, because the buffer is explicitly device-local and private; persisting drafts server-side would make them co-author-visible content the moment anything queried them, which is the opposite of the requirement.

**Keyed per item, not per pane**, so editing chapter 3, jumping to a codex entry and coming back restores chapter 3's draft rather than the last thing typed anywhere.

**Accepted limitation — quota.** `localStorage` is a few megabytes per origin, and a chapter body is not small. When a write hits quota, the oldest buffers are evicted, oldest-first, and the author is told. Silently dropping the buffer they are currently typing into would be the one unacceptable outcome, so the *current* item's buffer is never the eviction victim. A write that succeeded only after evicting others reports **`saved-after-eviction`** with the evicted keys, and the entry page **surfaces that to the author** — an eviction is data loss on some other item, so it is never silent.

### The principal-text-field rule

`BufferedDraft.draft` is a **single string**, and the first real subject — a codex entry — has **two** editable fields. `restoreBuffer.ts` was **deliberately not widened** to a `(name, body)` pair: the body is the substantive content the buffer exists to protect, while the name is small, always visible on screen, and cheap to retype.

The rule, stated so the chapter and book-state surfaces copy it rather than each inventing an encoding:

> **A multi-field subject buffers its principal text field.**

Its accepted consequences, both real:

- An **unsaved name is lost** on an unload.
- The reconciliation view **compares bodies only**.
- Its corollary, on the assistant side: a `canvas` frame targeting the **name** that arrives with **no registered target is dropped, not buffered** — writing it would surface a name where the body belongs. **A non-principal field written while the subject is not open is lost.**

That corollary is a reason to keep the buffer's shape **per item rather than per field** only until a subject genuinely needs more. When one does, widening the shape is a deliberate change to this rule, not a local fix at one call site.

### Where the buffer lives in the state ladder

**Module-level state in the `work` entry, not `<Page>State`.** `frontend.md`'s ladder puts app-lifetime state at the module level (`auth.ts` is the existing example, and it already reads `localStorage`). The buffer must outlive any page-state instance by definition — surviving a reload is the requirement — so a page-scoped home would be wrong even before the remount question. The buffer module (`src/work/restoreBuffer.ts`) exposes plain functions (`restoreBufferKey(...)`, `readBuffer(key)`, `writeBuffer(key, draft, baseVersion)`, `clearBuffer(key)`); it is not a reactive store, matching how `auth.ts` is treated. Reads are **total** — an absent, non-JSON or wrong-shaped entry returns `null` rather than throwing, because a corrupt buffer must never be able to break the page it belongs to.

This is a **sanctioned exception** to `frontend.md`'s "URL query params are the persistence layer" rule. That rule is about *view* state — filter, sort, mode, scroll anchor — which is small, shareable and belongs in a bookmarkable URL. Draft content is none of those things: it is large, private, and must not travel in a link. Recorded here so the exception is deliberate rather than drift.

**Feature 010 shipped it as a pure module with no writer.** Nothing imported it but `subject.ts`'s types until feature 013's codex entry page became its first caller. That gap was intentional — the buffer's shape had to be frozen before an editable subject existed, so the first subject would adopt it rather than negotiate it.

## The module tier — three members

`src/work/` now holds **three** module-level modules beside each other, all plain functions, none of them reactive stores, all of them outliving every page-state instance:

| Module | Holds | Persisted? |
|---|---|---|
| `restoreBuffer.ts` | unsaved draft text per item, with its base version | `localStorage` |
| `activeChat.ts` | which chat is open, per book | `localStorage` |
| `contentSubject.ts` | the current content-pane subject + its apply-draft callback | in memory only |

Each needed the same explicit sanction, because each is an exception to "state lives in a `<Page>State`". They are recorded together so a fourth is added on purpose rather than by precedent.

### The active-chat pointer (feature 011)

The chat pane needs to know which chat to reopen for a book after a remount or a reload. That pointer is **one id per book**, device-local, stored in `src/work/activeChat.ts` beside the buffer — **not in the URL** (a chat is private, so it must not travel in a shared link) and **not on the server** (it is view focus, not book content). Losing it is harmless: the pane falls back to the **most recent chat by timestamp**, which is what a returning author almost always wants anyway. The conversation itself is never at risk — it is server-persisted (`domain-chat.md`).

Realized exactly as designed. Reads never throw (absent, non-JSON, non-string and empty all resolve to `null`); writes and clears are best-effort and swallow storage errors. The sanction is easier to keep attached to a named file than to a concept, which is why the module is named here.

### The canvas target registry (feature 013)

`src/work/contentSubject.ts` holds the currently open content-pane subject (a `LoadedSubject`, per `frontend-workspace.md` → "Content pane — subject and editability") and, when that subject is editable, its **apply-draft callback**. The open page registers both in its existing page-level mount `useEffect` and unregisters them in the same cleanup; registration overwrites outright (newest wins) and unregistration clears **only** when the caller is still the registered owner, so a late unmount from a superseded page is a no-op.

It exists to avoid three things `frontend.md` bans outright:

- **React context** — the obvious way to let the chat pane reach the content pane, and forbidden.
- **A cross-page callback** — the chat pane and the content page are siblings under the shell with no shared parent state, and wiring one up would make the shell the owner of a thing neither of them owns.
- **A custom `useX` hook** — the other obvious way to share it.

A module of plain functions is what is left, and it is the tier this document already sanctions. Two consequences worth naming:

- **`ChatPaneState` gained no subject field.** It reads the registry **at send time**, so the turn always carries whatever is open at the moment the author sends, and no observer relationship exists between the two panes. The panes stay independent (UC-083) because nothing links them but a function call.
- **Fallback: a `canvas` frame with no registered target is written into the restore buffer**, so returning to the entry surfaces it through the path that already exists rather than through a second, parallel one. A frame naming no entry at all (`subject_id === null`, UC-076's blank entry) with no registered target is simply dropped — there is no key to write it under.

## Returning to a stale buffer

When a buffer's recorded base version does not match the server's current version, it is a **visible merge problem — never an auto-merge** (`domain-chapter.md` → "Concurrency", `domain-codex.md` → "Concurrency"):

1. The pane shows the server's current text **against** the buffered draft.
2. The author reconciles manually, taking one side whole. **The manual path is not optional** — but it does not ship with the buffer: the buffer landed at feature 010 as a pure module, and the **divergence view ships with the first editable subject** (`013.codex`, and later `015.chapter-writing-free-mode`). This is a user-confirmed scope decision, recorded rather than left as a silent divergence from the buffer's original wording.
3. An LLM-assisted merge is offered as a **Stage-5** capability, once the assistant subsystem exists.

### Two entrances, not one

The view is reached from **two** directions, and only naming both makes "the author never overwrites silently" true:

1. **A 409 on save.** A save carrying a stale base version is refused by the server; the client's job is to turn that refusal into the reconciliation view rather than a raw error. This is also what US-041's "warn the second author" looks like in the UI — the warning *is* the divergence view.
2. **A base-version mismatch detected at load**, before any save is attempted at all. The page loads the entry, reads the buffer at its key, and compares. A match restores the buffered draft; a mismatch opens the divergence view directly.

The **load-time entrance is the load-bearing one**. Entrance 1 protects the author who tries to save; entrance 2 protects the author who simply comes back to the page, which is the far commoner case and the one a save-centred design misses.

### A writer with no base version

The buffer has a **second writer** — the canvas dispatcher — and it is structurally unable to record a base version. Every buffer written by the author's own keystrokes carries the `modified_at` the page loaded. A `canvas` frame arriving with no registered target is written by a module that **never loaded the entry**, so it can only inherit the base version already sitting at that key, and `""` when there is none.

Since a codex row always has a non-null `modified_at`, an assistant draft buffered for an entry the author was **not** editing **reads as stale on return by construction**, and opens the divergence view instead of restoring silently. This is deliberate — the author is shown the assistant's draft against the server's text and chooses — but it has a consequence worth stating plainly:

> **The divergence view is the normal landing for the navigated-away-mid-turn path, not an edge case.**

Anything that treats the divergence view as a rare error condition (a scary color, a modal, a log line) is mis-sized for how often it will be seen.

## The codex realization (feature 013)

The first item type to use the buffer pins the generic design's concrete answers:

- **`baseVersion` is the entry's `modified_at` ISO string.** The buffer's `BufferBaseVersion` is `number | string` precisely so a chapter's numeric `version` and a codex entry's timestamp can share one shape.
- **`BufferedDraft.draft` holds the body only** — the principal-text-field rule above.
- **Both entrances are implemented**: a 409 from Save re-fetches into the conflict slot and raises the reconciliation flag; a load-time base-version mismatch does the same with no save attempted.
- **Reconciliation takes one side whole.** Keeping the server version clears the buffer and reseeds from the server's entry; keeping the draft adopts the server's entry **first** — so `baseVersion` becomes the server's new `modified_at` — leaves the view, and re-saves. There is no third, merged outcome.
- **`saved-after-eviction` is surfaced** to the author, listing the evicted keys.

## Sanctioned exclusions

The buffer's exclusions need sanctioning the same way its inclusions do, or the next author of a text field has to guess.

**The per-author system prompt is deliberately outside the buffer (feature 021).** It is editable on the working page's Book-state view and on the Shell's book-settings page, and neither buffers it. The reasoning: the buffer exists for **large content-pane artifacts whose loss is expensive**, while this is a **short settings field edited from two surfaces**, and buffering it on one surface but not the other would be incoherent — the author would get restore behaviour that depended on which page they happened to use.

Its consequences follow from the exclusion and are all intended: **no `baseVersion`, no stale-buffer detection, no divergence view, and no 409 path.** The row has exactly one writer — its owner, who is also the only reader — so there is no second author to diverge from.

## Out of scope

- **Chapter bodies.** The buffer's design covers them (`BufferBaseVersion` carries the numeric `Chapter.version` for exactly this reason) but no chapter surface exists yet; `015.chapter-writing-free-mode` is the first, and it adopts this tier rather than extending it.
- **A merge algorithm.** Reconciliation takes one side whole, by design. LLM-assisted merge is a Stage-5 capability.
- **Cross-device drafts.** The buffer is device-local by requirement, not by limitation; nothing here is a step toward syncing it.
