"""Tests for the web_search tool callable (feature 011, step 002).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 002):

    app.services.web_search  (NEW):
        async def web_search(query: str, num_results: int = 5) -> str
        _ENDPOINT = "https://www.googleapis.com/customsearch/v1"

    app.settings.Settings  (two new fields):
        google_search_api_key: str | None      (alias BOOKWRITER_GOOGLE_SEARCH_API_KEY)
        google_search_engine_id: str | None     (alias BOOKWRITER_GOOGLE_SEARCH_ENGINE_ID)
        get_settings() -> Settings  (lru_cached)

    app.services.secrets.resolve_env_ref  (given): "$NAME" -> os.environ[NAME],
        raising the typed env-not-set error when unset.

Expected values come from the SPEC ONLY — the step DoD (DoD-6, DoD-7, DoD-8,
DoD-9), the step Interface intent, and 002.context.md ("The Google Custom Search
JSON API" + "Settings and secrets") — never from implementation internals.

THE AIR GAP / NO NETWORK (DoD-9): every test replaces `httpx.AsyncClient` with a
fake (`monkeypatch.setattr(httpx, "AsyncClient", ...)`) — the frozen intent says
`web_search` "calls the Google Custom Search JSON API over `httpx` in an async
client it owns and closes", and the repo convention (conftest, llm_servers) is
`import httpx; httpx.AsyncClient(...)`, resolved at call time — so patching the
`httpx` module attribute intercepts the client the tool constructs. The fake
supports both `async with client:` and a manual `await client.aclose()`. No test
performs real network I/O.

Settings are lru_cached (`get_settings`), so the autouse fixture clears the cache
before and after each test and the helper clears it again after setting env, so
`web_search`'s call-time `get_settings()` sees the test's configuration.

Key spec facts asserted here:
    - With the boundary mocked to return results, the returned string contains each
      result's title, snippet and link; an absent `items` key yields a distinct
      "no results" string (DoD-6; UC-087 / US-101.AC-1).
    - The api key + engine id are resolved through `$ENV_VAR` indirection, and the
      resolved key never appears in the returned string (DoD-7).
    - Every failure mode returns an error string rather than raising: env var
      unset, settings unconfigured, non-2xx, transport failure, malformed payload
      (DoD-8) — a raising tool would abort the whole loop.
"""

import httpx
import pytest

import app.settings as settings_module
from app.services.web_search import web_search

# Env-var names used for the `$ENV` pointers. Names no other test relies on.
_API_KEY_VAR = "BOOKWRITER_TEST_GSEARCH_API_KEY"
_ENGINE_VAR = "BOOKWRITER_TEST_GSEARCH_ENGINE_ID"
_RESOLVED_SECRET = "super-secret-google-key-abc123"
_RESOLVED_ENGINE = "test-engine-id-xyz"


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Clear the lru_cached Settings before and after each test.

    Env-var changes only take effect if the cached `Settings` is rebuilt.
    """
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


def _configure_search_settings(monkeypatch, *, api_ref: str, engine_ref: str) -> None:
    """Point the two Settings fields at the given `$ENV`/literal references.

    Sets the `validation_alias` env vars and clears the Settings cache so the
    tool's call-time `get_settings()` sees them.
    """
    monkeypatch.setenv("BOOKWRITER_GOOGLE_SEARCH_API_KEY", api_ref)
    monkeypatch.setenv("BOOKWRITER_GOOGLE_SEARCH_ENGINE_ID", engine_ref)
    settings_module.get_settings.cache_clear()


class _FakeResponse:
    """A stand-in httpx.Response: controllable status, JSON body or JSON error."""

    def __init__(
        self,
        *,
        status_code: int = 200,
        json_data: object = None,
        json_exc: BaseException | None = None,
    ) -> None:
        self.status_code = status_code
        self._json_data = json_data
        self._json_exc = json_exc

    def json(self) -> object:
        if self._json_exc is not None:
            raise self._json_exc
        return self._json_data

    def raise_for_status(self) -> "_FakeResponse":
        # Mirrors httpx: a 4xx/5xx raises HTTPStatusError; 2xx is a no-op.
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://www.googleapis.com/customsearch/v1")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=request, response=response
            )
        return self


def _install_fake_client(
    monkeypatch,
    *,
    response: _FakeResponse | None = None,
    get_exc: BaseException | None = None,
    captured: dict | None = None,
):
    """Patch httpx.AsyncClient with a fake driving one GET.

    The fake supports both `async with httpx.AsyncClient() as c:` and a manual
    `c = httpx.AsyncClient(); ...; await c.aclose()` usage. `captured` (when
    given) records the request url / params / call-count.
    """

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, *exc) -> bool:
            return False

        async def aclose(self) -> None:
            return None

        async def get(self, url, params=None, **kwargs) -> _FakeResponse:
            if captured is not None:
                captured["url"] = url
                captured["params"] = params
                captured["calls"] = captured.get("calls", 0) + 1
            if get_exc is not None:
                raise get_exc
            assert response is not None
            return response

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)


# ---------------------------------------------------------------------------
# DoD-6 — results rendering and the "no results" case.
# ---------------------------------------------------------------------------

# DoD-6 (UC-087 / US-101.AC-1): with the HTTP boundary mocked to return results,
# web_search returns one string containing each result's title, snippet and link.
async def test_returns_string_with_each_result_title_snippet_link__DoD6_UC087_US101_AC1(
    monkeypatch,
):
    _configure_search_settings(
        monkeypatch, api_ref="literal-key", engine_ref="literal-engine"
    )
    payload = {
        "items": [
            {
                "title": "First Result Title",
                "snippet": "First result snippet text.",
                "link": "https://example.com/first",
            },
            {
                "title": "Second Result Title",
                "snippet": "Second result snippet text.",
                "link": "https://example.com/second",
            },
        ]
    }
    _install_fake_client(monkeypatch, response=_FakeResponse(json_data=payload))

    result = await web_search(query="anything")

    assert isinstance(result, str)
    for item in payload["items"]:
        assert item["title"] in result
        assert item["snippet"] in result
        assert item["link"] in result


# DoD-6 (UC-087 / US-101.AC-1): a response whose `items` key is ABSENT (Custom
# Search's empty result set) yields a distinct, explicit "no results" string —
# not an error, not a render of any result.
async def test_absent_items_yields_no_results_string__DoD6_UC087_US101_AC1(monkeypatch):
    _configure_search_settings(
        monkeypatch, api_ref="literal-key", engine_ref="literal-engine"
    )
    # Empty result set: `items` is absent, not an empty array (002.context.md).
    _install_fake_client(
        monkeypatch,
        response=_FakeResponse(json_data={"searchInformation": {"totalResults": "0"}}),
    )

    result = await web_search(query="nothing matches this")

    assert isinstance(result, str)
    assert result.strip() != ""
    # The spec quotes an explicit "no results" string as the content.
    assert "no result" in result.lower()


# ---------------------------------------------------------------------------
# DoD-7 — $ENV_VAR indirection; resolved key never in the returned string.
# ---------------------------------------------------------------------------

# DoD-7: web_search resolves its api key and engine id through `$ENV_VAR`
# indirection (the resolved secret, not the `$` pointer, reaches the request) and
# the resolved key NEVER appears in the returned string.
async def test_resolves_env_refs_and_hides_key__DoD7(monkeypatch):
    monkeypatch.setenv(_API_KEY_VAR, _RESOLVED_SECRET)
    monkeypatch.setenv(_ENGINE_VAR, _RESOLVED_ENGINE)
    _configure_search_settings(
        monkeypatch, api_ref=f"${_API_KEY_VAR}", engine_ref=f"${_ENGINE_VAR}"
    )

    payload = {
        "items": [
            {
                "title": "A Title",
                "snippet": "A snippet.",
                "link": "https://example.com/a",
            }
        ]
    }
    captured: dict = {}
    _install_fake_client(
        monkeypatch, response=_FakeResponse(json_data=payload), captured=captured
    )

    result = await web_search(query="query text")

    # The request carried the RESOLVED secret, not the `$` pointer — proving
    # $ENV_VAR indirection was applied at use time.
    request_blob = f"{captured.get('url')} {captured.get('params')}"
    assert _RESOLVED_SECRET in request_blob
    assert f"${_API_KEY_VAR}" not in request_blob

    # ...but the resolved key is never leaked into the model-visible output.
    assert _RESOLVED_SECRET not in result


# ---------------------------------------------------------------------------
# DoD-8 — every failure mode returns an error string rather than raising.
# ---------------------------------------------------------------------------

# DoD-8: a `$ENV` api-key pointer to an UNSET variable — resolve_env_ref raises,
# and web_search swallows it, returning an error string rather than raising.
async def test_unset_env_var_returns_error_string__DoD8(monkeypatch):
    monkeypatch.delenv(_API_KEY_VAR, raising=False)
    monkeypatch.delenv(_ENGINE_VAR, raising=False)
    _configure_search_settings(
        monkeypatch, api_ref=f"${_API_KEY_VAR}", engine_ref=f"${_ENGINE_VAR}"
    )
    # A fake client is installed to guarantee no network even if reached.
    _install_fake_client(monkeypatch, response=_FakeResponse(json_data={}))

    result = await web_search(query="anything")

    assert isinstance(result, str)
    assert result.strip() != ""


# DoD-8: settings unconfigured (both fields default to None) — web_search returns
# an error string rather than raising.
async def test_unconfigured_settings_returns_error_string__DoD8(monkeypatch):
    monkeypatch.delenv("BOOKWRITER_GOOGLE_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("BOOKWRITER_GOOGLE_SEARCH_ENGINE_ID", raising=False)
    settings_module.get_settings.cache_clear()
    _install_fake_client(monkeypatch, response=_FakeResponse(json_data={}))

    result = await web_search(query="anything")

    assert isinstance(result, str)
    assert result.strip() != ""


# DoD-8: a non-2xx response returns an error string rather than raising.
async def test_non_2xx_returns_error_string__DoD8(monkeypatch):
    _configure_search_settings(
        monkeypatch, api_ref="literal-key", engine_ref="literal-engine"
    )
    _install_fake_client(
        monkeypatch, response=_FakeResponse(status_code=500, json_data={})
    )

    result = await web_search(query="anything")

    assert isinstance(result, str)
    assert result.strip() != ""


# DoD-8: a transport failure (httpx raises during the GET) returns an error string
# rather than raising.
async def test_transport_failure_returns_error_string__DoD8(monkeypatch):
    _configure_search_settings(
        monkeypatch, api_ref="literal-key", engine_ref="literal-engine"
    )
    _install_fake_client(
        monkeypatch, get_exc=httpx.ConnectError("connection refused")
    )

    result = await web_search(query="anything")

    assert isinstance(result, str)
    assert result.strip() != ""


# DoD-8: a malformed payload (the response body is not decodable JSON) returns an
# error string rather than raising.
async def test_malformed_payload_returns_error_string__DoD8(monkeypatch):
    _configure_search_settings(
        monkeypatch, api_ref="literal-key", engine_ref="literal-engine"
    )
    _install_fake_client(
        monkeypatch,
        response=_FakeResponse(json_exc=ValueError("Expecting value")),
    )

    result = await web_search(query="anything")

    assert isinstance(result, str)
    assert result.strip() != ""


# ---------------------------------------------------------------------------
# DoD-9 — no real network I/O; the httpx boundary is mocked.
# ---------------------------------------------------------------------------

# DoD-9: the search routes through the mocked httpx boundary — the fake client's
# GET is the only outbound call and no real network I/O occurs.
async def test_no_real_network_boundary_is_mocked__DoD9(monkeypatch):
    _configure_search_settings(
        monkeypatch, api_ref="literal-key", engine_ref="literal-engine"
    )
    captured: dict = {}
    _install_fake_client(
        monkeypatch,
        response=_FakeResponse(
            json_data={
                "items": [
                    {"title": "T", "snippet": "S", "link": "https://example.com/x"}
                ]
            }
        ),
        captured=captured,
    )

    await web_search(query="anything")

    # The fake boundary was exercised exactly once; nothing hit the wire.
    assert captured.get("calls") == 1
