"""ModeTool data access. Session-free public API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM
row types never leak past this module (see ``docs/architecture/backend.md`` —
layer separation). Public functions accept and return ``ModeTool`` or plain
types.

Covers the mode-to-tool link rows: ``create``, ``get_by_id``, ``list_by_mode``
and the count-returning bulk ``delete_by_mode`` (``0`` is a normal result).
"""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.mode_tool import ModeTool

# The default tool selection seeded for each of the fixed five modes on a fresh
# database (024, D4). Keys mirror ``db/assistant_modes.py:DEFAULT_MODE_KEYS``;
# every name is an entry of ``services/tools.py:TOOL_REGISTRY``.
#
# A mode with ZERO ``mode_tool`` rows is an empty allowlist (the 012 rule, which
# 024 does not touch) — so before this constant existed, every one of the five
# modes resolved to no tools at all. Only the seeded STARTING STATE changes.
#
# The three codex modes and ``write-chapter`` carry ``web_search`` because losing
# it on a mode-bearing turn was an unintended consequence of the zero-rows rule,
# not a deliberate narrowing (``BASE_TOOL_NAMES`` gives it to every mode-less
# turn). ``close-chapter`` carries exactly the five tools
# ``assistant-config.md`` / ``services/close_tools.py`` already name as its set —
# no more.
#
# The four AUTHORING modes carry ``create_codex_entry`` (fast/007 D6): the three
# codex modes because the author is already working on lore there and the entry
# they ask for next is often a different one, and ``write-chapter`` because
# asking for an entry mid-chapter is the case the feature exists for.
# **``close-chapter`` deliberately does not.** A close run is the least
# supervised turn in the system — it already drafts summaries, may replace the
# live note set, may raise flags and may end with the chapter closed — and a run
# nobody is watching minting codex entries is the runaway case the tool's
# per-turn cap exists to bound. This reaches FRESH INSTALLS ONLY: the seeder
# below is idempotent per mode, so an already-seeded database gets the tool only
# when an administrator adds it in the assistant-config editor (D2/D3).
#
# The four AUTHORING modes also carry the four CODEX LISTING tools (025): a mode
# that can search and read the codex should be able to see what is in it, which
# is what keeps the model from inventing a duplicate of an entry it has never
# been shown. ``close-chapter`` again does not — its five tools are the closing
# set ``assistant-config.md`` names, and a close run reads the codex through
# ``read_continuity_context``. Fresh installs only, for the same reason as above.
#
# All five modes carry ``create_memo`` (026 step 008). Unlike every other name
# here it is seeded into ``close-chapter`` too: a memo is the AUTHOR's own
# private standing note and not book content, so the runaway-write argument that
# keeps ``create_codex_entry`` out of the close run does not apply — nothing a
# memo touches is reviewed, shared or part of the book. It is prompt-gated
# instead, by the "only on the author's direct request" guidance
# ``db/assistant_modes.py`` seeds into all five prompts (US-130).
#
# Seeding it here reaches FRESH INSTALLS ONLY, for the same reason as the two
# additions above: the seeder is idempotent per mode, so on an existing instance
# an administrator adds ``create_memo`` to the five modes BY HAND in the
# assistant-config editor (``026/context.md`` → decision 10 — a known
# consequence of idempotent seeding, not a defect, and deliberately NOT worked
# around with a backfill). ``assistant_runtime.BASE_TOOL_NAMES`` covers every
# mode-less surface meanwhile, and these rows are what keep US-129.AC-5's
# visible refusal reachable, BASE not overriding a mode's allowlist.
#
# Each tuple is in ``services/tools.py:TOOL_REGISTRY`` order, which is why
# ``create_codex_entry`` trails ``write_codex_draft`` in the codex modes and
# precedes the chapter tools in ``write-chapter``, and why ``create_memo`` — the
# registry's last entry — trails every name in all five.
DEFAULT_MODE_TOOL_NAMES: dict[str, tuple[str, ...]] = {
    "edit-character": (
        "web_search",
        "codex_search",
        "codex_read_entry",
        "write_codex_draft",
        "create_codex_entry",
        "codex_list_entries",
        "codex_list_characters",
        "codex_list_locations",
        "codex_list_facts",
        "create_memo",
    ),
    "edit-location": (
        "web_search",
        "codex_search",
        "codex_read_entry",
        "write_codex_draft",
        "create_codex_entry",
        "codex_list_entries",
        "codex_list_characters",
        "codex_list_locations",
        "codex_list_facts",
        "create_memo",
    ),
    "edit-fact": (
        "web_search",
        "codex_search",
        "codex_read_entry",
        "write_codex_draft",
        "create_codex_entry",
        "codex_list_entries",
        "codex_list_characters",
        "codex_list_locations",
        "codex_list_facts",
        "create_memo",
    ),
    "write-chapter": (
        "web_search",
        "codex_search",
        "codex_read_entry",
        "create_codex_entry",
        "read_chapter_text",
        "set_chapter_text",
        "update_selection",
        "add_text",
        "codex_list_entries",
        "codex_list_characters",
        "codex_list_locations",
        "codex_list_facts",
        "create_memo",
    ),
    "close-chapter": (
        "draft_chapter_summary",
        "draft_chapter_notes",
        "propose_active_notes",
        "raise_check_flag",
        "read_continuity_context",
        "create_memo",
    ),
}


async def create(row: ModeTool) -> ModeTool:
    """Persist ``row`` and return it with its snowflake ``id`` populated."""
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def get_by_id(id: int) -> ModeTool | None:
    """Return the ``ModeTool`` with primary key ``id``, or ``None``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(select(ModeTool).where(ModeTool.id == id))
        return result.one_or_none()


async def list_by_mode(mode_key: str) -> list[ModeTool]:
    """Return every ``ModeTool`` row whose ``mode_key`` equals ``mode_key``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(ModeTool).where(ModeTool.mode_key == mode_key)
        )
        return list(result.all())


async def delete_by_mode(mode_key: str) -> int:
    """Delete every ``ModeTool`` row for ``mode_key``; return how many were removed.

    The first half of the replace-set save (``assistant-config.md`` → replace-set
    semantics). Returns a **count**, not a ``bool`` like
    ``db/llm_servers.py:71 delete`` — a zero result is a normal, non-error state
    because an unconfigured mode legitimately has no rows.
    """
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(ModeTool).where(ModeTool.mode_key == mode_key)
        )
        rows = list(result.all())
        for row in rows:
            await session.delete(row)
        await session.commit()
        return len(rows)


async def seed_default_mode_tools() -> None:
    """Idempotently give each default mode its default tool selection (024, D4).

    For every key of :data:`DEFAULT_MODE_TOOL_NAMES`: if that mode currently holds
    **zero** ``ModeTool`` rows, insert one row per name in its default set. A mode
    with **any** existing row — previously seeded, admin-edited down to a subset,
    or admin-extended — is left entirely untouched.

    **The idempotency unit is the mode, not the row.** That is the whole safety
    property: a tool an admin deliberately removed is never re-added, as long as
    the mode still holds at least one row. Safe to call any number of times.

    Called from ``services/setup.py`` at both existing ``seed_default_modes()``
    call sites, immediately after that call.
    """
    for mode_key, tool_names in DEFAULT_MODE_TOOL_NAMES.items():
        # The idempotency check, asked ONCE per mode: any row at all means this
        # mode's selection is somebody's decision — a previous seed's or an
        # admin's — and the whole set is left alone. Asking per (mode, tool)
        # instead would re-add a tool an admin deliberately removed on every
        # subsequent seed, which is the failure this shape exists to prevent.
        if await list_by_mode(mode_key):
            continue
        for tool_name in tool_names:
            await create(ModeTool(mode_key=mode_key, tool_name=tool_name))
