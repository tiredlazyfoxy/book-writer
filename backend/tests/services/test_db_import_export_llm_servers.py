"""Tests for the llm_servers import/export codec + registry entry (feature 006,
step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001):
    def _llm_server_to_dict(server: LlmServer) -> dict[str, object]
                                                    in app.services.db_import_export
    def _dict_to_llm_server(data: dict[str, object]) -> LlmServer
                                                    in app.services.db_import_export
    TABLE_REGISTRY: appended with
        ("llm_servers", LlmServer, _llm_server_to_dict, _dict_to_llm_server)
        AFTER the existing `users` entry (D6). Each entry's FIRST element is the
        zip member filename and its SECOND element is the model class.
                                                    in app.services.db_import_export
    class LlmServer(SQLModel, table=True)            in app.models.llm_server
    class User(SQLModel, table=True)                 in app.models.user

Expected values come from the step spec (001.model-db-importexport.md DoD-5 +
decision D6), never from implementation internals:
    - a LlmServer round-trips through _llm_server_to_dict -> _dict_to_llm_server
      preserving all fields,
    - `enabled_models` is kept as its JSON string (not decoded to a list),
    - `api_key` is REDACTED on export (review R2, superseding step-001 DoD-5's
      "verbatim" clause / D6): a `$ENV` token is a pointer, not a secret, so it is
      preserved verbatim; a raw literal key is replaced with `None`,
    - TABLE_REGISTRY contains a tuple whose zip filename is "llm_servers" and
      whose model class is LlmServer, positioned AFTER the `users` entry.

These codecs are pure transforms, so no DB fixture is needed for the round-trip.
"""

from datetime import datetime

from app.models.llm_server import LlmServer
from app.models.user import User
from app.services.db_import_export import (
    TABLE_REGISTRY,
    _dict_to_llm_server,
    _llm_server_to_dict,
)


def _fully_populated_server() -> LlmServer:
    """A LlmServer with every field set to a distinct, non-default value."""
    return LlmServer(
        id=7,
        name="OpenAI Prod",
        backend_type="openai",
        base_url="https://api.openai.com/v1",
        api_key="$OPENAI_API_KEY",
        enabled_models='["gpt-4o", "gpt-4o-mini"]',
        is_active=True,
        is_embedding=True,
        embedding_model="text-embedding-3-small",
        created_at=datetime(2026, 7, 23, 12, 30, 0),
        modified_at=datetime(2026, 7, 23, 13, 45, 0),
    )


# DoD-5 (D6): a LlmServer round-trips through _llm_server_to_dict ->
# _dict_to_llm_server preserving all fields.
def test_llm_server_codec_round_trips_all_fields__DoD5():
    server = _fully_populated_server()

    data = _llm_server_to_dict(server)
    restored = _dict_to_llm_server(data)

    assert restored.id == server.id
    assert restored.name == server.name
    assert restored.backend_type == server.backend_type
    assert restored.base_url == server.base_url
    assert restored.api_key == server.api_key
    assert restored.enabled_models == server.enabled_models
    assert restored.is_active == server.is_active
    assert restored.is_embedding == server.is_embedding
    assert restored.embedding_model == server.embedding_model
    assert restored.created_at == server.created_at
    assert restored.modified_at == server.modified_at


# DoD-5 (D6): `enabled_models` is exported as its JSON string (kept verbatim,
# not decoded into a list), and restores back to the same string.
def test_enabled_models_kept_as_json_string__DoD5():
    server = _fully_populated_server()

    data = _llm_server_to_dict(server)

    # Exported form is the JSON string itself, not a decoded list.
    assert isinstance(data["enabled_models"], str)
    assert data["enabled_models"] == '["gpt-4o", "gpt-4o-mini"]'

    # And it restores to the identical JSON string.
    restored = _dict_to_llm_server(data)
    assert restored.enabled_models == '["gpt-4o", "gpt-4o-mini"]'


# Review R2 (supersedes step-001 DoD-5 / D6 "verbatim" clause): on export a raw
# literal `api_key` is REDACTED to None (no cleartext secret in the archive),
# while a `$ENV` token is a pointer, not a secret, and is preserved verbatim.
def test_api_key_redacted_on_export__R2():
    # (a) A raw literal key is redacted to None on export, and restores as None.
    literal_server = LlmServer(
        id=8,
        name="OpenAI Literal",
        backend_type="openai",
        base_url="https://api.openai.com/v1",
        api_key="sk-secret",
    )
    literal_data = _llm_server_to_dict(literal_server)
    assert literal_data["api_key"] is None

    restored_literal = _dict_to_llm_server(literal_data)
    assert restored_literal.api_key is None

    # (b) A `$ENV` token is preserved verbatim on export, and restores unchanged.
    env_server = _fully_populated_server()  # api_key="$OPENAI_API_KEY"
    env_data = _llm_server_to_dict(env_server)
    assert env_data["api_key"] == "$OPENAI_API_KEY"

    restored_env = _dict_to_llm_server(env_data)
    assert restored_env.api_key == "$OPENAI_API_KEY"


# DoD-5 (D6): TABLE_REGISTRY contains a tuple whose zip filename is "llm_servers"
# and whose model class is LlmServer, positioned AFTER the `users` entry. Each
# entry's first element is the zip member filename; its second is the model class.
def test_table_registry_has_llm_servers_after_users__DoD5():
    registry = list(TABLE_REGISTRY)
    filenames = [entry[0] for entry in registry]

    assert "users" in filenames, "the users entry must exist as the prior entry"
    assert "llm_servers" in filenames, "the llm_servers entry must be registered"

    users_index = filenames.index("users")
    llm_index = filenames.index("llm_servers")

    # The llm_servers entry is positioned after the users entry (D6).
    assert llm_index > users_index

    # The llm_servers tuple binds the correct model class, and users still binds
    # User (confirming no reordering of the prior entry).
    llm_entry = registry[llm_index]
    assert llm_entry[1] is LlmServer
    assert registry[users_index][1] is User
