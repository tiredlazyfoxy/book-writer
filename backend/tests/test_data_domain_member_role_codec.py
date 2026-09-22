"""JSONL codec round-trip for the MemberRole retype (feature 009, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001):
    class MemberRole(str, enum.Enum) with sole member co_author = "co_author"
                                                      in app.models.book_member
    class BookMember(SQLModel, table=True); role: MemberRole
                                                      in app.models.book_member
    class Book(SQLModel, table=True)                  in app.models.book
    def _book_to_dict / _dict_to_book                 in app.services.db_import_export
    def _book_member_to_dict / _dict_to_book_member   in app.services.db_import_export

Expected values come from the step spec (001.db-layer-extensions.md DoD-2 +
CLAUDE.md -> "DB Import/Export"), never from implementation internals:
    - DoD-2: a Book + BookMember round-trip through the JSONL export->import codec
      preserves `role` as MemberRole.co_author. Per the step brief, this is
      asserted by VALUE equality against MemberRole.co_author.

These codecs are pure transforms (like the 008 codec tests), so no DB fixture is
needed — the dict pair is exercised directly (_x_to_dict -> _dict_to_x).
"""

from datetime import datetime

from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.book_member import BookMember, MemberRole
from app.services.db_import_export import (
    _book_member_to_dict,
    _book_to_dict,
    _dict_to_book,
    _dict_to_book_member,
)


# DoD-2: a Book and a BookMember (role=MemberRole.co_author) round-trip through
# the export->import codec pair; the book's core fields survive and `role` is
# preserved as MemberRole.co_author (value equality per the step brief).
def test_book_and_member_codec_round_trip_preserves_role__DoD2():
    book = Book(
        id=555,
        title="A Book",
        description="A description",
        owner_id=42,
        collaboration_mode=CollaborationMode.free,
        visibility=Visibility.private,
        state=BookState.active,
        system_prompt="",
        active_notes="",
        created_at=None,
        modified_at=None,
    )
    member = BookMember(
        id=101,
        book_id=555,
        user_id=303,
        role=MemberRole.co_author,
        created_at=datetime(2026, 7, 25, 8, 15, 0),
    )

    restored_book = _dict_to_book(_book_to_dict(book))
    restored_member = _dict_to_book_member(_book_member_to_dict(member))

    # The book survives the round-trip (ids parse back to the same ints).
    assert restored_book.id == 555
    assert restored_book.owner_id == 42

    # The membership survives, and `role` round-trips as MemberRole.co_author.
    assert restored_member.book_id == 555
    assert restored_member.user_id == 303
    assert restored_member.role == MemberRole.co_author
