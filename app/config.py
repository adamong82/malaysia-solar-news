"""Central configuration: env vars, sources, and relevance rules.

主题（topic）结构：每个主题两套来源与词表 —— en（英文）与 zh（中文）。
语言层结构：每套自带 Google News 查询、RSS 来源、相关性词表与展示信息。
新增主题只需在 TOPICS 里加一段，看板会出现对应的切换按钮。
All keyword matching is case-insensitive; ASCII terms are whole-word based,
CJK terms are matched as substrings (中文没有词边界).
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
# 支持的语言：en = 英文新闻，zh = 中文新闻（看板顶部切换）。
LANGUAGES = ["en", "zh"]
LANGUAGE_LABELS = {"en": "EN", "zh": "中文"}

# 每个主题的收集规则按语言分层：
#   TOPICS[topic][lang] = {queries, rss, geo_terms, topic_terms,
#                          bonus_terms, ignore_terms, require_geo}
# en 层：沿用「≥1 地理词 + ≥1 主题词」硬过滤（GEO∧TOPIC）。
# zh 层：查询本身已带马来西亚语境（或来自大马中文报 site: 过滤），
#        故 require_geo=False 只看主题词；geo_terms 仍用于打分与关键词展示。
TOPICS: dict[str, dict] = {
    "solar": {
        # ---- 展示信息（看板 / Telegram 推送用，界面文案保持英文）
        "name": "Malaysia Solar News",
        "label": "Solar",
        "icon": "☀️",
        "sub": "Malaysia solar industry · auto-collected policy / market / project news",
        "en": {
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
            # Direct RSS/Atom feeds (global trade press; relevance filter
            # below keeps only Malaysia-related items).
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
            "bonus_terms": [
                "quota", "tariff", "nem", "cgpp", "lss5", "lss4", "policy",
                "regulation", "tender", "bid", "tax", "duty", "import duty",
                "surplus", "ppa", "rooftop", "corporate green power", "scan",
                "initiative", "subsidy", "incentive", "target", "2050", "2035",
            ],
            "ignore_terms": [
                "solar eclipse", "solar system nasa", "horoscope", "astrology",
            ],
        },
        "zh": {
            # 查询全部用 AND 连接（Google 隐式 AND）——每篇命中文都必含
            # 「马来西亚」，避免 OR 低优先级把纯区域新闻带进来；大马中文报
            # 用 site: 过滤（其直接 RSS 已失效），文章是否相关交给主题词判断。
            "require_geo": False,
            "queries": [
                "马来西亚 太阳能",
                "马来西亚 光伏",
                "马来西亚 可再生能源",
                "马来西亚 屋顶太阳能",
                "马来西亚 净电能计量",
                "马来西亚 太阳能 政策",
                "site:sinchew.com.my",       # 星洲日报
                "site:chinapress.com.my",    # 中国报
            ],
            "rss": [],
            "geo_terms": [
                "马来西亚", "馬來西亞", "大马", "大馬", "我国", "我國", "马国", "馬國",
                "中马", "新马", "柔佛", "砂拉越", "沙拉越", "雪兰莪", "雪蘭莪",
                "彭亨", "槟城", "檳城", "沙巴", "吉隆坡", "布城", "赛城",
                "新山", "古晋", "安华", "拿督", "丹斯里", "令吉", "马币",
                "malaysia", "malaysian", "tnb", "tenaga", "seda", "国能", "petra", "pmx",
            ],
            "topic_terms": [
                "太阳能", "光伏", "可再生能源", "屋顶太阳能", "净电能计量",
                "储能", "太阳能板", "太阳能电站", "绿色电力",
                "solar", "photovoltaic", "pv", "renewable",
            ],
            "bonus_terms": [
                "政策", "补贴", "配额", "招标", "投资", "关税", "电价",
                "激励", "津贴", "目标", "2050", "2030", "tariff", "quota",
                "ppa", "nem",
            ],
            "ignore_terms": [
                "日食", "占星", "星座", "solar eclipse", "horoscope", "astrology",
            ],
        },
    },
    "ai": {
        # ---- 展示信息（看板 / Telegram 推送用，界面文案保持英文）
        "name": "Malaysia AI News",
        "label": "AI",
        "icon": "🤖",
        "sub": "Malaysia AI industry · auto-collected policy / investment / technology news",
        "en": {
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
        "zh": {
            "require_geo": False,
            "queries": [
                "马来西亚 人工智能",
                "马来西亚 AI",
                "马来西亚 数据中心",
                "马来西亚 资料中心",
                "马来西亚 大模型",
                "马来西亚 AI 投资",
                "马来西亚 AI 政策",
                "马来西亚 半导体",
                "柔佛 数据中心",
                "site:sinchew.com.my",       # 星洲日报
                "site:chinapress.com.my",    # 中国报
            ],
            "rss": [],
            "geo_terms": [
                "马来西亚", "馬來西亞", "大马", "大馬", "我国", "我國", "马国", "馬國",
                "中马", "新马", "柔佛", "砂拉越", "沙拉越", "雪兰莪", "雪蘭莪",
                "彭亨", "槟城", "檳城", "沙巴", "吉隆坡", "布城", "赛城",
                "新山", "古晋", "安华", "拿督", "丹斯里", "令吉", "马币",
                "malaysia", "malaysian", "tnb", "mcmc", "petra", "pmx",
            ],
            "topic_terms": [
                "人工智能", "大模型", "数据中心", "资料中心", "机器学习",
                "深度学习", "生成式", "智能体", "神经网络", "聊天机器人",
                "芯片", "半导体", "英伟达",
                "ai", "gpu", "nvidia", "openai", "chatgpt", "llm",
            ],
            "bonus_terms": [
                "政策", "监管", "版权", "伦理", "投资", "融资", "初创",
                "算力", "基础设施", "主权", "采用", "2030", "2050",
                "data centre", "data center", "policy",
            ],
            "ignore_terms": [
                "人工授精", "占星", "星座", "artificial insemination",
            ],
        },
    },
}

# 看板默认展示的主题与语言（迁移前的旧数据/旧快照都视为 solar + en）。
DEFAULT_TOPIC = "solar"
DEFAULT_LANGUAGE = "en"


def topic_keys() -> list[str]:
    return list(TOPICS)
