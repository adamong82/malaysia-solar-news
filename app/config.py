"""Central configuration: env vars, sources, and relevance rules.

主题（topic）结构：每个主题自带 Google News 查询、RSS 来源、相关性词表与
展示信息。新增主题只需在 TOPICS 里加一段，看板会出现对应的切换按钮。
All keyword matching is case-insensitive, whole-word based.
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

# ---------------------------------------------------------------- topics
# An article of a topic is kept only if it matches >=1 GEO term AND
# >=1 TOPIC term (require_geo=False 时只要求 TOPIC 命中)。
TOPICS: dict[str, dict] = {
    "solar": {
        # ---- 展示信息（看板 / Telegram 推送用）
        "name": "Malaysia Solar News",
        "label": "Solar 太阳能",
        "icon": "☀️",
        "sub": "马来西亚太阳能产业 · 政策 / 市场 / 项目新闻自动收集",
        # ---- 相关性规则
        "require_geo": True,
        # Google News RSS search — covers Malaysian outlets (The Star,
        # Bernama, NST, Malay Mail, The Edge ...) without needing API keys.
        "queries": [
            "Malaysia solar",
            "Malaysia solar policy OR regulation OR quota",
            "SEDA Malaysia solar OR renewable",
            "NETR Malaysia solar OR energy transition",
            '"large scale solar" Malaysia OR "LSS" quota',
            'Malaysia "net energy metering" OR "NEM" solar',
            '"Tenaga Nasional" solar OR tariff OR TNB',
            "Malaysia photovoltaic OR solar farm",
            "Malaysia solar investment OR factory OR export",
        ],
        # Direct RSS/Atom feeds (global trade press; relevance filter below
        # keeps only Malaysia-related items).
        "rss": [
            ("https://www.pv-magazine.com/feed", "pv magazine"),
            ("https://www.solarpowerworldonline.com/feed/", "Solar Power World"),
            ("https://www.energy-storage.news/feed/", "Energy Storage News"),
            ("https://reneweconomy.com.au/feed/", "RenewEconomy"),
        ],
        "geo_terms": [
            "malaysia", "malaysian", "putrajaya", "tnb", "tenaga",
            "seda", "netr", "myrer", "lss", "suria", "myenergy",
            "suruhanjaya tenaga", "sarawak", "sabah", "peninsular malaysia",
        ],
        "topic_terms": [
            "solar", "photovoltaic", "pv", "renewable", "renewables",
            "net energy metering", "energy transition", "feed-in tariff",
            "large-scale solar", "clean energy", "green electricity",
            "electricity", "energy storage", "solar farm", "rooftop",
        ],
        # Bonus terms raise the ranking score (dashboard sorts by recency,
        # but score is shown and can be used for "top stories" views).
        "bonus_terms": [
            "quota", "tariff", "nem", "cgpp", "lss5", "lss4", "policy",
            "regulation", "tender", "bid", "tax", "duty", "import duty",
            "surplus", "ppa", "rooftop", "corporate green power", "scan",
            "initiative", "subsidy", "incentive", "target", "2050", "2035",
        ],
        # Hard exclusions (drop regardless of score).
        "ignore_terms": [
            "solar eclipse", "solar system nasa", "horoscope", "astrology",
        ],
    },
    "ai": {
        # ---- 展示信息（看板 / Telegram 推送用）
        "name": "Malaysia AI News",
        "label": "AI 人工智能",
        "icon": "🤖",
        "sub": "马来西亚 AI 产业 · 政策 / 投资 / 技术新闻自动收集",
        # ---- 相关性规则
        # Google News 查询已自带马来西亚语境；国际 AI RSS 也按
        # GEO∧TOPIC 过滤，只留与马来西亚相关的条目。
        "require_geo": True,
        "queries": [
            "Malaysia AI",
            'Malaysia "artificial intelligence" OR "generative AI"',
            'Malaysia "AI policy" OR "AI roadmap" OR "national AI"',
            'MyDIGITAL Malaysia AI OR "data centre" OR "data center"',
            'Malaysia "machine learning" OR "large language model"',
            "Malaysia AI startup OR investment OR funding",
            'Malaysia "AI regulation" OR "AI ethics" OR trust',
            'Malaysia Nvidia OR GPU OR "AI chip" OR semiconductor',
            'Johor Malaysia "data centre" OR AI OR cloud',
            'Sarawak Malaysia AI OR data centre OR "digital economy"',
        ],
        "rss": [
            ("https://techcrunch.com/category/artificial-intelligence/feed/", "TechCrunch AI"),
            ("https://venturebeat.com/category/ai/feed/", "VentureBeat AI"),
            ("https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "The Verge AI"),
            ("https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss", "IEEE Spectrum AI"),
            ("https://blog.google/technology/ai/rss/", "Google AI Blog"),
        ],
        "geo_terms": [
            "malaysia", "malaysian", "putrajaya", "mydigital", "mcmc",
            "mosti", "johor", "sarawak", "sabah", "peninsular malaysia",
            "kuala lumpur", "cyberjaya",
        ],
        "topic_terms": [
            "ai", "artificial intelligence", "generative ai", "genai",
            "machine learning", "deep learning", "large language model",
            "llm", "chatgpt", "openai", "gemini", "copilot", "nvidia",
            "gpu", "data centre", "data center", "neural network",
            "computer vision", "foundation model", "agi", "anthropic",
            "deepseek", "inference", "ai model", "ai chip",
        ],
        "bonus_terms": [
            "policy", "regulation", "ethics", "funding", "investment",
            "startup", "sovereign", "compute", "cloud", "semiconductor",
            "roadmap", "talent", "innovation", "ministry", "initiative",
            "infrastructure", "supercomputer", "ranking", "adoption",
            "2030", "2050",
        ],
        "ignore_terms": [
            "artificial insemination", "horoscope", "astrology",
        ],
    },
}

# 看板默认展示的主题（迁移前的旧数据/旧快照都视为 solar）。
DEFAULT_TOPIC = "solar"


def topic_keys() -> list[str]:
    return list(TOPICS)
