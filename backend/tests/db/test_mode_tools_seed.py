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

Widened by fast/007.codex-create-from-chat for its DoD-8 ONLY: the default tool
sets now also carry `create_codex_entry` in `edit-character`, `edit-location`,
`edit-fact` and `write-chapter`, and must NOT carry it in `close-chapter`
(`fast/007/plan.md` -> Interface intent -> "Seeded defaults" and DoD-8). Every
other assertion here is feature 024's, unchanged.

Widened again by 025.codex-listing-tools, which appends the four listing-tool
names to the `edit-character`, `edit-location`, `edit-fact` and `write-chapter`
tuples and leaves `close-chapter` alone (`025/plan.md` -> Interface ->
`backend/app/db/mode_tools.py`). Only the expected tuples move; no new `[test]`
DoD item lives in this file (025's DoD-14 is `[verify]`), and every assertion
below is unchanged.

Widened once more by 026.memos step 008, which appends `create_memo` to ALL FIVE
default tuples (`008.create-memo-tool.md` -> Interface intent ->
`backend/app/db/mode_tools.py`). As with the two widenings above, only the
expected tuples move and every pre-existing assertion is unchanged. That step
also brings this file two `[test]` DoD items of its own, at the bottom:

    026 DoD-7  -- `DEFAULT_MODE_TOOL_NAMES` names `create_memo` for all five
                  modes, AND seeding stays idempotent PER MODE, so an existing
                  install is NOT backfilled (`026/context.md` -> decision 10).
    026 DoD-11 -- (US-130.AC-1) each of the five seeded mode prompts carries
                  guidance that a memo is created only on the author's direct
                  request, never unasked.

The `system_prompt` WORDING is deliberately not tested (`plan.md` -> Test plan ->
"Not tested"); only its non-blankness, which DoD-4 names. 026's DoD-11 does not
break that rule: it asserts the guidance's SUBSTANCE tolerantly (the prompt speaks
of memos, of a direct request, and of not creating one unasked) and never pins a
sentence. US-130 is prompt-enforced by design and inherits US-121.AC-3's caveat --
an administrator who rewrites a mode prompt can weaken it -- so DoD-11 pins that
the guidance SHIPS, never that a model obeys it.

`asyncio_mode = "auto"`; the `db` fixture supplies an initialized throwaway
temp-SQLite database, so each test starts with zero mode and mode_tool rows.
"""

import re
from datetime import datetime

import pytest

from app.db import assistant_modes, mode_tools
from app.db.engine import DbConfig
from app.models.mode_tool import ModeTool

# --- context.md -> "Default per-mode tool selections" (authoritative) --------

# fast/007 DoD-8: the mode-gated creation tool joins the three codex-editing
# modes and write-chapter, and is absent from close-chapter.
CREATE_TOOL = "create_codex_entry"

CREATE_TOOL_MODES = ("edit-character", "edit-location", "edit-fact", "write-chapter")
NO_CREATE_TOOL_MODE = "close-chapter"

# 025.codex-listing-tools widens four of the five default tuples: each of
# `edit-character`, `edit-location`, `edit-fact` and `write-chapter` gains all four
# listing-tool names; `close-chapter` is unchanged (`025/plan.md` -> Interface ->
# `backend/app/db/mode_tools.py`, transcribed verbatim below).
LIST_TOOLS = (
    "codex_list_entries",
    "codex_list_characters",
    "codex_list_locations",
    "codex_list_facts",
)

# 026.memos step 008: the memo-creation tool joins ALL FIVE default tuples --
# close-chapter included, unlike the two widenings above (`008.create-memo-tool.md`
# -> Interface intent: "`DEFAULT_MODE_TOOL_NAMES` gains `create_memo` for **all
# five** modes").
MEMO_TOOL = "create_memo"

CODEX_TOOLS = (
    "web_search",
    "codex_search",
    "codex_read_entry",
    "write_codex_draft",
    CREATE_TOOL,
    *LIST_TOOLS,
    MEMO_TOOL,
)

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
        CREATE_TOOL,
        *LIST_TOOLS,
        MEMO_TOOL,
    ),
    "close-chapter": (
        "draft_chapter_summary",
        "draft_chapter_notes",
        "propose_active_notes",
        "raise_check_flag",
        "read_continuity_context",
        MEMO_TOOL,
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
# fast/007 DoD-8 -- the seeded defaults gate `create_codex_entry` by mode
# ---------------------------------------------------------------------------


def test_default_mode_tool_names_gate_create_codex_entry__DoD8():
    # fast/007 DoD-8: DEFAULT_MODE_TOOL_NAMES lists `create_codex_entry` for
    # edit-character, edit-location, edit-fact and write-chapter, and NOT for
    # close-chapter.
    for mode_key in CREATE_TOOL_MODES:
        assert CREATE_TOOL in mode_tools.DEFAULT_MODE_TOOL_NAMES[mode_key]
    assert CREATE_TOOL not in mode_tools.DEFAULT_MODE_TOOL_NAMES[NO_CREATE_TOOL_MODE]


async def test_seeded_rows_gate_create_codex_entry_by_mode__DoD8(db: DbConfig):
    # fast/007 DoD-8: a freshly seeded database carries a `create_codex_entry`
    # mode_tool row for the four authoring modes and none for close-chapter.
    await _seed()

    for mode_key in CREATE_TOOL_MODES:
        assert CREATE_TOOL in await _tool_names(mode_key)
    assert CREATE_TOOL not in await _tool_names(NO_CREATE_TOOL_MODE)


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


# ---------------------------------------------------------------------------
# 026.memos step 008 — DoD-7: `create_memo` in all five default tuples, AND
#                             seeding still idempotent PER MODE
# ---------------------------------------------------------------------------


# 026 DoD-7 (first half): `DEFAULT_MODE_TOOL_NAMES` names `create_memo` for ALL
# FIVE modes -- close-chapter included. This is the half that keeps US-129.AC-5
# reachable: an administrator can still edit a mode down and remove the tool, and
# the visible refusal is then observable rather than vacuous
# (`008.context.md` -> "Why both halves — BASE **and** the seeded rows").
def test_default_mode_tool_names_carry_create_memo_for_all_five__026_DoD7():
    assert set(mode_tools.DEFAULT_MODE_TOOL_NAMES) == FIXED_FIVE_KEYS

    for mode_key in FIXED_FIVE_KEYS:
        names = mode_tools.DEFAULT_MODE_TOOL_NAMES[mode_key]
        assert MEMO_TOOL in names, mode_key
        # Once per mode, not twice.
        assert list(names).count(MEMO_TOOL) == 1, mode_key


# 026 DoD-7 (first half, at the row level): a FRESH install's seeded rows carry
# the tool for every one of the five modes.
async def test_fresh_install_seeds_create_memo_for_all_five__026_DoD7(db: DbConfig):
    await _seed()

    for mode_key in sorted(FIXED_FIVE_KEYS):
        assert MEMO_TOOL in await _tool_names(mode_key), mode_key


# 026 DoD-7 (second half -- and the reason an EXISTING install needs an
# administrator to add the tool by hand, `026/context.md` -> decision 10):
# seeding is idempotent PER MODE, so a mode that already has rows is left
# ENTIRELY untouched -- it is not topped up with the new default, not even by one
# row. The other four modes, which had no rows, are seeded normally: the
# idempotence unit is the mode, not the database.
#
# This is deliberately NOT a defect to "fix" with a backfill; the plan forbids
# planning one.
async def test_existing_install_is_not_backfilled_with_create_memo__026_DoD7(
    db: DbConfig,
):
    existing_mode = "edit-fact"
    prior_rows = ["web_search", "codex_search"]

    # An instance that has been running since before this feature: this mode
    # already carries the administrator's selection.
    for name in prior_rows:
        await mode_tools.create(ModeTool(mode_key=existing_mode, tool_name=name))

    await _seed()

    # Left entirely untouched -- no create_memo, and nothing else added either.
    assert sorted(await _tool_names(existing_mode)) == sorted(prior_rows)
    assert MEMO_TOOL not in await _tool_names(existing_mode)

    # The modes that had no rows were seeded, and they do carry the tool.
    for mode_key in sorted(FIXED_FIVE_KEYS - {existing_mode}):
        assert MEMO_TOOL in await _tool_names(mode_key), mode_key


# ---------------------------------------------------------------------------
# 026.memos step 008 — DoD-11 (US-130.AC-1): the seeded prompts carry the
#                              "only on the author's direct request" guidance
# ---------------------------------------------------------------------------

# Asserted by SUBSTANCE, tolerant of wording, and SCOPED to the memo guidance
# itself. Two properties this check deliberately has, both of which an earlier
# draft got wrong:
#
#  - It keys on SUBSTANCE, not on a list of accepted phrasings. A closed phrase
#    list is an assertion the DoD does not make and one a blind coder cannot
#    satisfy: they have no way to know which turns of phrase the list admits, and
#    a perfectly good sentence in an unlisted grammatical form reads as a failure.
#    So the two halves are keyed on word STEMS -- `ask` covers asks / asked /
#    asking, `request` covers request / requests / requested / "on request" -- and
#    the restrictive half on the ordinary restriction and negation words.
#  - It scans only the MEMO PARAGRAPH, not the whole prompt. A mode prompt is long
#    and already talks about asking, requesting and not doing things unprompted
#    for reasons that have nothing to do with memos, so a whole-prompt scan is
#    partly satisfied by pre-existing text and the clause stops saying what it
#    means. The unit is the BLANK-LINE-DELIMITED PARAGRAPH containing the memo
#    mention: the way a tool is actually documented -- one paragraph per tool --
#    and therefore the unit the guidance really lives in.
#
# Two narrower units were tried and abandoned, recorded here so neither is
# reinvented:
#
#  - A SENTENCE containing the memo mention. Too narrow: it breaks guidance
#    legitimately split across sentences ("Never create one unasked. Create a memo
#    only when the author asks.").
#  - That sentence plus its two immediate NEIGHBOURS, with a token anchor
#    requiring one half to land in a sentence literally containing "memo". Wrong
#    on both sides. Too LOOSE: a memo paragraph carrying only the request half
#    still borrowed the restriction half from the codex-creation rule that happens
#    to sit next to it. And too TIGHT in a way a blind coder could never diagnose:
#    it rejected the DEFAULT tool-paragraph shape, where the first sentence names
#    and defines the tool and the second states the rule with a PRONOUN referring
#    back -- "`create_memo` saves a standing memo the author keeps for this book.
#    Call it only when they have directly asked you to note something down." The
#    guidance is plainly present; the rule sentence simply does not repeat the
#    noun, and no failure message could tell the coder that repeating it was the
#    fix. That is the same "a blind coder cannot satisfy this" fault as the closed
#    phrase list above, in a different costume.
#
# The paragraph unit dominates both: it keeps the split-across-sentences tolerance,
# accepts the pronoun form, and rejects the borrowing the window admitted.
#
# The exact sentence stays the coder's, and an administrator may rewrite it later
# -- which is precisely the caveat US-130's Note records. Nothing here claims a
# model obeys the guidance; only that it ships.

# Matched on WORD boundaries, so a stem cannot be satisfied by an unrelated word
# that merely contains it -- `\bask` is asks / asked / asking but never "task",
# and `\bnot\b` is the negation but never "note" or "nothing", both of which a
# mode prompt is full of.

# The author ASKED for it: any inflection of ask or request, or the negative form
# of the same relation.
_REQUEST_PATTERNS = (r"\bask", r"\brequest", r"\bunasked\b", r"\bunprompted\b")

# ...and ONLY then: the restriction / negation that carries "never unasked".
# `solely` / `exclusively` are the "only" family a coder may reach for instead
# ("solely at the author's request", "exclusively in response to a request"); both
# are restriction words in ordinary use and cost nothing in precision.
_RESTRICTION_PATTERNS = (
    r"\bonly\b",
    r"\bsolely\b",
    r"\bexclusively\b",
    r"\bnever\b",
    r"\bunless\b",
    r"\bnot\b",
    r"n't\b",
    r"\bwithout\b",
    r"\bunasked\b",
    r"\bunprompted\b",
)

_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")


def _memo_guidance(prompt: str) -> str:
    """The memo guidance: every blank-line paragraph that mentions a memo."""
    paragraphs = _PARAGRAPH_BREAK.split(prompt.lower())
    return "\n".join(
        paragraph for paragraph in paragraphs if "memo" in paragraph
    )


def _matches(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _prompt_carries_memo_guidance(prompt: str) -> None:
    assert "memo" in prompt.lower(), "the prompt says nothing about memos"

    guidance = _memo_guidance(prompt)

    # Both halves must live in the memo's OWN paragraph. Neither may be borrowed
    # from the paragraph next door -- which, on `write-chapter`, is the
    # codex-creation rule and carries both halves for its own reasons.
    assert _matches(_REQUEST_PATTERNS, guidance), (
        "the memo guidance does not tie creating one to the author asking for it: "
        f"{guidance!r}"
    )
    assert _matches(_RESTRICTION_PATTERNS, guidance), (
        "the memo guidance does not restrict creation to that request -- nothing "
        f"in it says a memo is never created unasked: {guidance!r}"
    )


# 026 DoD-11: the guidance is in the shipped default for every one of the five
# modes.
@pytest.mark.parametrize("mode_key", sorted(FIXED_FIVE_KEYS))
def test_default_prompt_carries_memo_guidance__026_DoD11(mode_key: str):
    prompt = assistant_modes.DEFAULT_MODE_SYSTEM_PROMPTS[mode_key]

    assert isinstance(prompt, str)
    _prompt_carries_memo_guidance(prompt)


# 026 DoD-11: and it actually reaches the database on a fresh install -- the
# guidance ships in the SEEDED prompts, which is what the clause pins.
async def test_seeded_prompts_carry_memo_guidance__026_DoD11(db: DbConfig):
    await _seed()

    for mode_key in sorted(FIXED_FIVE_KEYS):
        mode = await assistant_modes.get_by_id(mode_key)
        assert mode is not None, mode_key
        assert mode.system_prompt is not None, mode_key
        _prompt_carries_memo_guidance(mode.system_prompt)
