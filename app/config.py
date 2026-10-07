"""Central configuration: env vars, sources, and relevance rules.

Edit GOOGLE_NEWS_QUERIES / RSS_FEEDS / term lists to tune what the bot
collects. All keyword matching is case-insensitive, whole-word based.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# ---------------------------------------------------------------- paths
DATA_DIR = Path(os.getenv("DATA_DIR", str(ROOT / "data")))
DB_PATH = DATA_DIR / "news.db"
SNAPSHOT_PATH = DATA_DIR / "articles.json"
STATIC_DIR = ROOT / "static"
DOCS_DIR = ROOT / "docs"

# ---------------------------------------------------------------- env
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "").strip()
WEB_ACCESS_TOKEN = os.getenv("WEB_ACCESS_TOKEN", "").strip()

ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "1") == "1"
RUN_ON_START = os.getenv("RUN_ON_START", "0") == "1"
COLLECT_INTERVAL_MIN = int(os.getenv("COLLECT_INTERVAL_MIN", "60"))
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "25"))

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# ---------------------------------------------------------------- sources
# Google News RSS search — covers Malaysian outlets (The Star, Bernama,
# NST, Malay Mail, The Edge ...) without needing API keys.
GOOGLE_NEWS_QUERIES = [
    "Malaysia solar",
    "Malaysia solar policy OR regulation OR quota",
    "SEDA Malaysia solar OR renewable",
    "NETR Malaysia solar OR energy transition",
    '"large scale solar" Malaysia OR "LSS" quota',
    'Malaysia "net energy metering" OR "NEM" solar',
    '"Tenaga Nasional" solar OR tariff OR TNB',
    "Malaysia photovoltaic OR solar farm",
    "Malaysia solar investment OR factory OR export",
]

# Direct RSS/Atom feeds (global trade press; relevance filter below keeps
# only Malaysia-related items).
RSS_FEEDS = [
    ("https://www.pv-magazine.com/feed", "pv magazine"),
    ("https://www.solarpowerworldonline.com/feed/", "Solar Power World"),
    ("https://www.energy-storage.news/feed/", "Energy Storage News"),
    ("https://reneweconomy.com.au/feed/", "RenewEconomy"),
]

# ---------------------------------------------------------------- relevance
# An article is kept only if it matches >=1 GEO term AND >=1 TOPIC term.
GEO_TERMS = [
    "malaysia", "malaysian", "putrajaya", "tnb", "tenaga",
    "seda", "netr", "myrer", "lss", "suria", "myenergy",
    "suruhanjaya tenaga", "sarawak", "sabah", "peninsular malaysia",
]

TOPIC_TERMS = [
    "solar", "photovoltaic", "pv", "renewable", "renewables",
    "net energy metering", "energy transition", "feed-in tariff",
    "large-scale solar", "clean energy", "green electricity",
    "electricity", "energy storage", "solar farm", "rooftop",
]

# Bonus terms raise the ranking score (dashboard sorts by recency, but
# score is shown and can be used for "top stories" views).
BONUS_TERMS = [
    "quota", "tariff", "nem", "cgpp", "lss5", "lss4", "policy",
    "regulation", "tender", "bid", "tax", "duty", "import duty",
    "surplus", "ppa", "rooftop", "corporate green power", "scan",
    "initiative", "subsidy", "incentive", "target", "2050", "2035",
]

# Hard exclusions (drop regardless of score).
IGNORE_TERMS = [
    "solar eclipse", "solar system nasa", "horoscope", "astrology",
]
