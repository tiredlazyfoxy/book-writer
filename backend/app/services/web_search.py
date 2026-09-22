"""The ``web_search`` tool — Google Custom Search JSON API over ``httpx``.

The first and only entry in ``services/tools.py:TOOL_REGISTRY`` at this feature.
A stateless async callable: it resolves the api key and engine id through the
``$ENV_VAR`` indirection (``services/secrets.py:resolve_env_ref``), issues one
``GET`` against the Custom Search endpoint in an ``httpx`` async client it owns
and closes, and renders the results into a single compact, model-readable string
(title, snippet and link per result; an explicit "no results" string when the
response carries no ``items``).

**It catches its own failures and returns an error string rather than raising.**
Rationale (``context.md`` → the ``llm`` client constraints): a tool that raises is
wrapped as ``RuntimeError`` by the ``llm`` client and **aborts the entire tool
loop**, and the error is never fed back to the model — so a raising tool turns a
recoverable search failure (unset env var, unconfigured settings, non-2xx,
transport failure, malformed payload) into a failed turn. The resolved key is
never logged and never appears in the returned string.

The parameters are exactly the field names of
``models/schemas/tools.py:WebSearchArgs`` — this is enforced by the ``llm``
client's ``inspect.signature`` validation and must not drift.

Skeleton (011 step 002): the signature is frozen; the body is UNIMPLEMENTED.
"""

import logging

import httpx

from app.services.secrets import resolve_env_ref
from app.settings import get_settings

logger = logging.getLogger(__name__)

# Google Custom Search JSON API endpoint (one GET per call).
_ENDPOINT = "https://www.googleapis.com/customsearch/v1"


async def web_search(query: str, num_results: int = 5) -> str:
    """Search the public web and return a compact, model-readable string.

    Resolves ``google_search_api_key`` and ``google_search_engine_id`` from
    settings through :func:`resolve_env_ref`, issues one ``GET`` to the Custom
    Search endpoint (query, ``cx``, ``num``), and renders each result's title,
    snippet and link. Returns a distinct "no results" string when the response
    carries no ``items``. Every failure mode returns an error string instead of
    raising (see module docstring). The resolved key never appears in the return
    value or the logs.

    Parameters mirror :class:`WebSearchArgs` field names exactly.

    Skeleton (011 step 002): UNIMPLEMENTED.
    """
    settings = get_settings()

    # Resolve the ``$ENV_VAR`` pointers at call time. ``resolve_env_ref`` raises
    # ``LlmServerError`` when the referenced variable is unset — swallow it here so
    # a recoverable configuration problem never aborts the whole tool loop. Error
    # strings below never embed the resolved key or the exception detail (which,
    # for HTTP errors, would carry the key inside the request URL).
    try:
        api_key = resolve_env_ref(settings.google_search_api_key)
        engine_id = resolve_env_ref(settings.google_search_engine_id)
    except Exception:
        logger.warning("web_search: credential reference could not be resolved")
        return "Web search error: the search credential is not available."

    if not api_key or not engine_id:
        return "Web search error: web search is not configured on this server."

    params: dict[str, object] = {
        "key": api_key,
        "cx": engine_id,
        "q": query,
        "num": num_results,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(_ENDPOINT, params=params)
    except Exception:
        # Transport failure (DNS, connection, timeout). Do not stringify the
        # exception — its request URL carries the resolved key.
        logger.warning("web_search: transport failure reaching the search service")
        return "Web search error: could not reach the search service."

    if response.status_code >= 400:
        # Non-2xx. Report the status code only — the request URL (and thus the
        # key) must never appear in the returned string.
        return (
            f"Web search error: the search service returned HTTP "
            f"{response.status_code}."
        )

    try:
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("payload is not a JSON object")
        items = payload.get("items")
        if items is None:
            return f'No results found on the web for "{query}".'
        if not isinstance(items, list):
            raise ValueError("items is not a list")
        if not items:
            return f'No results found on the web for "{query}".'
        rendered: list[str] = []
        for index, item in enumerate(items, start=1):
            title = str(item.get("title", "")).strip()
            snippet = str(item.get("snippet", "")).strip()
            link = str(item.get("link", "")).strip()
            rendered.append(f"{index}. {title}\n{snippet}\n{link}")
    except Exception:
        logger.warning("web_search: malformed response payload")
        return "Web search error: the search service returned an unreadable response."

    return "\n\n".join(rendered)
