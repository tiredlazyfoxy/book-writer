"""Shared ``$ENV`` secret resolver (feature 006, step 002, D3).

The ONE resolver for ``"$ENV_VAR"`` API-key indirection across the codebase.
Resolution happens **only at use time** (step 003's probe / any future embed
call), never at rest — the stored ``api_key`` keeps its raw / ``"$ENV_VAR"`` token
form in the DB.

Import direction (cycle avoidance): this leaf helper imports the typed
:class:`~app.services.llm_servers.LlmServerError` **from** the service module; the
service module does **not** import ``secrets`` (its step-002 functions never
resolve a key), so the module graph is acyclic. Step 003's probe reaches this
helper via a function-local import.

Skeleton (step 002): the signature is frozen; the body is UNIMPLEMENTED.
"""

import os

from app.services.llm_servers import LlmServerError, LlmServerErrorReason

__all__ = ["resolve_env_ref", "LlmServerError", "LlmServerErrorReason"]


def resolve_env_ref(value: str | None) -> str | None:
    """Resolve a stored API-key value to its live secret.

    - ``None`` → ``None``.
    - a value starting with ``$`` → return ``os.environ[name]`` (name = the value
      minus the leading ``$``), raising :class:`LlmServerError` with the
      ``env_not_set`` case (US-021.AC-1) when that variable is unset.
    - any other value → returned verbatim (a raw literal key).
    """
    if value is None:
        return None
    if value.startswith("$"):
        name = value[1:]
        try:
            return os.environ[name]
        except KeyError:
            raise LlmServerError(
                LlmServerErrorReason.env_not_set,
                f"Environment variable '{name}' is not set.",
            )
    return value
