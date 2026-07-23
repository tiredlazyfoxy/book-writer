"""Tests for the shared `$ENV` secret resolver (feature 006, step 002).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 002):

    app.services.secrets  (NEW):
        def resolve_env_ref(value: str | None) -> str | None
            # None -> None
            # "$FOO" -> os.environ["FOO"]  (raises env-not-set error when unset)
            # any other value -> returned verbatim
            # (sync; called only at use time)

    app.services.llm_servers  (the typed error lives here, imported by secrets):
        class LlmServerErrorReason(str, enum.Enum)
            invalid_backend_type="invalid-backend-type", missing_field="missing-field",
            not_found="not-found", env_not_set="env-not-set",
            probe_failed="probe-failed"
        class LlmServerError(Exception)  __init__(reason, message="")  -> .reason

Expected values come from the SPEC ONLY — the step DoD (DoD-8) and D3 in
context.md — never from implementation internals.

Key spec facts asserted here (DoD-8 / US-021.AC-1):
    - resolve_env_ref(None) -> None
    - resolve_env_ref("$FOO") -> os.environ["FOO"] (the resolved value at use time)
    - resolve_env_ref(<literal>) -> the same string verbatim
    - resolve_env_ref("$FOO") with FOO unset -> raises LlmServerError whose
      .reason is LlmServerErrorReason.env_not_set (D3: maps to 400).

The resolver is a pure sync function that only reads os.environ; no DB is
needed. Env vars are set/unset with pytest's `monkeypatch` so the process
environment is restored after each test. Async mode is irrelevant here (these
are plain sync tests) but the suite runs under asyncio_mode = "auto".
"""

import pytest

from app.services import secrets
from app.services.llm_servers import LlmServerError, LlmServerErrorReason


# DoD-8 (US-021.AC-1): a None input resolves to None (no key configured).
def test_resolve_none_returns_none__DoD8_US021_AC1():
    assert secrets.resolve_env_ref(None) is None


# DoD-8 (US-021.AC-1): a "$FOO" reference resolves to the value of os.environ["FOO"]
# at use time.
def test_resolve_env_ref_returns_environ_value__DoD8_US021_AC1(monkeypatch):
    monkeypatch.setenv("BOOKWRITER_TEST_SECRET", "s3cr3t-value")

    assert secrets.resolve_env_ref("$BOOKWRITER_TEST_SECRET") == "s3cr3t-value"


# DoD-8 (US-021.AC-1): any value NOT starting with `$` is returned verbatim
# (a stored raw literal key).
def test_resolve_literal_returns_verbatim__DoD8_US021_AC1():
    assert secrets.resolve_env_ref("sk-raw-literal-key") == "sk-raw-literal-key"
    # An empty string is also a literal (not a `$` reference) — returned as-is.
    assert secrets.resolve_env_ref("") == ""


# DoD-8 (US-021.AC-1): a "$FOO" reference whose variable is unset raises the
# typed env-not-set error (D3: maps to 400).
def test_resolve_unset_env_ref_raises_env_not_set__DoD8_US021_AC1(monkeypatch):
    monkeypatch.delenv("BOOKWRITER_TEST_MISSING", raising=False)

    with pytest.raises(LlmServerError) as exc:
        secrets.resolve_env_ref("$BOOKWRITER_TEST_MISSING")
    assert exc.value.reason == LlmServerErrorReason.env_not_set
