"""Bounded DuckDuckGo HTML research; returned web content remains untrusted."""
from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import quote, unquote

import requests

from config import ResearchConfig
from ollama_client import OllamaClient
from prompts import research_prompt


@dataclass(frozen=True)
class ResearchResult:
    title: str
    url: str
    snippet: str


def search_web(
    query: str,
    config: ResearchConfig,
    session: requests.Session | None = None,
) -> list[ResearchResult]:
    if not query.strip():
        return []
    client = session or requests.Session()
    response = client.get(
        "https://html.duckduckgo.com/html/?q=" + quote(query),
        headers={"User-Agent": "local-email-agent/1.0"},
        timeout=20,
    )
    response.raise_for_status()
    results: list[ResearchResult] = []
    pattern = re.compile(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'class="result__snippet"[^>]*>(.*?)</a?>',
        re.S,
    )
    for match in pattern.finditer(response.text):
        if len(results) >= config.max_results:
            break
        url = unquote(match.group(1))
        title = re.sub("<.*?>", "", match.group(2)).strip()
        snippet = re.sub("<.*?>", "", match.group(3)).strip()
        results.append(ResearchResult(title, url, snippet))
    return results


def conduct_research(query: str, config: ResearchConfig, ollama: OllamaClient) -> str:
    results = search_web(query, config)
    if not results:
        return "I could not find sufficient public search results for that question."
    source_text = "\n\n".join(
        f"Title: {item.title}\nURL: {item.url}\nSnippet: {item.snippet}" for item in results
    )
    return ollama.generate(research_prompt(query, source_text))
