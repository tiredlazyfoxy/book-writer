<!-- product-spec:start -->
# Stories — FEAT-011 Content moderation

### US-045 — Admin reads a book in the moderation view only
- **Feature:** FEAT-011 · **Actor:** ACT-001 · **Realizes:** UC-043
- **Status:** proposed
- **Story:** As an admin, I want to read any book in a moderation view, so
  that I can find unwanted or illegal content without authoring access.
- **Acceptance criteria:**
  - **US-045.AC-1** — Given any book regardless of visibility, when an
    admin opens it in the moderation view, then its content is shown
    read-only.
  - **US-045.AC-2** — Given an admin, when the book is open in the
    moderation view, then no authoring action is available to them.
  - **US-045.AC-3** — Given an admin, when they use the main authoring
    interface, then no book access is available to them there.
- **Source:** `[confirmed: user]` interview 2026-07-20, "admin access &
  moderation": "admins can read all books... special read mode."

### US-046 — Admin quarantines a book
- **Feature:** FEAT-011 · **Actor:** ACT-001 · **Realizes:** UC-044
- **Status:** proposed
- **Story:** As an admin, I want to quarantine a book, so that unwanted
  content is taken down immediately and can still be reversed if it was a
  mistake.
- **Acceptance criteria:**
  - **US-046.AC-1** — Given a book that is not quarantined, when an admin
    quarantines it with a reason, then the book becomes invisible to its
    owner and co-authors as well as any reader.
- **Source:** `[confirmed: user]` interview 2026-07-20, "admin access &
  moderation": "quarantine makes the book invisible to everyone including
  its members — fast takedown, reversible mistake."

### US-047 — Admin destroys a quarantined book
- **Feature:** FEAT-011 · **Actor:** ACT-001 · **Realizes:** UC-045
- **Status:** proposed
- **Story:** As an admin, I want to destroy a quarantined book, so that
  illegal content actually leaves the instance.
- **Acceptance criteria:**
  - **US-047.AC-1** — Given a quarantined book, when an admin destroys it,
    then the book is permanently removed.
  - **US-047.AC-2** — Given a book that has never been quarantined, when an
    admin attempts to destroy it directly, then the destruction is
    refused.
- **Source:** `[confirmed: user]` interview 2026-07-20, "admin access &
  moderation": "quarantine a whole book, then destroy it as a separate
  action... permanently."

### US-048 — Owner is told their book was removed and why
- **Feature:** FEAT-011 · **Actor:** ACT-004 · **Realizes:** UC-046
- **Status:** proposed
- **Story:** As a book owner, I want to be told when and why my book was
  removed, so that I'm not left guessing.
- **Acceptance criteria:**
  - **US-048.AC-1** — Given a book that has been quarantined or destroyed,
    when its owner accesses it, then a removal notice is shown stating the
    reason given by the admin.
- **Source:** `[confirmed: user]` interview 2026-07-20, "admin access &
  moderation": "the owner sees a removal notice, with a reason. Not
  silent."

### US-093 — The moderation view includes the codex
- **Feature:** FEAT-011 · **Actor:** ACT-001 · **Realizes:** UC-043
- **Status:** proposed
- **Story:** As an admin, I want the moderation view to include a book's
  codex, so that I can find unwanted lore content, not just chapters.
- **Acceptance criteria:**
  - **US-093.AC-1** — Given any book regardless of visibility, when an
    admin opens it in the moderation view, then its codex is shown
    alongside its chapters, read-only.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 4",
  "codex": "Yes — it's book content."
<!-- product-spec:end -->
