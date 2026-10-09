"""Collectors: Google News RSS search + direct RSS feeds, with relevance
scoring (>=1 GEO term AND >=1 TOPIC term for en; topic term only for zh).
Matching is case-insensitive; ASCII terms are whole-word based, CJK terms
are matched as substrings (中文没有词边界)."""
from __future__ import annotations

import calendar
import html
import logging
import re
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Optional
from urllib.parse import quote
from urllib.parse import urlparse

import feedparser
import httpx

from . import config

log = logging.getLogger("collector")

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _clean(text: str, limit: int = 500) -> str:
    text = html.unescape(_TAG_RE.sub(" ", text or ""))
    return _WS_RE.sub(" ", text).strip()[:limit]


def _entry_time(entry: Any) -> Optional[str]:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            ts = calendar.timegm(t)
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")
    return None


def _entry_source(entry: Any, fallback_url: str) -> str:
    src = entry.get("source")
    if isinstance(src, dict) and src.get("title"):
        return _clean(src["title"], 80)
    if src is not None and getattr(src, "get", None):
        title = src.get("title")
        if title:
            return _clean(title, 80)
    netloc = urlparse(fallback_url).netloc.replace("news.google.com", "")
    return netloc.lstrip("www.")


def _parse_feed(content: bytes, fallback_source: str = "") -> list[dict[str, Any]]:
    feed = feedparser.parse(content)
    items = []
    for e in feed.entries:
        title = _clean(e.get("title", ""), 300)
        url = (e.get("link") or "").strip()
        if not title:
            continue
        items.append({
            "title": title,
            "url": url,
            "source": fallback_source or _entry_source(e, url),
            "published_at": _entry_time(e),
            "summary": _clean(e.get("summary", "") or e.get("description", "")),
        })
    return items


def _fetch(url: str) -> Optional[bytes]:
    try:
        r = httpx.get(
            url,
            headers={"User-Agent": config.USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"},
            timeout=config.HTTP_TIMEOUT,
            follow_redirects=True,
        )
        r.raise_for_status()
        return r.content
    except Exception as exc:  # network / HTTP errors are logged, not fatal
        log.warning("fetch failed %s: %s", url, exc)
        return None


def collect_google_news(query: str, language: str = "en") -> list[dict[str, Any]]:
    if language == "zh":
        # 中文必须用 zh-CN/Hans 参数 —— zh-MY 会退化成英文源（已验证）。
        locale = "hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    else:
        locale = "hl=en-MY&gl=MY&ceid=MY:en"
    url = "https://news.google.com/rss/search?q=" + quote(query) + "&" + locale
    body = _fetch(url)
    if not body:
        return []
    items = _parse_feed(body)
    for it in items:
        it["summary"] = it["summary"] or query  # keep traceability of query
    return items


def collect_rss(feed_url: str, default_source: str) -> list[dict[str, Any]]:
    body = _fetch(feed_url)
    if not body:
        return []
    return _parse_feed(body, fallback_source=default_source)


# ---------------------------------------------------------------- scoring
def _find_terms(text: str, terms: list[str]) -> list[str]:
    return [t for t in terms if _term_re(t).search(text)]


_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


@lru_cache(maxsize=None)
def _term_re(term: str) -> "re.Pattern[str]":
    r"""Term matcher: ASCII terms keep whole-word boundaries (but only
    against ASCII alphanumerics, so 马来西亚AI still matches 'ai');
    CJK terms are matched as plain substrings because 中文没有词边界 ——
    a (?<!\w) lookbehind would never match next to another Chinese char."""
    if _CJK_RE.search(term):
        return re.compile(re.escape(term))
    return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(term) + r"(?![A-Za-z0-9_])")


def score_article(art: dict[str, Any], lang_cfg: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Return article with score/keywords attached, or None if irrelevant.
    Term lists come from the language layer of the topic config."""
    text = f"{art.get('title','')} {art.get('summary','')}".lower()
    if any(_term_re(t).search(text) for t in lang_cfg["ignore_terms"]):
        return None
    geo = _find_terms(text, lang_cfg["geo_terms"])
    top = _find_terms(text, lang_cfg["topic_terms"])
    if not top or (lang_cfg.get("require_geo", True) and not geo):
        return None
    bonus = _find_terms(text, lang_cfg["bonus_terms"])
    score = 3 * len(geo) + 2 * len(top) + len(bonus)
    art["score"] = score
    art["keywords"] = ",".join(dict.fromkeys(geo + top + bonus))
    return art


_CJK_TITLE_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def collect_all(topic: str, language: str = "en") -> tuple[list[dict[str, Any]], int]:
    """Run every configured source of one topic in one language.
    Returns (relevant articles, total seen)."""
    cfg = config.TOPICS[topic][language]
    seen: list[dict[str, Any]] = []
    for q in cfg["queries"]:
        items = collect_google_news(q, language)
        log.info("[%s/%s] google news %-45s -> %d", topic, language, q, len(items))
        seen.extend(items)
    for feed_url, name in cfg["rss"]:
        items = collect_rss(feed_url, name)
        log.info("[%s/%s] rss %-40s -> %d", topic, language, name, len(items))
        seen.extend(items)

    if language == "zh":
        # 中文模式只保留标题真正是中文的条目（Google News 偶尔会混入英文源）
        seen = [x for x in seen if _CJK_TITLE_RE.search(x.get("title", ""))]

    relevant = [a for a in (score_article(dict(x), cfg) for x in seen) if a]
    for a in relevant:
        a["language"] = language
    # in-run dedupe by exact title (same story via several queries)
    uniq: dict[str, dict[str, Any]] = {}
    for a in relevant:
        key = a["title"].strip().lower()
        if key not in uniq or a.get("score", 0) > uniq[key].get("score", 0):
            uniq[key] = a
    return list(uniq.values()), len(seen)
