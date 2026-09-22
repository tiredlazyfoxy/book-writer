# 015.chapter-writing-free-mode — Chapter writing in blocks (free mode)
<!-- roadmap:start -->
- **Stage:** 5.chapters · **Track:** multi-step · **Size:** L
- **Delivers:** FEAT-009
- **Depends on:** `014.chapter-skeleton`, `010.working-page`

## Definition
Write a chapter in free mode: open a planned chapter (only one open at a
time), add blocks through the one write path, save with the
version/409 concurrency contract and the restore-buffer reconciliation,
close it (ungated at this stage), and reopen a closed chapter (refused
while another is open/closing).

## Scope
**In:** UC-035/036/037/038/039; US-036..041. `ChapterChange` write path;
the planned→open→closing→closed machine (close ungated here); 409/version
handling; content-pane editor for the open chapter.
**Out:** continuity drafting on close (`016.chapter-close-continuity`
gates the close); variants (`018.chapter-history-variants`); composing
blocks by chatting with the assistant (mapped later).

## Open questions for the planner
- The close seam — close is ungated here and `016.chapter-close-continuity`
  later adds the approved-continuity requirement; keep the seam explicit.
<!-- roadmap:end -->
