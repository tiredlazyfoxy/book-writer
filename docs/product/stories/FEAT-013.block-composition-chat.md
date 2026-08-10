<!-- product-spec:start -->
# Stories — FEAT-013 AI authoring assistant

(File retains its original slug, `block-composition-chat`, per the
merge-fence filename-stability rule — the feature was renamed, not
renumbered.)

### US-056 — Author starts chats freely; chats persist until archived
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:**
  UC-053, UC-057
- **Status:** delivered
- **Story:** As an author, I want to start a composition chat freely and
  leave it without losing it, so that I can pick it up again later instead
  of being forced to finish or bind it to one edit or chapter.
- **Acceptance criteria:**
  - **US-056.AC-1** — Given the author is a member of the book, when they
    start a new chat, then a chat is created, private to them, independent
    of any chapter, codex entry or content-pane subject.
  - **US-056.AC-2** — Given an open chat, when the author leaves it, then
    the chat persists — it is not destroyed — and remains available to
    resume (US-095).
  - **US-056.AC-3** — Given no chapter is open in the book, when the
    author starts a chat, then the chat still starts, with a reduced
    baseline.
  - **US-056.AC-4** — Given no model is available to the author, when they
    start a new chat, then starting it is refused with a message saying so.
  - **US-056.AC-5** — Given no model is available to the author, when they
    start a new chat, then no chat is created — their chats list gains no
    entry.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "block composition chat": "The author starts and ends chats freely — not
  bound to a block or a chapter."; interview 2026-07-23, "Augment round 5",
  "the working page — two-pane, chat + content": "chats are persistent,
  not ephemeral." AC-4 and AC-5: `[confirmed:
  docs/plans/023.chat-ux-revision/]` DoD-9 (delivered 2026-08-08, verifier
  PASS) — delivery evidence, not an interview answer; see interview
  2026-08-10, "addendum — review round 1 findings".

### US-057 — The mode-dependent baseline is available to a composition chat
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-054
- **Status:** proposed
- **Story:** As an author, I want my chat's pushed context to match
  whether I'm working on a chapter or a codex entry, so that generated
  content stays consistent without the full book being present.
- **Acceptance criteria:**
  - **US-057.AC-1** — Given the content pane holds a chapter, when the
    author sends a prompt, then the focused chapter's text and the current
    selection (if any) are available to the chat.
  - **US-057.AC-2** — Given the content pane holds a chapter, when the
    author sends a prompt, then summaries of all prior chapters are
    available to the chat.
  - **US-057.AC-3** — Given the content pane holds a chapter, when the
    author sends a prompt, then the current state notes are available to
    the chat.
  - **US-057.AC-4** — Given the content pane holds a chapter, when the
    author sends a prompt, then the sketches of all upcoming chapters are
    available to the chat.
  - **US-057.AC-5** — Given the content pane holds a codex entry, when the
    author sends a prompt, then only the entry and the current selection
    (if any) are available to the chat — no summaries, state notes or
    sketches are pushed.
  - **US-057.AC-6** — Given either mode, when the author asks about
    material outside the pushed baseline, then it is fetched on request,
    not pushed automatically.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "generation context": "All four — summaries of all prior chapters,
  current state notes, full text of the open chapter, sketches of upcoming
  chapters."; challenge C11. **Sharpened, round 5:** interview 2026-07-23,
  "context model — hybrid push/pull", "context model — RESOLVED": "Split
  by size... Chapter mode: the compact continuity distillate always fits,
  so it is always present... Codex-entry mode: only the entry itself (+
  selection) is pushed."

### US-058 — Author iterates with the LLM to refine the next edit
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-054
- **Status:** delivered
- **Story:** As an author, I want to send free-form prompts and get
  responses inside the chat, so that I can create, recreate and polish the
  next edit before producing it.
- **Acceptance criteria:**
  - **US-058.AC-1** — Given an active composition chat, when the author
    sends a free-form prompt, then the LLM's response appears in the chat.
  - **US-058.AC-2** — Given a response in the chat, when the author sends
    another prompt, then the chat continues with the prior exchange
    retained.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "block composition chat": "author chats and is
  creating/recreating/polishing the next block."

### US-059 — The assistant's shared-canvas write follows the book's collaboration mode at save
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-055
- **Status:** delivered
- **Story:** As an author, I want what the assistant writes into the open
  chapter to enter it the same way a manually written edit would, so
  that collaboration rules stay consistent regardless of who wrote it.
- **Acceptance criteria:**
  - **US-059.AC-1** — Given the book is in free mode, when the author
    saves the assistant's draft written into the open chapter, then the
    edit is added to the chapter directly.
  - **US-059.AC-2** — Given the book is in proposal mode, when a co-author
    saves the assistant's draft written into the open chapter, then the
    edit is held as a proposal until the owner applies it.
  - **US-059.AC-3** — Given the content-pane subject is a read-only
    (closed) chapter, when the author asks the assistant to write into it,
    then the write is refused.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "block composition chat": "In proposal mode... a co-author's generated
  block become? A proposal."; interview 2026-07-23, "Augment round 5",
  "the working page — two-pane, chat + content": "Draft until saved... only
  then do collaboration-mode rules apply." **Delivered** (the tool-level
  refusal mirror of the book's collaboration mode):
  `docs/plans/015.chapter-writing-free-mode/` (2026-07-30).

### US-060 — A failed composition shows an error, offers retry, preserves the conversation
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-056
- **Status:** delivered
- **Story:** As an author, I want a clear error and a retry option when the
  LLM fails, so that I don't lose my conversation or retype it.
- **Acceptance criteria:**
  - **US-060.AC-1** — Given the author sends a prompt or requests edit
    production, when the LLM is unreachable or returns nothing, then an
    error is shown with a retry action.
  - **US-060.AC-2** — Given a failed request, when the error is shown, then
    the conversation up to that point is preserved.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "block composition chat": "Error shown, retry offered, conversation
  preserved so nothing is retyped."

### US-061 — A composition chat is visible only to its author, even once persisted
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:**
  UC-057, UC-081, UC-082
- **Status:** delivered
- **Story:** As an author, I want my composition chats kept private, so
  that only my saved output is shared with others.
- **Acceptance criteria:**
  - **US-061.AC-1** — Given a composition chat belonging to one author,
    when another member of the book, including the owner, views the book,
    then that chat — active or archived — is not visible to them.
  - **US-061.AC-2** — Given saved output produced with the assistant's
    help (an edit or codex entry), when it is added or proposed, then only
    that saved output is shared, not the chat that produced it.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "block composition chat": "Private to their author... Only the produced
  block is shared."; interview 2026-07-23, "Augment round 5", "the working
  page — two-pane, chat + content": "Chats stay private to their author and
  per book."

### US-089 — A composition chat can draw on the book's codex
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-078
- **Status:** delivered
- **Story:** As an author, I want my composition chat to draw on the book's
  codex, so that generated content stays consistent with established lore.
- **Acceptance criteria:**
  - **US-089.AC-1** — Given a book with codex entries, when the author sends
    a prompt in a composition chat, then the book's codex is available to
    the chat.
  - `_TBD: which entries count as "relevant" enough to reach the chat — no
    measurable criterion offered; see challenge C27._`
- **Source:** `[confirmed: user]` `docs/.cache/product/interview.md`,
  "## challenges (2026-07-20, round 4)", challenge C26.

### US-095 — Chats persist and are managed (list, pick, continue)
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-081
- **Status:** delivered
- **Story:** As an author, I want my stored chats listed so I can pick one
  and continue it, so that I don't lose earlier work when I step away.
- **Acceptance criteria:**
  - **US-095.AC-1** — Given the author has stored chats for the book, when
    they open the book's chats list, then their non-archived chats are
    shown, most recently active first.
  - **US-095.AC-2** — Given a listed chat, when the author picks it, then
    it reopens with its full prior history.
  - **US-095.AC-3** — Given the author is viewing their chats list, when
    they ask to see archived chats, then their archived chats are shown
    (restoring one is US-096).
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 5",
  "the working page — two-pane, chat + content": "Like Claude's chat
  manager — chats are stored, continuable... picker lives inside the chat
  pane." **Amended, finalization 2026-08-10:** the list is reached from
  the book's material rather than from inside the chat pane; the picked
  chat still opens in the chat pane (AC-2, unchanged). `[confirmed: user]`
  interview 2026-08-10, "finalization — plans 023 + 024"; challenge
  C-f2324-1. Delivered: `docs/plans/023.chat-ux-revision/` (2026-08-08).

### US-096 — Archive a chat instead of ending it
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-082
- **Status:** delivered
- **Story:** As an author, I want to archive a chat I'm done with instead
  of losing it, so that I can still find it later if I need it.
- **Acceptance criteria:**
  - **US-096.AC-1** — Given a stored chat, when the author archives it,
    then it leaves the active chat list.
  - **US-096.AC-2** — Given an archived chat, when the author chooses to
    restore it, then it becomes available again — it was not destroyed.
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 5",
  "the working page — two-pane, chat + content": "FEAT-013 'end a chat'
  becomes archive a chat (reversible)."

### US-097 — The content pane shows any chapter, read-only unless it is the open one
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-083
- **Status:** delivered
- **Story:** As an author, I want to load any chapter into the content
  pane to discuss it with the assistant, so that I can reference other
  chapters without disrupting what I'm writing.
- **Acceptance criteria:**
  - **US-097.AC-1** — Given a chapter that is not the book's open chapter,
    when the author loads it into the content pane, then it loads
    read-only.
  - **US-097.AC-2** — Given a read-only chapter loaded in the content
    pane, when the author or the assistant attempts to write into it, then
    the write is refused.
  - **US-097.AC-3** — Given the book's open chapter, when the author loads
    it into the content pane, then it loads editable.
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 5",
  "the working page — two-pane, chat + content": "Which chapters can
  occupy the content pane? Any chapter — read-only unless it is the open
  one." Delivered: `docs/plans/015.chapter-writing-free-mode/`
  (2026-07-30).

### US-098 — The author hands the assistant a text selection as focused source
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-084
- **Status:** delivered
- **Story:** As an author, I want to give the assistant just a selected
  passage instead of the whole artifact, so that its response is focused
  on what I actually mean.
- **Acceptance criteria:**
  - **US-098.AC-1** — Given text selected in the content pane, when the
    author sends a prompt, then the assistant's response is grounded in
    the selection rather than the full artifact.
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 5",
  "the working page — two-pane, chat + content": "a selection — a narrowed
  source, NEW requirement." Delivered:
  `docs/plans/015.chapter-writing-free-mode/` (2026-07-30).

### US-099 — The assistant reads another chapter on request
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-085
- **Status:** proposed
- **Story:** As an author, I want to ask the assistant to read a specific
  chapter, so that it can reference it without me copying text in.
- **Acceptance criteria:**
  - **US-099.AC-1** — Given the author names another chapter, when they
    ask the assistant to read it, then that chapter's full text reaches
    the assistant for that exchange.
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 5",
  "context model — hybrid push/pull": "read chapter 8."

### US-100 — The assistant searches the book's material by meaning
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-086
- **Status:** proposed
- **Story:** As an author, I want the assistant to find relevant material
  in my book by meaning, so that I don't have to hand-pick the right
  chapter or note myself.
- **Acceptance criteria:**
  - **US-100.AC-1** — Given the author asks a question not tied to a named
    chapter, when the assistant searches, then material relevant to the
    question reaches it without the author naming a source.
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 5",
  "context model — hybrid push/pull": "the book's own material by
  meaning-search."

### US-101 — The assistant may consult the web
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-087
- **Status:** delivered
- **Story:** As an author, I want the assistant to look things up on the
  web when my question needs outside information, so that I'm not limited
  to what's in my book.
- **Acceptance criteria:**
  - **US-101.AC-1** — Given a question that needs information outside the
    book, when the author asks the assistant to check the web, then web
    results reach the chat.
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 5",
  "context model — hybrid push/pull": "Web search — IN (new scope)."

### US-102 — The assistant runs a scoped consistency check in chat and returns a focused result
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-088
- **Status:** proposed
- **Story:** As an author, I want to ask a targeted consistency question in
  chat and get a concise answer, so that I don't have to read the raw
  chapters myself to check.
- **Acceptance criteria:**
  - **US-102.AC-1** — Given a targeted consistency question (e.g., "does
    this contradict chapter 8?"), when the author asks it, then the
    assistant returns a focused finding.
  - **US-102.AC-2** — Given the same question, when the assistant answers,
    then the raw chapters or notes it consulted are not dumped into the
    conversation.
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 5",
  "context model — hybrid push/pull": "scoped, on-demand checks... return a
  focused result without dumping the raw chapters."

### US-103 — The assistant writes into the open artifact; nothing persists until saved
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:**
  UC-055, UC-076, UC-077
- **Status:** delivered
- **Story:** As an author, I want the assistant's writes to land as an
  editable draft I control, so that nothing is added to my book or codex
  without my say-so.
- **Acceptance criteria:**
  - **US-103.AC-1** — Given the assistant writes into the open
    content-pane subject, when it finishes, then the result appears as an
    editable draft, not committed content.
  - **US-103.AC-2** — Given a draft on the shared canvas, when the author
    saves, then it persists per the book's collaboration mode (free →
    applied directly; proposal → held as a proposal).
  - **US-103.AC-3** — Given a draft on the shared canvas, when the author
    does not save, then nothing changes in the chapter or codex.
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 5",
  "the working page — two-pane, chat + content": "Draft until saved... an
  explicit save persists it, and only then do collaboration-mode rules
  apply." Delivered: `docs/plans/015.chapter-writing-free-mode/`
  (2026-07-30).

### US-105 — Author browses the book's material by kind from the working page
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-090
- **Status:** partially delivered
- **Story:** As an author, I want to browse the book's material by kind
  from the working page's navigator, so that I can find and open what I
  need without leaving the page.
- **Acceptance criteria:**
  - **US-105.AC-1** — Given the navigator, when the author picks a kind
    (e.g., Characters), then that list renders in the content pane.
  - **US-105.AC-2** — Given a rendered list, when the author picks a list
    item, then it opens in the content pane.
  - **US-105.AC-3** — Given the navigator, when the author picks
    **Chats**, then their chats list renders in the content pane, the same
    as every other kind.
  - **US-105.AC-4** — Given the navigator, when the author picks
    **Variants**, then the chapter's variants and revisions render in the
    content pane.
  - **US-105.AC-5** — Given a rendered chats list, when the author picks a
    chat from it, then that chat opens in the chat pane, not the content
    pane.
  - **US-105.AC-6** — Given a rendered chats list, when the author picks a
    chat from it, then the list stays where it is — the author is not
    taken away from it.
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 6",
  "the working-page navigator". AC-4: `[confirmed: user]` interview
  2026-07-24, "augment round 7", divergence 2. AC-3 amended and AC-5/AC-6
  added: `[confirmed: user]` interview 2026-08-10, "finalization — plans
  023 + 024"; challenge C-f2324-1.

### US-107 — Unsaved content-pane edits are retained and restored
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-092
- **Status:** delivered
- **Story:** As an author, I want my unsaved edits to an item restored when
  I come back to it, so that I don't lose work by navigating away or
  reloading.
- **Acceptance criteria:**
  - **US-107.AC-1** — Given unsaved edits on an item, when the author
    navigates away and returns, then the edits are restored.
  - **US-107.AC-2** — Given unsaved edits on an item, when the author
    reloads the page and returns to the item, then the edits are still
    restored.
  - **US-107.AC-3** — Given an author's unsaved buffer on an item, when a
    co-author views the same item, then they do not see the buffer.
  - **US-107.AC-4** — Given an unsaved buffer on an item, when the author
    has not explicitly saved, then the item remains unpersisted.
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 6",
  "the restore buffer — unsaved per-item edits". Delivered:
  `docs/plans/015.chapter-writing-free-mode/` (2026-07-30).

### US-117 — Author undoes the assistant's last write to the open artifact
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-055
- **Status:** delivered
- **Story:** As a book member, I want to undo the assistant's last write
  to the open artifact, so that I can reject a suggestion without losing
  what I had written.
- **Acceptance criteria:**
  - **US-117.AC-1** — Given the assistant has written into the open
    artifact, when the author undoes it, then the artifact returns to
    the text it held immediately before that write.
  - **US-117.AC-2** — Given the assistant has written several times, when
    the author undoes repeatedly, then the writes are reversed
    most-recent-first.
  - **US-117.AC-3** — Given the author has typed their own changes, when
    they undo the assistant's write, then only assistant-originated
    writes are reversed; the author's own typing is undone by the editor
    itself.
  - **US-117.AC-4** — Given no assistant write has occurred, when the
    author looks for the undo, then it is unavailable.
- **Note:** The undo history is **session-lived and device-local** — it
  does not survive a reload, and it is not shared between members.
- **Source:** `[confirmed: user]` interview 2026-07-30, "finalization —
  021 + 014 + 015", "challenges (2026-07-30)", challenge C1 — shipped
  without a story (20 snapshots per (book, chapter), in memory,
  assistant writes only). Delivered:
  `docs/plans/015.chapter-writing-free-mode/` (2026-07-30).

### US-119 — Author's chats carry meaningful titles without naming them
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-101
- **Status:** delivered
- **Story:** As an author, I want my chats to be labelled by what they are
  about, so that I can find the right one in my list without having named
  each one myself.
- **Acceptance criteria:**
  - **US-119.AC-1** — Given a chat that the author has not named, when
    they send their first message in it, then the chat's title becomes a
    short label drawn from that conversation.
  - **US-119.AC-2** — Given a chat titled this way, when the author sends
    their fifth message in it, then the title is drawn again from the
    conversation as it now stands.
  - **US-119.AC-3** — Given a chat, when the author sends a message that is
    neither their first nor their fifth in it, then the chat's title is
    left unchanged.
  - **US-119.AC-4** — Given titling fails or produces nothing, when the
    author sends a message, then the chat keeps the title it already had.
  - **US-119.AC-5** — Given titling fails or produces nothing, when the
    author sends a message, then no error about the title is shown to the
    author.
  - **US-119.AC-6** — Given titling fails or produces nothing, when the
    author sends a message, then the message is sent normally.
- **Source:** `[confirmed: user]` interview 2026-08-10, "finalization —
  plans 023 + 024". Delivered: `docs/plans/023.chat-ux-revision/`
  (2026-08-08).

### US-120 — Author sees which tools the assistant used and what they returned
- **Feature:** FEAT-013 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-102
- **Status:** delivered
- **Story:** As an author, I want to see what the assistant looked up or
  changed while answering me, so that I can judge its answer instead of
  taking it on trust.
- **Acceptance criteria:**
  - **US-120.AC-1** — Given the assistant takes an action while answering,
    when it starts that action, then the action appears in the
    conversation, named, before its outcome is known.
  - **US-120.AC-2** — Given an action shown in the conversation, when it
    returns, then its outcome is shown against it, marked as having
    succeeded or failed.
  - **US-120.AC-3** — Given the assistant takes several actions in one
    answer, when they are shown, then they appear in the order they were
    taken.
  - **US-120.AC-4** — Given an action shown in the conversation, when the
    author expands it, then what was asked for and what came back are
    shown.
  - **US-120.AC-5** — Given the author returns to the chat later, when
    they read that answer again, then the actions taken for it are still
    shown with it.
  - **US-120.AC-6** — Given an action shown in the conversation, when the
    author has not expanded it, then its detail is collapsed.
- **Source:** `[confirmed: user]` interview 2026-08-10, "finalization —
  plans 023 + 024". Delivered: `docs/plans/024.chat-agent-loop/`
  (2026-08-09).
<!-- product-spec:end -->
