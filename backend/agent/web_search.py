#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Web Search Engine | محرك البحث على الويب
============================================================
Dedicated search engine the Wolf uses to fetch what it needs or what
the user asks it to fetch (Iron Law #47: bilingual).

محرك بحث مخصص يستخدمه الذئب لجلب ما يحتاجه من معلومات أو ما نطلب منه جلبه.

Capabilities:
- search(query, max_results, lang) — multi-provider web search with
  graceful degradation (Iron Law #41)
- fetch_page(url, max_chars) — download a page and extract readable text
  (this is the "جلب/jلب" part: retrieve full content, not just snippets)
- TTL cache (1h, 200 entries) to avoid hammering engines

Provider order (no API key needed for 1-4):
1. Tavily / Brave / SerpAPI — only if env keys present (professional grade)
2. Google News RSS — no key, AR-best (100+ Arabic results verified 2026-09-26)
3. DuckDuckGo Lite (often anti-bot walled: anomaly-modal — EN chain only)
5. Bing RSS (no key, bot-wall resistant — VERIFIED 2026-09-26)
6. Wikipedia API, locale-aware (en/ar)

Language-aware chain (Phase 42):
- Arabic: google-news-rss → bing-rss → wikipedia
- English: bing-rss → duckduckgo-lite → google-news-rss → wikipedia
DuckDuckGo HTML excluded (100% blocked — anomaly-modal).

Arabic: queries containing Arabic script automatically use mkt=ar-SA
for Bing, ar.wikipedia.org for Wikipedia, and EG:ar locale for Google News.

Env (optional, all empty = keyless mode still works):
    TAVILY_API_KEY, BRAVE_SEARCH_API_KEY, SERPAPI_API_KEY

Iron Laws Applied:
- #15 (Verify)     : self_test() in __main__
- #22 (Autonomous) : no prompts — execute immediately
- #33 (Lessons)    : bilingual docstrings (Iron Law #47)
- #41 (Conflict)   : every failure surfaces with provider + reason;
                      result always states its `source` (provenance)
- #47 (Bilingual)  : every public function has Arabic translation
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
BOT_AGENT = "AlphaWolfAgent/0.1 (web-search-engine)"

ARABIC_RE = re.compile(r"[\u0600-\u06FF]")

CACHE_TTL_SEC = 3600
CACHE_MAX_ENTRIES = 200
_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}


# ============================================================================
# Data model
# ============================================================================

@dataclass
class SearchResult:
    """Single web result with provenance.

    نتيجة ويب واحدة مع المصدر.
    """
    title: str
    url: str
    snippet: str = ""
    source: str = ""   # provider name: bing-rss | duckduckgo | wikipedia ...
    lang: str = "en"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# Helpers
# ============================================================================

def detect_lang(query: str, lang: str = "auto") -> str:
    """Detect query language (ar/en). Explicit lang always wins.

    كشف لغة الاستعلام (عربي/إنجليزي).
    """
    if lang in ("ar", "en"):
        return lang
    return "ar" if ARABIC_RE.search(query or "") else "en"


def detect_search_language(query: str) -> str:
    """Detect if query is primarily Arabic or English (30% threshold).

    كشف لغة الاستعلام بهامش 30% — أكثر تحفظاً من detect_lang.

    Returns "ar" if Arabic chars >= 30% of alpha chars, else "en".
    Used for choosing provider chain (Google News RSS for AR-first).
    """
    if not query:
        return "en"
    arabic_chars = sum(1 for c in query if '\u0600' <= c <= '\u06FF')
    total_alpha = sum(1 for c in query if c.isalpha())
    if total_alpha == 0:
        return "en"
    return "ar" if (arabic_chars / total_alpha) > 0.3 else "en"


def _http_get(url: str, timeout: int = 15, accept: str = "text/html,application/xhtml+xml") -> str:
    """GET a URL and return decoded text."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": accept, "Accept-Language": "en-US,en;q=0.9"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _strip_tags(html: str, limit: int = 300) -> str:
    """Strip HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    hit = _cache.get(key)
    if hit and (time.time() - hit[0]) < CACHE_TTL_SEC:
        return hit[1]
    _cache.pop(key, None)
    return None


def _cache_put(key: str, value: Dict[str, Any]) -> None:
    if len(_cache) >= CACHE_MAX_ENTRIES:
        oldest = min(_cache.items(), key=lambda kv: kv[1][0])[0]
        _cache.pop(oldest, None)
    _cache[key] = (time.time(), value)


# ============================================================================
# Providers (no key)
# ============================================================================

def _ddg_search(query: str, max_results: int, lite: bool = False) -> List[Dict[str, Any]]:
    """DuckDuckGo HTML/Lite scrape. Returns [] when anti-bot walled.

    Note (Phase 42): DDG HTML mode is excluded from main chain (always blocked).
    Lite mode is used for English fallback; Arabic queries skip this provider.
    """
    encoded = urllib.parse.quote_plus(query)
    url = (
        f"https://lite.duckduckgo.com/lite/?q={encoded}"
        if lite
        else f"https://html.duckduckgo.com/html/?q={encoded}"
    )
    html = _http_get(url)
    # Enhanced blocker detection (Phase 42): check more anti-bot signals.
    html_lower = html.lower()
    if (
        "anomaly-modal" in html
        or "captcha" in html_lower
        or "robot" in html_lower
        or len(html) < 5000
    ):
        print(f"[WebSearch] ddg({'lite' if lite else 'html'}) blocked (len={len(html)})")
        return []  # anti-bot wall — let the next provider try

    if lite:
        link_pat = re.compile(r'<a[^>]+class="result-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
        snip_pat = re.compile(r'<td[^>]*class="result-snippet"[^>]*>(.*?)</td>', re.DOTALL)
    else:
        link_pat = re.compile(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
        snip_pat = re.compile(r'class="result__snippet"[^>]*>(.*?)</(?:td|a|div)', re.DOTALL)

    out: List[Dict[str, Any]] = []
    for m in link_pat.finditer(html):
        if len(out) >= max_results:
            break
        link, title_raw = m.group(1), m.group(2)
        title = _strip_tags(title_raw, 200)
        snip_m = snip_pat.search(html, m.end())
        snippet = _strip_tags(snip_m.group(1), 300) if snip_m else ""
        if title and link.startswith("http"):
            out.append({"title": title, "url": link, "snippet": snippet})
    return out


def _bing_rss_search(query: str, max_results: int, lang: str = "en") -> List[Dict[str, Any]]:
    """Bing RSS (no key, bot-wall resistant). VERIFIED 2026-09-26."""
    import xml.etree.ElementTree as ET

    mkt = "ar-SA" if lang == "ar" else "en-US"
    url = f"https://www.bing.com/search?format=rss&q={urllib.parse.quote_plus(query)}&mkt={mkt}"
    data = _http_get(url, accept="application/rss+xml")
    root = ET.fromstring(data)
    out: List[Dict[str, Any]] = []
    for item in root.iter("item"):
        if len(out) >= max_results:
            break
        title = (item.findtext("title") or "").strip()[:200]
        link = (item.findtext("link") or "").strip()
        snippet = _strip_tags(item.findtext("description") or "", 300)
        if title and link.startswith("http"):
            out.append({"title": title, "url": link, "snippet": snippet})
    return out


def _wikipedia_search(query: str, max_results: int, lang: str = "en") -> List[Dict[str, Any]]:
    """Wikipedia API (encyclopedic fallback, locale-aware)."""
    host = "ar.wikipedia.org" if lang == "ar" else "en.wikipedia.org"
    url = (
        f"https://{host}/w/api.php?action=query&list=search"
        f"&srsearch={urllib.parse.quote_plus(query)}&format=json&srlimit={max_results}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": BOT_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    out: List[Dict[str, Any]] = []
    for hit in data.get("query", {}).get("search", []):
        title = hit.get("title", "")
        slug = urllib.parse.quote(title.replace(" ", "_"))
        out.append({
            "title": title,
            "url": f"https://{host}/wiki/{slug}",
            "snippet": _strip_tags(hit.get("snippet", ""), 300),
        })
    return out


def _google_news_search(query: str, max_results: int, lang: str = "en") -> List[Dict[str, Any]]:
    """Google News RSS (no API key required, excellent for news queries).

    بحث أخبار Google عبر RSS — لا يحتاج API key.
    Best for: news queries, especially Arabic (100+ results verified 2026-09-26).
    Locale-aware: ar → Egypt/Arabic, en → US/English, fr → France/French.

    Returns empty list on any failure (anti-bot wall, network error, XML parse).
    """
    import xml.etree.ElementTree as ET

    locale_map = {
        "ar": ("news.google.com", "ar", "EG", "EG:ar"),
        "en": ("news.google.com", "en-US", "US", "US:en"),
        "fr": ("news.google.com", "fr", "FR", "FR:fr"),
    }
    host, hl, gl, ceid = locale_map.get(lang, locale_map["en"])
    url = (
        f"https://{host}/rss/search?q={urllib.parse.quote_plus(query)}"
        f"&hl={hl}&gl={gl}&ceid={ceid}"
    )

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
                "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            content = resp.read()
        # Short response = likely blocked or no results
        if len(content) < 500:
            print(f"[WebSearch] google-news-rss returned short body ({len(content)} bytes)")
            return []

        root = ET.fromstring(content)
        out: List[Dict[str, Any]] = []
        for item in root.findall(".//item"):
            if len(out) >= max_results:
                break
            title = (item.findtext("title") or "").strip()[:200]
            link = (item.findtext("link") or "").strip()
            description = item.findtext("description") or ""
            pub_date = (item.findtext("pubDate") or "").strip()
            source_el = item.find("source")
            source_name = (
                (source_el.text or "").strip() if source_el is not None and source_el.text
                else "google-news"
            )

            # Clean HTML from description for snippet
            snippet = _strip_tags(description, 300)

            if title and link.startswith("http"):
                out.append({
                    "title": title,
                    "url": link,
                    "snippet": snippet,
                    "source": source_name,
                    "published": pub_date,
                    "engine": "google-news-rss",
                })
        return out
    except Exception as e:
        print(f"[WebSearch] google-news-rss failed: {type(e).__name__}: {e}")
        return []


# ============================================================================
# Providers (API key — used only when env keys exist)
# ============================================================================

def _tavily_search(query: str, max_results: int) -> List[Dict[str, Any]]:
    """Tavily (professional grade, needs TAVILY_API_KEY)."""
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("TAVILY_API_KEY not set")
    payload = json.dumps({
        "api_key": key, "query": query, "max_results": max_results,
        "include_answer": False, "search_depth": "basic",
    }).encode()
    req = urllib.request.Request(
        "https://api.tavily.com/search", data=payload,
        headers={"Content-Type": "application/json", "User-Agent": BOT_AGENT},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [
        {"title": (r.get("title") or "")[:200], "url": r.get("url", ""),
         "snippet": (r.get("content") or "")[:300]}
        for r in data.get("results", []) if r.get("url")
    ][:max_results]


def _brave_search(query: str, max_results: int) -> List[Dict[str, Any]]:
    """Brave Search API (needs BRAVE_SEARCH_API_KEY)."""
    key = os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    if not key:
        raise RuntimeError("BRAVE_SEARCH_API_KEY not set")
    url = f"https://api.search.brave.com/res/v1/web/search?q={urllib.parse.quote_plus(query)}&count={max_results}"
    req = urllib.request.Request(url, headers={"X-Subscription-Token": key, "User-Agent": BOT_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [
        {"title": (r.get("title") or "")[:200], "url": r.get("url", ""),
         "snippet": (r.get("description") or "")[:300]}
        for r in (data.get("web") or {}).get("results", []) if r.get("url")
    ][:max_results]


def _serpapi_search(query: str, max_results: int) -> List[Dict[str, Any]]:
    """SerpAPI Google engine (needs SERPAPI_API_KEY)."""
    key = os.environ.get("SERPAPI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("SERPAPI_API_KEY not set")
    url = (f"https://serpapi.com/search.json?engine=google&q={urllib.parse.quote_plus(query)}"
           f"&num={max_results}&api_key={key}")
    req = urllib.request.Request(url, headers={"User-Agent": BOT_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [
        {"title": (r.get("title") or "")[:200], "url": r.get("link", ""),
         "snippet": (r.get("snippet") or "")[:300]}
        for r in data.get("organic_results", []) if r.get("link")
    ][:max_results]


# ============================================================================
# Public API
# ============================================================================

def search(query: str, max_results: int = 5, lang: Optional[str] = "auto") -> Dict[str, Any]:
    """Search the web across providers with graceful degradation.

    البحث على الويب عبر عدة موفرين بتدهور متدرج.

    Returns dict: success, query, lang, results[{title,url,snippet}],
    count, source (provider that answered), errors[{provider, error}].
    Results are cached for 1h (same query+lang+count).

    Provider chain (Phase 42, language-aware, no API key):
    - Arabic: google-news-rss → bing-rss → wikipedia
    - English: bing-rss → duckduckgo-lite → google-news-rss → wikipedia
    - Optional paid providers (Tavily/Brave/SerpAPI) used first if env keys exist.
    - DuckDuckGo HTML is excluded (always blocked — anomaly-modal 100%).
    """
    query = (query or "").strip()
    if not query:
        return {"success": False, "query": query, "results": [], "count": 0,
                "source": None, "error": "Empty query | استعلام فارغ"}

    # Resolve language: explicit "ar"/"en" wins, "auto"/None → detect.
    if lang is None or lang == "auto":
        lang = detect_search_language(query)
    elif lang not in ("ar", "en"):
        lang = detect_search_language(query)

    max_results = max(1, min(int(max_results or 5), 20))
    cache_key = f"{lang}:{max_results}:{query}"
    hit = _cache_get(cache_key)
    if hit is not None:
        out = dict(hit)
        out["cached"] = True
        return out

    errors: List[Dict[str, str]] = []
    chain: List[Tuple[str, Any]] = []
    # Optional paid providers first (Iron Law #41: any working key used).
    if os.environ.get("TAVILY_API_KEY", "").strip():
        chain.append(("tavily", lambda: _tavily_search(query, max_results)))
    if os.environ.get("BRAVE_SEARCH_API_KEY", "").strip():
        chain.append(("brave", lambda: _brave_search(query, max_results)))
    if os.environ.get("SERPAPI_API_KEY", "").strip():
        chain.append(("serpapi", lambda: _serpapi_search(query, max_results)))

    # Language-aware fallback chain (Phase 42).
    if lang == "ar":
        chain += [
            ("google-news-rss", lambda: _google_news_search(query, max_results, lang="ar")),
            ("bing-rss", lambda: _bing_rss_search(query, max_results, lang)),
            ("wikipedia", lambda: _wikipedia_search(query, max_results, lang)),
        ]
    else:
        chain += [
            ("bing-rss", lambda: _bing_rss_search(query, max_results, lang)),
            ("duckduckgo-lite", lambda: _ddg_search(query, max_results, lite=True)),
            ("google-news-rss", lambda: _google_news_search(query, max_results, lang="en")),
            ("wikipedia", lambda: _wikipedia_search(query, max_results, lang)),
        ]

    for name, fn in chain:
        try:
            results = fn() or []
        except Exception as e:
            errors.append({"provider": name, "error": f"{type(e).__name__}: {e}"})
            continue
        if results:
            for r in results:
                r.setdefault("source", name)
                r.setdefault("lang", lang)
            out = {"success": True, "query": query, "lang": lang, "results": results,
                   "count": len(results), "source": name, "errors": errors, "cached": False}
            if name == "wikipedia":
                out["note"] = "Encyclopedic results only (web engines unreachable)"
            _cache_put(cache_key, out)
            return out
        errors.append({"provider": name, "error": "no results (blocked or empty)"})

    return {"success": False, "query": query, "lang": lang, "results": [], "count": 0,
            "source": None, "errors": errors,
            "hint": "All providers failed. Set TAVILY_API_KEY / BRAVE_SEARCH_API_KEY / SERPAPI_API_KEY."}


def fetch_page(url: str, max_chars: int = 8000) -> Dict[str, Any]:
    """Fetch a page and extract readable text (the retrieval/جلب step).

    جلب صفحة واستخراج نصها المقروء.

    Strips scripts/styles/nav, keeps title + headings + paragraphs.
    max_chars caps output (default 8000, hard cap 50000).
    """
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        return {"success": False, "url": url, "error": "URL must start with http(s) | الرابط يجب أن يبدأ بـ http"}
    max_chars = max(500, min(int(max_chars or 8000), 50000))

    try:
        html = _http_get(url, timeout=20)
    except Exception as e:
        return {"success": False, "url": url, "error": f"Download failed: {type(e).__name__}: {e}"}

    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    title = _strip_tags(title_m.group(1), 200) if title_m else ""
    # Drop non-content zones
    cleaned = re.sub(r"<(script|style|nav|header|footer|aside|noscript)[^>]*>.*?</\1>",
                     " ", html, flags=re.DOTALL | re.IGNORECASE)
    # Prefer article/main, else body
    for zone in ("article", "main"):
        m = re.search(rf"<{zone}[^>]*>(.*?)</{zone}>", cleaned, re.DOTALL | re.IGNORECASE)
        if m and len(m.group(1)) > 500:
            cleaned = m.group(1)
            break
    blocks: List[str] = []
    for tag in ("h1", "h2", "h3", "p", "li"):
        for m in re.finditer(rf"<{tag}[^>]*>(.*?)</{tag}>", cleaned, re.DOTALL | re.IGNORECASE):
            txt = _strip_tags(m.group(1), 2000)
            if len(txt) > 20:
                blocks.append(txt)
    text = "\n".join(blocks) or _strip_tags(cleaned, max_chars)
    truncated = len(text) > max_chars
    text = text[:max_chars]
    return {"success": True, "url": url, "title": title, "text": text,
            "chars": len(text), "truncated": truncated}


def self_test() -> bool:
    """Verify engine end-to-end (Iron Law #15).

    Tests (3 categories):
      1. Arabic: should return real news via google-news-rss (not just Wikipedia).
      2. English: should return real results via bing-rss/ddg/google-news.
      3. Edge cases: empty query rejected; language detection correct.
    """
    print("=" * 60)
    print("Running web_search engine self-tests (Phase 42 chain)...")
    print("=" * 60)
    passed = 0
    failed = 0

    # Test 1: Arabic news (was broken — only Wikipedia returned)
    print("\n[Test 1] AR news query: 'مايكروسوفت' (expect google-news-rss)")
    r = search("مايكروسوفت", max_results=5, lang="ar")
    print(f"  success={r['success']} source={r.get('source')} lang={r.get('lang')} count={r['count']}")
    if r.get("results"):
        print(f"  first title: {(r['results'][0].get('title') or '')[:80]}")
    if r["success"] and r["count"] >= 3 and r.get("source") != "wikipedia":
        print(f"  ✓ PASS — got {r['count']} Arabic news results (not just Wikipedia)")
        passed += 1
    else:
        print(f"  ✗ FAIL — got only {r['count']} results via {r.get('source')}")
        failed += 1

    # Test 2: English query
    print("\n[Test 2] EN query: 'Python 3.12 release'")
    r2 = search("Python 3.12 release", max_results=3, lang="en")
    print(f"  success={r2['success']} source={r2.get('source')} lang={r2.get('lang')} count={r2['count']}")
    if r2.get("results"):
        print(f"  first title: {(r2['results'][0].get('title') or '')[:80]}")
    if r2["success"] and r2["count"] >= 2:
        print(f"  ✓ PASS — got {r2['count']} English results via {r2.get('source')}")
        passed += 1
    else:
        print(f"  ✗ FAIL — got only {r2['count']} results via {r2.get('source')}")
        failed += 1

    # Test 3: Empty query edge case
    print("\n[Test 3] Empty query edge case")
    r3 = search("", max_results=5)
    if not r3["success"] and r3.get("error"):
        print(f"  ✓ PASS — empty query rejected: {r3['error'][:50]}")
        passed += 1
    else:
        print(f"  ✗ FAIL — empty query not rejected properly")
        failed += 1

    # Test 4: Auto-detect language (Arabic query without explicit lang)
    print("\n[Test 4] Auto-detect AR: 'أخبار الذكاء الاصطناعي' (lang=None → ar)")
    r4 = search("أخبار الذكاء الاصطناعي", max_results=3)
    print(f"  detected lang={r4.get('lang')} source={r4.get('source')} count={r4['count']}")
    if r4.get("lang") == "ar" and r4["success"]:
        print(f"  ✓ PASS — auto-detected Arabic, got {r4['count']} results")
        passed += 1
    else:
        print(f"  ✗ FAIL — lang={r4.get('lang')} (expected ar)")
        failed += 1

    # Test 5: Auto-detect English
    print("\n[Test 5] Auto-detect EN: 'latest AI news' (lang=None → en)")
    r5 = search("latest AI news", max_results=3)
    print(f"  detected lang={r5.get('lang')} source={r5.get('source')} count={r5['count']}")
    if r5.get("lang") == "en" and r5["success"]:
        print(f"  ✓ PASS — auto-detected English, got {r5['count']} results")
        passed += 1
    else:
        print(f"  ✗ FAIL — lang={r5.get('lang')} (expected en)")
        failed += 1

    # Test 6: Fetch page (smoke test, only if previous EN test succeeded)
    if r2["success"] and r2.get("results"):
        print("\n[Test 6] fetch_page on first EN result")
        f = fetch_page(r2["results"][0]["url"], max_chars=2000)
        print(f"  success={f['success']} chars={f.get('chars', 0)}")
        if f["success"] and f.get("chars", 0) > 100:
            print(f"  ✓ PASS — fetched {f['chars']} chars")
            passed += 1
        else:
            print(f"  ✗ FAIL — fetch failed or too short")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)
