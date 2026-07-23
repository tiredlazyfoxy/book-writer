"""Tests for the require_role(admin) guard factory (feature 005, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001):

    app.services.auth  (AMEND):
        def require_role(min_role: UserRole) -> Callable[..., Awaitable[User]]
            # dependency FACTORY: returns
            #   async def dependency(user: User = Depends(get_current_user)) -> User
            # which returns the caller when the caller's role satisfies the
            # ladder {author:0, admin:1}, else raises HTTPException(403).

    app.models.user  (given):
        class UserRole(str, enum.Enum)  {admin="admin", author="author"}
        class User(SQLModel, table=True)

Expected values come from the spec ONLY — the step DoD (DoD-13), the step
Interface intent ("require_role"), and context.md (cross-cutting decision 1:
ladder {author:0, admin:1}; insufficient -> 403) — never from implementation
internals.

Per 001.context.md ("require_role shape") the inner dependency receives the
resolved caller via `Depends(get_current_user)`, so a unit test may construct
`require_role(admin)` and invoke the returned coroutine directly with a `User`
passed explicitly as `user=` — no live request, no DB — to assert the ladder
(admin admitted, author refused). Async tests use asyncio_mode = "auto".
"""

import pytest
from fastapi import HTTPException

from app.models.user import User, UserRole
from app.services import auth


# DoD-13 (US-005.AC-3): the dependency returned by require_role(admin) returns
# the caller when the caller's role is `admin` (admin level satisfies the
# admin requirement on the ladder author < admin).
async def test_require_role_admin_admits_admin_caller__DoD13_US005_AC3():
    admin_user = User(username="root", role=UserRole.admin)

    dependency = auth.require_role(UserRole.admin)
    result = await dependency(user=admin_user)

    # The guard admits the caller unchanged.
    assert result is admin_user


# DoD-13 (US-005.AC-3): the dependency returned by require_role(admin) rejects a
# caller whose role is `author` (author level is below the admin requirement),
# raising the HTTP-403 error directly from the services layer.
async def test_require_role_admin_rejects_author_caller_with_403__DoD13_US005_AC3():
    author_user = User(username="scribe", role=UserRole.author)

    dependency = auth.require_role(UserRole.admin)

    with pytest.raises(HTTPException) as exc:
        await dependency(user=author_user)

    # Insufficient role -> HTTP 403 (cross-cutting decision 1 / taxonomy).
    assert exc.value.status_code == 403
