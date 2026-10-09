"""Telegram push notifications (HTML cards). Gracefully no-ops when the
bot token / chat id are not configured yet."""
from __future__ import annotations

import html
import logging
import time
from typing import Any

import httpx

from . import config

log = logging.getLogger("notify")

API = "https://api.telegram.org/bot{token}/method"
MAX_MSG = 3500  # keep well under Telegram's 4096-char limit


def _api(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def send_telegram(text: str, retries: int = 2) -> bool:
    token, chat_id = config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        log.info("telegram not configured — skip push (%d chars)", len(text))
        return False
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
        "protect_content": False,
    }
    for attempt in range(retries + 1):
        try:
            r = httpx.post(_api(token, "sendMessage"), json=payload, timeout=20)
            if r.status_code == 200:
                return True
            # 429 backoff
            if r.status_code == 429:
                wait = r.json().get("parameters", {}).get("retry_after", 3)
                log.warning("telegram 429, sleep %ss", wait)
                time.sleep(wait)
                continue
            log.error("telegram error %s: %s", r.status_code, r.text[:300])
            return False
        except Exception as exc:
            log.error("telegram exception: %s", exc)
            time.sleep(1 + attempt)
    return False


def _stars(score: float) -> str:
    """Weighted score → 1..5 stars. 5→★, 6-7→★★, 8-9→★★★,
    10-11→★★★★, >=12→★★★★★ (weights unchanged, display only)."""
    if not score:
        return ""
    n = min(5, max(1, int((score - 3) / 2 + 0.5)))  # half-up rounding
    return "★" * n + "☆" * (5 - n)


def _card(a: dict[str, Any], icon: str = "☀️") -> str:
    title = html.escape(a.get("title", ""))
    link = a.get("url", "")
    source = html.escape(a.get("source", "") or "unknown")
    pub = (a.get("published_at") or a.get("collected_at") or "")[:16].replace("T", " ")
    head = f'🚨 <b>{title}</b>' if a.get("score", 0) >= 8 else f'{icon} <b>{title}</b>'
    stars = _stars(a.get("score", 0))
    meta = " · ".join(x for x in (source, pub, stars) if x)
    line = f"{head}\n<i>{meta}</i>"
    if link:
        line += f'\n<a href="{html.escape(link, quote=True)}">Read more →</a>'
    kws = a.get("keywords", "")
    if kws:
        line += "\n#" + " #".join(kws.split(",")[:6])
    return line


def notify_new(articles: list[dict[str, Any]], topic: str = "") -> int:
    """Push new articles to Telegram, batched into as few messages as
    possible. Returns number of articles included in a sent message.
    The message header/card emoji follow the topic display info."""
    if not articles:
        return 0
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        log.info("%d new articles, telegram not configured — not pushing", len(articles))
        return 0

    cfg = config.TOPICS.get(topic or config.DEFAULT_TOPIC,
                            config.TOPICS[config.DEFAULT_TOPIC])
    batches: list[str] = []
    header = f"{cfg['icon']} <b>{cfg['name']} · {len(articles)} new</b>\n"
    current = header
    for a in articles:
        card = _card(a, cfg["icon"]) + "\n\n"
        if len(current) + len(card) > MAX_MSG:
            batches.append(current)
            current = card
        else:
            current += card
    batches.append(current)

    sent = 0
    for b in batches:
        if send_telegram(b):
            sent += len(articles) // len(batches) or len(articles)
    return len(articles) if sent else 0
