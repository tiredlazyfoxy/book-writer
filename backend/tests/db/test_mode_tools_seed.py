"""Default per-mode tool seeding and its idempotency (feature 024, DoD-4).

Bound to the frozen skeleton (`status.md` -> `## Skeleton`):

    app.db.mode_tools:
        DEFAULT_MODE_TOOL_NAMES: dict[str, tuple[str, ...]]
        async def seed_default_mode_tools() -> None
    app.db.assistant_modes:
        DEFAULT_MODE_SYSTEM_PROMPTS: dict[str, str]
        async def seed_default_modes() -> None        (signature unchanged)

    (reused, unchanged) mode_tools.create / list_by_mode / delete_by_mode,
    assistant_modes.get_by_id / update / DEFAULT_MODE_KEYS

Expected values come from the SPEC ONLY:
    - the five default tool sets are `context.md` -> "Default per-mode tool
      selections (authoritative -- the test-coder binds to these)", transcribed
      verbatim below;
    - the five mode keys are `edit-character`, `edit-location`, `edit-fact`,
      `write-chapter`, `close-chapter`;
    - DoD-4: a fresh database carries all five modes with those exact tool sets
      and a NON-BLANK `system_prompt` each; re-running the seed leaves an
      admin-edited `system_prompt` and a deliberately-removed single `mode_tool`
      row (with the mode's other rows intact) both untouched;
    - `plan.md` -> Interface: the idempotency unit is PER MODE, not per row --
      "a mode with **any** existing row ... is left untouched", which is exactly
      what makes a deliberate removal survive.

The `system_prompt` WORDING is deliberately not tested (`plan.md` -> Test plan ->
"Not tested"); only its non-blankness, which DoD-4 names.

`asyncio_mode = "auto"`; the `db` fixture supplies an initialized throwaway
temp-SQLite database, so each test starts with zero mode and mode_tool rows.
"""

from datetime import datetime

import pytest

from app.db import assistant_modes, mode_tools
from app.db.engine import DbConfig
from app.models.mode_tool import ModeTool

# --- context.md -> "Default per-mode tool selections" (authoritative) --------

CODEX_TOOLS = ("web_search", "codex_search", "codex_read_entry", "write_codex_draft")

EXPECTED_TOOLS: dict[str, tuple[str, ...]] = {
    "edit-character": CODEX_TOOLS,
    "edit-location": CODEX_TOOLS,
    "edit-fact": CODEX_TOOLS,
    "write-chapter": (
        "web_search",
        "codex_search",
        "codex_read_entry",
        "read_chapter_text",
        "set_chapter_text",
        "update_selection",
        "add_text",
    ),
    "close-chapter": (
        "draft_chapter_summary",
        "draft_chapter_notes",
        "propose_active_notes",
        "raise_check_flag",
        "read_continuity_context",
    ),
}

FIXED_FIVE_KEYS = set(EXPECTED_TOOLS)


async def _seed() -> None:
    """Both seeds, in the order `services/setup.py` runs them (plan Interface)."""
    await assistant_modes.seed_default_modes()
    await mode_tools.seed_default_mode_tools()


async def _tool_names(mode_key: str) -> list[str]:
    rows = await mode_tools.list_by_mode(mode_key)
    return [row.tool_name for row in rows]


# ---------------------------------------------------------------------------
# DoD-4 (a) -- a fresh database converges on the five modes, their exact tool
#              sets, and a non-blank prompt each
# ---------------------------------------------------------------------------


async def test_fresh_database_carries_five_modes_with_default_tools__DoD4(db: DbConfig):
    # DoD-4: on a fresh database the seed leaves all five modes present, each
    # holding EXACTLY the default tool set context.md names -- no more, no fewer,
    # no duplicate row -- and each carrying a non-blank system_prompt.
    await _seed()

    # The five keys are the fixed system set.
    assert set(assistant_modes.DEFAULT_MODE_KEYS) == FIXED_FIVE_KEYS

    for mode_key, expected in EXPECTED_TOOLS.items():
        names = await _tool_names(mode_key)
        # Exactly the expected set, and each tool exactly once.
        assert set(names) == set(expected)
        assert len(names) == len(expected)

        mode = await assistant_modes.get_by_id(mode_key)
        assert mode is not None
        assert mode.system_prompt is not None
        assert mode.system_prompt.strip() != ""


@pytest.mark.parametrize("mode_key", sorted(EXPECTED_TOOLS))
async def test_repeated_seed_adds_no_duplicate_rows__DoD4(db: DbConfig, mode_key: str):
    # DoD-4: the seed converges -- running it again over an already-seeded
    # database leaves each mode's rows exactly as they were.
    await _seed()
    before = sorted(await _tool_names(mode_key))

    await _seed()

    assert sorted(await _tool_names(mode_key)) == before
    assert len(before) == len(EXPECTED_TOOLS[mode_key])


# ---------------------------------------------------------------------------
# DoD-4 (b) -- a re-run never re-imposes what an admin deliberately changed
# ---------------------------------------------------------------------------

ADMIN_PROMPT = "ADMIN EDITED THIS PROMPT — do not overwrite it."
EDITED_MODE = "edit-character"
TRIMMED_MODE = "write-chapter"
REMOVED_TOOL = "add_text"


async def test_reseed_preserves_admin_prompt_and_removed_tool__DoD4(db: DbConfig):
    # DoD-4 (the property that makes seeding acceptable at all): after an admin
    # edits one mode's system_prompt and deliberately removes ONE tool from
    # another mode, re-running the seed re-imposes neither -- the prompt keeps the
    # admin's text and the removed tool stays removed, while that mode's other
    # rows are intact.
    await _seed()

    # An admin edits one mode's prompt.
    mode = await assistant_modes.get_by_id(EDITED_MODE)
    assert mode is not None
    mode.system_prompt = ADMIN_PROMPT
    mode.modified_at = datetime(2026, 8, 9, 12, 0, 0)
    await assistant_modes.update(mode)

    # An admin removes exactly ONE tool from a different mode, leaving the rest.
    kept = [name for name in EXPECTED_TOOLS[TRIMMED_MODE] if name != REMOVED_TOOL]
    assert len(kept) == len(EXPECTED_TOOLS[TRIMMED_MODE]) - 1
    await mode_tools.delete_by_mode(TRIMMED_MODE)
    for name in kept:
        await mode_tools.create(ModeTool(mode_key=TRIMMED_MODE, tool_name=name))
    assert sorted(await _tool_names(TRIMMED_MODE)) == sorted(kept)

    await _seed()

    # The admin's prompt survived, unchanged and un-blanked.
    reloaded = await assistant_modes.get_by_id(EDITED_MODE)
    assert reloaded is not None
    assert reloaded.system_prompt == ADMIN_PROMPT

    # The deliberately removed tool was NOT re-added...
    names = await _tool_names(TRIMMED_MODE)
    assert REMOVED_TOOL not in names
    # ...and the mode's remaining rows are intact, each still exactly once.
    assert sorted(names) == sorted(kept)

    # Every other mode is untouched by the re-run, and this mode's neighbours
    # kept their full default sets.
    for mode_key, expected in EXPECTED_TOOLS.items():
        if mode_key == TRIMMED_MODE:
            continue
        other = await _tool_names(mode_key)
        assert sorted(other) == sorted(expected)
