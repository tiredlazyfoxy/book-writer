"""Tests for the members-only codex capabilities in authz (feature 013, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001), in
`app.services.authz`:
    Capability.browse_codex      -- new enum member
    Capability.edit_codex_entry  -- new enum member
    def require(access: BookAccess, capability: Capability) -> None
        (raises BookAuthorizationError when the role is not permitted)
`BookAccess`, `AccessRole`, `BookAuthorizationError`, `resolve_book_access`,
`book_access` and the seven pre-existing capabilities are untouched by this step.

Expected values come from the step spec (001.codex-db-authz.md -> Interface
intent + Definition of done, plus 001.context.md), never from implementation
internals:
    - the browse/search capability is granted to owner and co_author and refused
      -- raising BookAuthorizationError -- for reader and none (DoD-10);
    - the create/edit capability is granted to owner and co_author and refused
      for reader and none (DoD-11);
    - the seven pre-existing capabilities and their matrix rows are unchanged:
      read_book -> {owner, co_author, reader}; view_book_detail ->
      {owner, co_author}; archive_book / transfer_ownership / add_member /
      remove_member / set_visibility -> {owner} only (DoD-12, regression guard).

The collaboration-mode (`free` vs `proposal`) nuance is deliberately NOT
asserted here: the role matrix has no vocabulary for it and step 002's codex
service applies it, exactly as 011 layered chat ownership on top of book_access.

BookAccess instances are constructed directly (a frozen dataclass), so these
tests need no database and no HTTP. No network.
"""

import pytest

from app.models.book import BookState, CollaborationMode, Visibility
from app.services.authz import (
    AccessRole,
    BookAccess,
    BookAuthorizationError,
    Capability,
    require,
)

ALL_ROLES = [
    AccessRole.owner,
    AccessRole.co_author,
    AccessRole.reader,
    AccessRole.none,
]

MEMBERS_ONLY = {AccessRole.owner, AccessRole.co_author}


def _access(role: AccessRole) -> BookAccess:
    """A BookAccess with the given role, built directly (no resolve).

    The non-role fields are spec-required BookAccess members but are irrelevant
    to the capability decision, which keys only on `role`.
    """
    return BookAccess(
        book_id=1,
        user_id=2,
        role=role,
        book_state=BookState.active,
        visibility=Visibility.private,
        collaboration_mode=CollaborationMode.free,
    )


def _assert_matrix_row(capability: Capability, granted: set[AccessRole]) -> None:
    """require permits exactly `granted` and raises for every other role."""
    for role in ALL_ROLES:
        if role in granted:
            assert require(_access(role), capability) is None, (
                f"{capability} must be granted to {role}"
            )
        else:
            with pytest.raises(BookAuthorizationError):
                require(_access(role), capability)


# ---------------------------------------------------------------------------
# DoD-10 — the browse/search codex capability is members-only
# ---------------------------------------------------------------------------


# DoD-10 (US-085.AC-1): the browse capability is granted to owner and co_author
# and refused -- raising BookAuthorizationError -- for reader and none.
def test_browse_codex_is_members_only__DoD10_US085_AC1():
    _assert_matrix_row(Capability.browse_codex, MEMBERS_ONLY)


# DoD-10 (US-085.AC-1): spelled out per role, so a failure names the offending
# cell rather than the whole row.
def test_browse_codex_granted_to_owner__DoD10_US085_AC1():
    assert require(_access(AccessRole.owner), Capability.browse_codex) is None


def test_browse_codex_granted_to_co_author__DoD10_US085_AC1():
    assert require(_access(AccessRole.co_author), Capability.browse_codex) is None


def test_browse_codex_refused_for_reader__DoD10_US085_AC1():
    with pytest.raises(BookAuthorizationError):
        require(_access(AccessRole.reader), Capability.browse_codex)


def test_browse_codex_refused_for_none__DoD10_US085_AC1():
    with pytest.raises(BookAuthorizationError):
        require(_access(AccessRole.none), Capability.browse_codex)


# ---------------------------------------------------------------------------
# DoD-11 — the create/edit codex capability is members-only
# ---------------------------------------------------------------------------


# DoD-11 (US-079.AC-1, US-085.AC-1): the create/edit capability is granted to
# owner and co_author and refused for reader and none.
def test_edit_codex_entry_is_members_only__DoD11_US079_AC1():
    _assert_matrix_row(Capability.edit_codex_entry, MEMBERS_ONLY)


# DoD-11 (US-079.AC-1, US-085.AC-1): spelled out per role.
def test_edit_codex_entry_granted_to_owner__DoD11_US079_AC1():
    assert require(_access(AccessRole.owner), Capability.edit_codex_entry) is None


def test_edit_codex_entry_granted_to_co_author__DoD11_US085_AC1():
    assert require(_access(AccessRole.co_author), Capability.edit_codex_entry) is None


def test_edit_codex_entry_refused_for_reader__DoD11_US085_AC1():
    with pytest.raises(BookAuthorizationError):
        require(_access(AccessRole.reader), Capability.edit_codex_entry)


def test_edit_codex_entry_refused_for_none__DoD11_US079_AC1():
    with pytest.raises(BookAuthorizationError):
        require(_access(AccessRole.none), Capability.edit_codex_entry)


# ---------------------------------------------------------------------------
# DoD-12 — regression guard over the seven pre-existing capabilities
# ---------------------------------------------------------------------------


# The pre-existing matrix, per 001.context.md ("Capability currently holds seven
# members") and feature 009's frozen policy. Adding the two codex rows must
# leave every one of these (capability, role) decisions exactly as it was.
PRE_EXISTING_MATRIX: dict[str, set[AccessRole]] = {
    "read_book": {AccessRole.owner, AccessRole.co_author, AccessRole.reader},
    "view_book_detail": {AccessRole.owner, AccessRole.co_author},
    "archive_book": {AccessRole.owner},
    "transfer_ownership": {AccessRole.owner},
    "add_member": {AccessRole.owner},
    "remove_member": {AccessRole.owner},
    "set_visibility": {AccessRole.owner},
}


# DoD-12 (regression guard): all seven pre-existing capability members still
# exist on the enum under their original names.
def test_pre_existing_capabilities_still_exist__DoD12():
    for name in PRE_EXISTING_MATRIX:
        assert hasattr(Capability, name), f"Capability.{name} disappeared"


# DoD-12 (regression guard): every previously granted (capability, role) pair
# still resolves the same way -- granted stays granted, refused stays refused,
# for all four roles across all seven pre-existing capabilities.
@pytest.mark.parametrize("capability_name", sorted(PRE_EXISTING_MATRIX))
def test_pre_existing_matrix_rows_unchanged__DoD12(capability_name: str):
    capability = getattr(Capability, capability_name)
    _assert_matrix_row(capability, PRE_EXISTING_MATRIX[capability_name])


# DoD-12 (regression guard): the role vocabulary itself is unchanged -- the four
# AccessRole members the matrix is keyed on still exist.
def test_access_roles_unchanged__DoD12():
    assert {role.name for role in AccessRole} == {
        "owner",
        "co_author",
        "reader",
        "none",
    }
