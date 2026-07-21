# BookWriter — The Idea

*A place where people and a language model write long books together, without losing the plot.*

---

## 1. In one paragraph

BookWriter is a private, self-hosted workshop for writing long-form fiction with the help of a
large language model. A book lives on the platform as a single shared object: an ordered set of
chapters, a growing reference volume of the characters, places and lore it is about, and a
continuously maintained record of what is currently true in its world. Authors write it a piece
at a time, in conversation with the model, and the platform's job is to make sure that every new
piece is written with the whole book in mind — even when the book has grown far past anything a
model could read in one sitting. Around this sits a small, deliberate set of rules about who may
write what, when, and with whose approval, so that two or five people can work on the same book
without stepping on each other or on the story.

---

## 2. The problem it exists to solve

Anyone who has tried to write a novel with an AI assistant has met the same wall, usually around
chapter four.

The first chapters go beautifully. The model has read everything you have written so far, it
remembers the protagonist's name, her injury, the argument in the tavern, the promise she made.
Then the book gets long. The model can no longer hold it all. And the moment it stops holding it
all, it starts inventing: the injured arm heals without a scene, a dead character walks in, the
city that was three days' ride away is suddenly next door. The author becomes an unpaid continuity
editor, re-pasting summaries into a chat window, keeping a private text file of "things the AI
keeps forgetting," and losing the thread of the actual writing.

The second wall arrives when more than one person is involved. Co-authoring long fiction is
genuinely hard even without a model in the room. Two people writing into the same document
overwrite each other. Sending chapters back and forth by email means nobody knows which version is
the real one. Adding an AI to that mess multiplies it — now there are three sources of text and no
agreed authority over any of them.

The third wall is the fear of changing your mind. Halfway through chapter nine you realise chapter
three was wrong. Fixing it feels dangerous: what else did it break? Trying an entirely different
direction for the story feels worse — the only honest way to explore an alternative is to copy the
whole thing somewhere else and hope you can keep the two straight.

Generic chat tools do not solve any of this, because a chat has no idea it is inside a book. It
has no notion of a chapter, of who owns the story, of what was decided three hundred pages ago, or
of what happens to the rest of the manuscript when you change your mind about the middle. A word
processor solves the opposite half: it knows about documents and nothing about narrative memory or
generation.

BookWriter's claim is that these are one problem, not three. All of them come from the same
missing thing: **a system that understands the book as a structured, shared, remembered object,
and treats the model as a collaborator inside that structure rather than a chat window next to
it.**

An honest note about the evidence behind this, recorded rather than dressed up: this is a
greenfield product built the way its author believes the work should be done. It is not a
migration away from a painful existing workflow. That is a real limitation of the case for it, and
it is written down here on purpose rather than replaced with an invented origin story.

---

## 3. The core idea

A book on BookWriter is not a file. It is a living object with four faces, and the whole product
falls out of keeping those four faces in agreement with each other.

**The skeleton.** Before a book is written, it is planned. Authors lay out chapters in order and
give each one a *sketch* — a short statement of the idea, what happens, what it is for. The
skeleton is the map. It exists from the very first day of a project and it keeps changing as the
book grows. Crucially, the skeleton is where collaboration is cheap: everyone can work on it at
once, safely, because nothing in it is finished prose.

**The prose.** Chapters are written one at a time, and each is written in *blocks* — modest,
digestible pieces rather than one heroic act of composition. A block is the unit of writing, the
unit of collaboration, and the unit of AI generation. Writing in blocks is what makes an
AI-assisted chapter feel like writing rather than like prompting: you shape a piece, you accept
it, you move to the next.

**The memory.** When a chapter is finished, the platform reads it and drafts two things: a
*summary* of what happened, and a set of *state notes* — the facts that must remain true from now
on. The arm is broken. The alliance is signed. The harbour burned. Summaries are backward-looking
narrative; state notes are forward-binding truth. Together they are how a book two hundred pages
long can still inform the writing of page two hundred and one without anyone re-reading it — a
human or a machine.

**The codex.** Alongside the story sits the book's reference volume: entries for characters,
locations, and lore facts. If state notes are what *changed*, the codex is what *is*. Elen is the
exiled cartographer with the burned hands — that belongs in the codex, and it stays true across
the whole book. Her hands being burned *in chapter six* is a state note. Keeping identity and
change apart is one of the deliberate design decisions of the product, because collapsing them is
exactly what makes AI-assisted worldbuilding turn to mush.

Everything else in BookWriter — the collaboration rules, the moderation surface, the variants, the
consistency checking — exists to keep these four faces honest with each other as the book, and the
number of people writing it, grows.

---

## 4. Who it is for

**The solo novelist working with AI as a serious tool.** Not someone generating a book by pressing
a button, but someone who wants a model in the loop the way a writer might want a very
well-briefed assistant: one that has actually read the manuscript, knows the cast, and never
contradicts chapter four. This author is the centre of gravity of the product.

**Small co-writing teams.** Two, three, five people writing one book together — a lead author with
collaborators, a writing partnership, a shared-world project. They need a single authoritative copy
of the manuscript, clear rules about who may change what, and a way for contributions to be
reviewed rather than merely applied.

**The lead author of a shared project.** Someone who owns the story's direction and invites others
into it. This person needs real control — over sequence, over what gets written when, and over
what other people's contributions do to the book — without that control becoming a bottleneck that
makes collaborators useless.

**Readers inside a trusted circle.** People who are given sight of a book without being given a
pen. Not the public internet — a logged-in, known audience.

**The person who runs the instance.** BookWriter is a system somebody hosts, for themselves or for
a group. That person needs to stand it up, manage accounts, connect it to whichever model service
they have chosen, keep the data healthy, and remove content that shouldn't be there.

An important distinction that runs through the entire product: *owner* and *co-author* describe a
relationship to one particular book, not a rank. The same person is the owner of their own novel
and a co-author on someone else's, at the same time, with different powers in each. Authority is
always local to a book.

---

## 5. How it actually works

### Starting a book

An author creates a book and becomes its owner. Ownership means responsibility for the shape of
the story: sequence, who is allowed in, how contributions arrive, and when a chapter is done.

Two decisions are made early, and both can be changed later. **Visibility**: a book is either
private — only the owner and invited co-authors can see it — or public, meaning any logged-in user
on the instance can read it, but only read it. There is deliberately no anonymous, public-internet
surface; this is a workshop, not a publishing platform. **Collaboration mode**: free or proposal.
More on that below.

### Planning before writing

The owner and co-authors build the chapter skeleton. Anyone who is a member can add a chapter and
write or rewrite the sketch of any chapter that has not been written yet. Only the owner sets the
order — sequence is a story decision, and the story has one lead.

This is where the product's collaboration model gets interesting, because of the next rule.

### One open chapter

A book has exactly one chapter open for writing at any time. Everything else is either planned and
unwritten, or closed and finished.

This looks, at first glance, like an anti-collaboration rule — how do five people work on a book
with one writable chapter? It is deliberate, and it comes from a conviction about how long fiction
is actually written: **front to back, one thread at a time.** A novel is not a codebase; chapter
seven genuinely depends on chapter six in a way that cannot be parallelised without producing
incoherence. The single open chapter *is* the coordination mechanism. It means everyone always
knows where the book currently is.

And it is precisely why sketches exist. Collaborators who are not writing the current chapter are
not idle — they are ahead of it, building the skeleton, sharpening the plan for chapters eight
through fifteen, deciding what the book is going to do. Parallel work happens on the *plan*.
Serial work happens on the *prose*. That split is the heart of the collaboration design.

### Writing a chapter in blocks

The owner opens a chapter and writing begins. Blocks are added one at a time. Two people adding
different blocks both succeed — the chapter simply grows. Two people editing the *same* block is
the only genuine collision, and the second one is warned before their version stands.

Blocks can be written by hand. Mostly, they are written in conversation.

### Composing with the model

An author opens a composition chat. This is a free-form conversation whose purpose is to produce
the next block: draft it, dislike it, redirect, sharpen, try a different angle, and eventually say
*that one* — at which point the block enters the chapter.

What makes this different from any general-purpose chat is what the conversation is guaranteed to
know. Every composition chat has access to:

- the summaries of every prior chapter,
- the current state notes — everything that must still be true,
- the full text of the chapter currently being written,
- the sketches of the chapters still to come,
- and the book's codex.

That last item about upcoming sketches is worth pausing on. The model is not only told where the
book has been; it is told where the book is going. A block written with the next three chapters'
intentions in view can *aim* — it can plant something, hold something back, set up a scene that
pays off later. That is the difference between an assistant that continues text and one that
writes a chapter of a novel.

Composition chats are private to the author who opened them. The messy middle of your creative
process — the false starts, the arguments with the model, the four rejected versions — belongs to
you. Only the finished block is shared, even with the book's owner. Authors start and end chats
freely; they are working sessions, not permanent records.

### Closing a chapter, and what closing means

When a chapter is done, the platform reads it and drafts its summary and its state-note changes:
what facts this chapter added, what it modified, what it made no longer true. The owner reviews
that draft, corrects it, and approves it.

**A chapter cannot close until its continuity has been approved.** This is one of the strongest
rules in the product, and it is a value judgement expressed as a constraint: closing a chapter
*means* the book's memory is up to date. The one moment where an author is guaranteed to have the
chapter fresh in mind is the moment they finish it — so that is where the work of remembering it
is placed. Skip it, and the memory rots silently, which is the exact failure the entire product
exists to prevent.

Note who does this work: the machine drafts, the human approves. Continuity is too important to be
fully automated and too tedious to be fully manual. The platform proposes; the author decides.

### Changing your mind

The owner can reopen a closed chapter. Editing it does not overwrite it — it produces a **variant**.
Every version of a chapter is kept and remains readable. The owner chooses which variant *is* the
chapter for every purpose: reading, export, and the context the model sees. Switching between them
is a normal, reversible act.

This is how the product removes the fear of correction. Nothing you wrote is destroyed by fixing
it.

But changing an early chapter still has consequences downstream, and the platform does not pretend
otherwise. When a fixed chapter closes — and at any time on demand — a **consistency check** reads
the book's chapters, summaries, state notes and codex, and looks for contradictions. What it finds
becomes a **flag**: a note attached to a chapter, with a comment.

The critical design decision here: **the check never rewrites anything.** It reports. It flags. It
warns. Every remedy is an author's decision. Automatic repair of a novel by a language model is a
categorically worse outcome than an honest list of things that look wrong — because the author is
the only one who knows which contradiction is a mistake and which is a mystery being set up on
purpose.

Flags are not only for the machine. Any member can raise one with a comment — *this scene
contradicts the prologue*, *her voice is wrong here*. Every flag records where it came from, a
check or a person, because those two carry very different weight.

### Exploring a completely different story

Fixing is for correcting *this* book. When an author wants to explore a genuinely different
direction — what if she never left the city — they **clone** the book instead.

A clone is a full, independent copy: chapters, blocks, sketches, summaries and state notes, the
codex, the collaboration mode and visibility, and whichever members the cloner chooses to bring
along. And then it is completely on its own. No link to its source, no syncing, no merging, no
comparison view.

That independence is a choice with a real cost, accepted openly: two clones drift apart forever,
and a fix that both need must be made twice. The alternative — a branching version tree with merge
semantics — was designed during this product's development and then deliberately rejected, because
it would have made the interface and the mental model dramatically more complicated for a benefit
most novelists would never use. A book stays a straight line. If you want a different line, you get
a different book.

Co-authors, not only owners, may clone a public book, and doing so makes them the owner of their
own copy. That is a deliberate act of trust: co-authors are collaborators, and forking is how
creative variation actually happens. It is bounded by one rule — only the owner may clone a
*private* book, so that nobody can quietly copy someone's unpublished work and open it up.

### The codex

As a book grows, so does the cast and the world. The codex is where they live: entries for
characters, for locations, and for lore facts.

Characters and locations are treated as special because they have **names**, and a name is
functional here, not decorative — a named entry can be referred to by state notes and addressed by
name in the writing. Lore facts have no name and neither ability; they are things that are simply
true about the world.

Entries can be written by hand, browsed, searched, and — most usefully — created and rewritten from
inside the same composition chat where the prose is being written. Mid-scene you can ask for the
innkeeper you just invented to be written up as a character, or for the description of the harbour
city to be revised to match what just happened to it. Nothing is saved silently: the entry is shown
in the chat first and stored only when you ask for it.

Entries keep their edit history, and any member can look back through it and restore an earlier
version. Entries are archived rather than deleted, so nothing that the rest of the book refers to
can vanish underneath it.

Codex coverage is explicitly **optional**. Not every character has to have an entry — the product's
own phrasing is "better to be, but not required." The consistency check may point out that a
chapter refers to someone with no entry behind them, but it *warns and never blocks*. The tool is
there to help, not to impose bureaucracy on somebody who is trying to write a novel.

The codex belongs to members only. A reader of a public book sees the story, not the workings
behind it. And a codex can be copied from one book into another, which is what makes sequels and
shared universes practical.

---

## 6. Two ways to collaborate

Every book runs in one of two modes, chosen by the owner and changeable at any time.

**Free mode.** Co-authors write directly. A block is saved and it is in the chapter. This suits
partnerships and small trusted teams where the friction of review would cost more than it saves.

**Proposal mode.** Co-authors submit proposed blocks. Nothing lands until the owner applies it.
Crucially, review here is a **merge, not a verdict** — the owner can take one block from this
person's proposal and two from that one's, assembling the chapter from the best of what arrived.
This suits a lead author with a clear vision and contributors working within it.

Both modes use exactly the same unit of work. The only difference between them is whether a gate
exists between writing a block and it becoming part of the chapter. That symmetry is deliberate: it
means the mode can be switched mid-book without reshaping how anyone works, and it means the entire
proposal apparatus is an addition to the writing model rather than a second, parallel one.

The same rule governs state notes and codex entries. In free mode a member changes them directly;
in proposal mode they propose and the owner applies. One idea about authority, applied
consistently everywhere.

---

## 7. What the model does, and what it does not

The product's position on AI is specific, and it is visible in every feature.

**The model drafts.** It composes blocks in conversation. It proposes chapter summaries and state
notes when a chapter closes. It writes and rewrites codex entries on request. It reads the book
looking for contradictions.

**The human decides.** Continuity data is approved, not accepted. A produced block enters the
chapter only when the author says so, and follows the same collaboration rules as anything written
by hand. A generated codex entry is shown before it is saved. A consistency finding becomes a flag
for someone to consider, never an edit.

**The model never silently changes the book.** There is no path anywhere in the product by which
prose or facts are rewritten without a person choosing it. This is not caution for its own sake; it
is what makes the tool usable for something as personal as a novel. An assistant that quietly
improves your manuscript is not an assistant.

The other half of the AI position is about *context*, and it is the reason the whole structure
exists. The platform's promise is not "the model has read your book" — for a long book that is
impossible and pretending otherwise is how the wall gets hit. The promise is that the model is
always given the things that matter: what happened before, in condensed form; what is currently
true; what is being written right now, in full; where the story is heading; and who and what the
book is about. The structure is not bureaucracy imposed on the author. It is what buys the author a
model that stays coherent at chapter forty.

---

## 8. Control, privacy and trust

**Nothing an author owns is destroyed by the platform.** Books are archived, never deleted. Codex
entries are archived. User accounts are disabled rather than removed, so that everything they
wrote keeps its attribution. Chapter edits produce variants rather than replacements. The principle
is consistent across the whole system: things go away from view; they do not stop existing.

**Attribution survives disagreement.** Remove a co-author from a book and their text stays, still
credited to them. Losing access is not the same as being erased, and a collaboration ending badly
should not corrupt the record of who wrote what.

**Books can change hands.** Ownership can be transferred — an owner stepping back, a project
changing lead. And if an owner's account is disabled, an administrator can reassign their books, so
that a shared project cannot be orphaned by one person's departure.

**Administrators run the platform; they do not join the stories.** An administrator manages the
instance — accounts, model connections, the health of the data. They have no authoring presence in
anyone's book, in any mode, whatever its visibility. There is exactly one way an administrator sees
book content: a separate, read-only moderation view, whose entire purpose is finding material that
must not be on the instance.

**Moderation is two-step and honest about itself.** A book can be *quarantined* — made invisible to
everyone including its members — which is a fast takedown that can be undone if it was a mistake.
Destroying it is a separate, deliberate second act, and it is the single exception to the
never-destroy principle anywhere in the product. Either way the owner is told, with a reason;
nothing disappears silently. Moderation reaches the codex as well as the prose, because illegal
material sits just as comfortably in a character entry as in a chapter.

And one limitation is stated plainly rather than left to be discovered: **moderation does not reach
clones.** Because clones are fully independent books, taking one down does not take down a copy
someone made. Each book is moderated on its own. That is the price of the independence that makes
cloning useful, and it is written into the product's own documentation as a known cost rather than
hidden.

---

## 9. Running an instance

BookWriter is software somebody hosts — for themselves, for a writing group, for a small studio.
That shapes the product in ways worth stating.

The instance is entirely behind a login. There is no anonymous surface at all, and "public" means
public *to the people on this instance*. The audience for a book is always a known set of people.

Whoever runs it sets it up from nothing: bring up a fresh instance with a first administrator, or
restore one from an existing export. From then on the administrator manages accounts, connects the
platform to whichever model service they are using and chooses which models are available, and
keeps an eye on the health and portability of the data — including taking it out of the system in
full, which matters a great deal when the data is somebody's novel.

The model connection being a choice rather than a fixture is a genuine product position: authors
are not locked to one AI vendor, and an instance owner can point BookWriter at a hosted service or
at something running on their own hardware. For people writing unpublished fiction, being able to
keep the whole thing on machines they control is not a technical detail — it is the reason they
would use a self-hosted tool at all.

---

## 10. What makes it different

Stated plainly, against the alternatives people actually use today.

**Against a general AI chat:** BookWriter knows it is inside a book. It knows what a chapter is,
who owns the story, what was true two hundred pages ago, and what the plan for the next three
chapters is. A chat knows the last few thousand words and nothing else, and the author does the
remembering by hand.

**Against a shared document:** BookWriter has an opinion about how collaborative fiction gets
written. Sequence is owned. One chapter is live. Contributions can be reviewed and merged rather
than merely landing. And the document is not the only artifact — the memory and the reference
volume are first-class.

**Against a writing app with an AI feature bolted on:** the memory of the book is the product, not
an add-on. Summaries, state notes and the codex are not conveniences for the author's benefit;
they are the mechanism by which generation stays coherent past the point where naive approaches
collapse.

**Against version-control-style branching:** BookWriter deliberately refuses the version tree. A
book is a straight line with a rich per-chapter history; alternatives are separate books. The
complexity of merges and branch trees was considered and rejected as a bad trade for novelists.

---

## 11. The principles underneath

Every significant decision in this product can be traced to one of a small number of convictions.

**The book is the unit, not the message.** Everything is organised around a durable, structured
work rather than around a conversation.

**Memory is designed, not hoped for.** A long book cannot be held in a context window, so the
product builds a deliberate, human-approved representation of what the book knows and feeds that
forward.

**Identity and change are different things.** Who a character is belongs in the codex; what a
chapter did to them belongs in a state note. Collapsing the two is what makes AI worldbuilding
degrade.

**The machine drafts, the human decides.** Everywhere, without exception.

**Warn, do not block.** The consistency check flags; it does not gate. The codex is encouraged, not
mandatory. The tool serves the writing rather than governing it — with exactly one exception, the
approved-continuity requirement for closing a chapter, which is enforced because it is the single
piece of discipline the whole system depends on.

**Nothing is destroyed.** Archive, disable, variant, clone. Removal from view is not removal from
existence — with the one sanctioned exception of moderating illegal content off the instance.

**Authority is local to a book.** Ownership is a relationship, not a rank. The same person leads
here and contributes there.

**Serial prose, parallel planning.** Collaboration happens on the plan, where it is cheap and safe;
the prose stays a single thread, where coherence lives.

**Say what is not solved.** Several genuine limitations — moderation not reaching clones, two
clones drifting apart permanently, the absence of pain evidence behind the collaboration
features — are written down rather than smoothed over. A limitation that is recorded is a decision;
one that is not is a defect waiting to be found.

---

## 12. What success looks like

Not downloads or seats — this is a tool for a specific job, and it works or it doesn't.

An author writes a book to chapter thirty with model assistance, and chapter thirty is still
consistent with chapter three, without the author having maintained a single continuity spreadsheet
by hand.

An author realises chapter eight was wrong, fixes it, is told what it broke, deals with the list,
and keeps writing — rather than abandoning the correction because they were afraid of it.

Three people write one book together, and the book stays one book: one authoritative text, no lost
contributions, no confusion about what the current version is.

An author wonders what would have happened if the protagonist had stayed, clones the book, and
finds out — without endangering the version they have been working on for six months.

And someone stands up an instance on their own machine, connects it to a model they chose, invites
two friends, and starts writing on the same day.

---

*This document describes the idea. It states what BookWriter is for and how it behaves; it says
nothing about how any of it is built.*
