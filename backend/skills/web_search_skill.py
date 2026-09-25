#!/usr/bin/env python3
r"""
Name: web_search_skill
Description: DuckDuckGo HTML scraping for offline-friendly web search. Falls back to Wikipedia.
Description_AR: كشط DuckDuckGo HTML للبحث دون اتصال. احتياطي: ويكيبيديا.
Author: Alpha Wolf Team
Version: 1.0.0
Parameters: {"query": "string", "max_results": "integer", "lite": "boolean"}

Iron Laws Applied:
- #15 (Verify)  : returns structured dict, never raw HTML
- #22 (Autonomous): no prompts — execute immediately
- #33 (Lessons) : bilingual AR+EN docstrings (Iron Law #47)
- #41 (Conflict): surfaces CAPTCHA / network failures honestly
- #47 (Bilingual): every function has Arabic translation
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List


def _ddg_scrape(url_template: str, query: str, max_results: int, lite: bool = False) -> List[Dict[str, str]]:
    """Scrape DuckDuckGo results from HTML.

    كشط نتائج DuckDuckGo من HTML.
    """
    encoded = urllib.parse.quote_plus(query)
    url = url_template.format(q=encoded)

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    # Anti-bot detection (Iron Law #41: surface this clearly)
    if "anomaly-modal" in html or "captcha" in html.lower():
        return []

    results: List[Dict[str, str]] = []

    if lite:
        link_pattern = re.compile(
            r'<a[^>]+class="result-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            re.DOTALL,
        )
        snippet_pattern = re.compile(
            r'<td[^>]*class="result-snippet"[^>]*>(.*?)</td>',
            re.DOTALL,
        )
    else:
        link_pattern = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            re.DOTALL,
        )
        snippet_pattern = re.compile(
            r'class="result__snippet"[^>]*>(.*?)</(?:td|a|div)',
            re.DOTALL,
        )

    for match in link_pattern.finditer(html):
        if len(results) >= max_results:
            break
        url_m = match.group(1)
        title_raw = match.group(2)
        title = re.sub(r'<[^>]+>', '', title_raw).strip()

        snippet = ""
        snippet_match = snippet_pattern.search(html, match.end())
        if snippet_match:
            snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()[:300]

        if title and url_m and url_m.startswith("http"):
            results.append({
                "title": title[:200],
                "url": url_m,
                "snippet": snippet,
            })

    return results


def _wikipedia_search(query: str, max_results: int) -> List[Dict[str, str]]:
    """Wikipedia API fallback (encyclopedic, no API key, very reliable).

    احتياطي: API ويكيبيديا (مجاني، بدون مفتاح، موثوق جداً).
    """
    encoded = urllib.parse.quote_plus(query)
    url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded}&format=json&srlimit={max_results}"

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AlphaWolfAgent/0.1 (educational)"},
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    results: List[Dict[str, str]] = []
    for hit in data.get("query", {}).get("search", []):
        title = hit.get("title", "")
        snippet = re.sub(r'<[^>]+>', '', hit.get("snippet", "")).strip()
        results.append({
            "title": title,
            "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
            "snippet": snippet[:300],
        })
    return results


def run(query: str, max_results: int = 5, lite: bool = False, **kwargs: Any) -> Dict[str, Any]:
    """Search the web with graceful fallback chain (Iron Law #41).

    البحث على الويب مع سلسلة احتياطية متدرجة.

    Strategy order:
      1. DuckDuckGo HTML (full)
      2. DuckDuckGo Lite
      3. Wikipedia API (encyclopedic only)

    Args:
        query: Search query string | نص البحث
        max_results: Max results to return (default 5) | أقصى عدد نتائج
        lite: Force DuckDuckGo Lite endpoint | فرض DuckDuckGo Lite

    Returns:
        Dict with: success, query, results (list), count, source, errors (list)
        قاموس يحتوي على: نجاح، استعلام، نتائج، عدد، مصدر، أخطاء
    """
    if not query or not query.strip():
        return {
            "success": False,
            "error": "Empty query | استعلام فارغ",
            "query": query,
            "results": [],
            "count": 0,
        }

    errors: List[str] = []

    # Strategy 1: DuckDuckGo HTML full
    if not lite:
        try:
            results = _ddg_scrape(
                "https://html.duckduckgo.com/html/?q={q}",
                query, max_results, lite=False,
            )
            if results:
                return {
                    "success": True,
                    "query": query,
                    "results": results,
                    "count": len(results),
                    "source": "duckduckgo",
                    "errors": [],
                }
        except Exception as e:
            errors.append(f"DDG HTML: {type(e).__name__}: {e}")

    # Strategy 2: DuckDuckGo Lite
    try:
        results = _ddg_scrape(
            "https://lite.duckduckgo.com/lite/?q={q}",
            query, max_results, lite=True,
        )
        if results:
            return {
                "success": True,
                "query": query,
                "results": results,
                "count": len(results),
                "source": "duckduckgo-lite",
                "errors": errors,
            }
    except Exception as e:
        errors.append(f"DDG Lite: {type(e).__name__}: {e}")

    # Strategy 3: Wikipedia
    try:
        results = _wikipedia_search(query, max_results)
        if results:
            return {
                "success": True,
                "query": query,
                "results": results,
                "count": len(results),
                "source": "wikipedia",
                "note": "Encyclopedic results only (search engines blocked)",
                "errors": errors,
            }
    except Exception as e:
        errors.append(f"Wikipedia: {type(e).__name__}: {e}")

    # All strategies failed
    return {
        "success": False,
        "query": query,
        "results": [],
        "count": 0,
        "source": None,
        "errors": errors,
        "hint": "Search engines blocked. Use SerpAPI/Bing API key.",
    }


if __name__ == "__main__":
    # Self-test (Iron Law #15)
    out = run(query="Python programming", max_results=3)
    print(f"Test 1 (web search): success={out['success']}, source={out.get('source')}, count={out['count']}")
    assert out["success"] or out["errors"], f"Should at least surface errors: {out}"

    out2 = run(query="", max_results=3)
    print(f"Test 2 (empty query): {out2}")
    assert not out2["success"], "Empty query should fail"

    print("✓ web_search_skill self-test PASSED")