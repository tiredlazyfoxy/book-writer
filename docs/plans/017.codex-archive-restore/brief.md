# 017.codex-archive-restore — Codex archive & restore
<!-- roadmap:start -->
- **Stage:** 6.archive-history · **Track:** multi-step · **Size:** M
- **Delivers:** FEAT-017 (UC-072)
- **Depends on:** `013.codex`

## Definition
Archive a codex entry instead of deleting it, and restore an archived
entry. An archived entry is removed from the vector index and does not
silently break state notes that reference it by name.

## Scope
**In:** UC-072; US-081. Archive/restore lifecycle; index removal on
archive, re-index on restore.
**Out:** chapter archive (no requirement — dropped); version
history/restore (`019.codex-history`); cross-book copy.

## Open questions for the planner
- None.
<!-- roadmap:end -->
