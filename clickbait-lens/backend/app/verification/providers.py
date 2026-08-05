"""Live search providers.

``duckduckgo`` is the keyless default so the prototype does real verification out
of the box. ``tavily`` and ``brave`` are better but need API keys. ``fixture``
is deterministic and offline — the test suite uses it so verification tests
don't depend on the live web.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from urllib.parse import quote_plus, unquote, urlparse

import httpx
from selectolax.parser import HTMLParser

from ..config import get_settings
from .base import SearchResult

log = logging.getLogger(__name__)

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "search_results.json"


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.removeprefix("www.")
    except ValueError:
        return ""


class DuckDuckGoProvider:
    """Keyless search via DuckDuckGo's HTML endpoint.

    No API key, no quota — at the cost of being scraping, so it can break when
    the markup changes. Swap in Tavily or Brave for anything load-bearing.
    """

    name = "duckduckgo"
    ENDPOINT = "https://html.duckduckgo.com/html/"

    async def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        settings = get_settings()
        try:
            async with httpx.AsyncClient(
                timeout=settings.search_timeout_seconds,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; ClickbaitLens/0.1)"},
            ) as client:
                response = await client.post(self.ENDPOINT, data={"q": query})
                response.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("duckduckgo search failed: %s", exc)
            return []
        return self._parse(response.text, limit)

    def _parse(self, html: str, limit: int) -> list[SearchResult]:
        tree = HTMLParser(html)
        results: list[SearchResult] = []
        for node in tree.css("div.result"):
            link = node.css_first("a.result__a")
            if link is None:
                continue
            url = self._clean_url(link.attributes.get("href", ""))
            snippet_node = node.css_first(".result__snippet")
            results.append(
                SearchResult(
                    title=link.text(strip=True),
                    url=url,
                    snippet=snippet_node.text(strip=True) if snippet_node else "",
                    source=_domain(url),
                )
            )
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def _clean_url(href: str) -> str:
        # DuckDuckGo wraps results as /l/?uddg=<encoded target>
        match = re.search(r"uddg=([^&]+)", href)
        return unquote(match.group(1)) if match else href


class TavilyProvider:
    """Tavily search API — purpose-built for retrieval, returns clean snippets."""

    name = "tavily"
    ENDPOINT = "https://api.tavily.com/search"

    async def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        settings = get_settings()
        if not settings.tavily_api_key:
            log.warning("CBL_TAVILY_API_KEY is not set; returning no evidence")
            return []
        payload = {
            "api_key": settings.tavily_api_key,
            "query": query,
            "max_results": limit,
            "search_depth": "advanced",
            "include_answer": False,
        }
        try:
            async with httpx.AsyncClient(timeout=settings.search_timeout_seconds) as client:
                response = await client.post(self.ENDPOINT, json=payload)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("tavily search failed: %s", exc)
            return []
        return [
            SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
                source=_domain(item.get("url", "")),
                published=item.get("published_date"),
            )
            for item in data.get("results", [])[:limit]
        ]


class BraveProvider:
    """Brave Search API."""

    name = "brave"
    ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

    async def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        settings = get_settings()
        if not settings.brave_api_key:
            log.warning("CBL_BRAVE_API_KEY is not set; returning no evidence")
            return []
        try:
            async with httpx.AsyncClient(timeout=settings.search_timeout_seconds) as client:
                response = await client.get(
                    self.ENDPOINT,
                    params={"q": query, "count": limit},
                    headers={
                        "Accept": "application/json",
                        "X-Subscription-Token": settings.brave_api_key,
                    },
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("brave search failed: %s", exc)
            return []
        return [
            SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=re.sub(r"<[^>]+>", "", item.get("description", "")),
                source=_domain(item.get("url", "")),
                published=item.get("age"),
            )
            for item in data.get("web", {}).get("results", [])[:limit]
        ]


class FixtureProvider:
    """Offline provider backed by a JSON file. Deterministic — used by tests."""

    name = "fixture"

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or FIXTURE_PATH
        self._data: dict[str, list[dict]] | None = None

    def _load(self) -> dict[str, list[dict]]:
        if self._data is None:
            if self._path.exists():
                self._data = json.loads(self._path.read_text())
            else:
                self._data = {}
        return self._data

    async def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        data = self._load()
        words = set(re.findall(r"[a-z0-9]+", query.lower()))
        best: list[SearchResult] = []
        best_overlap = 0
        for key, entries in data.items():
            overlap = len(words & set(re.findall(r"[a-z0-9]+", key.lower())))
            if overlap > best_overlap:
                best_overlap = overlap
                best = [SearchResult(**entry) for entry in entries][:limit]
        return best


_PROVIDERS = {
    "duckduckgo": DuckDuckGoProvider,
    "tavily": TavilyProvider,
    "brave": BraveProvider,
    "fixture": FixtureProvider,
}


def get_provider(name: str | None = None):
    """Return the configured provider instance."""
    key = name or get_settings().search_provider
    try:
        return _PROVIDERS[key]()
    except KeyError:
        raise ValueError(
            f"Unknown search provider {key!r}. Options: {', '.join(sorted(_PROVIDERS))}"
        ) from None


def search_url(query: str) -> str:
    """A human-clickable search URL, so users can audit the automated verdict."""
    return f"https://duckduckgo.com/?q={quote_plus(query)}"
