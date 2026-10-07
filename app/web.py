"""FastAPI app: dashboard UI + JSON API + webhook ingest + hourly scheduler.

    uvicorn app.web:app --port 8000
"""
from __future__ import annotations

import json
import logging
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from . import config, db
from .notify import notify_new
from .pipeline import run_once
from .scheduler import loop as scheduler_loop

log = logging.getLogger("web")


def _start_scheduler() -> None:
    def _runner():
        scheduler_loop(run_immediately=config.RUN_ON_START)

    t = threading.Thread(target=_runner, name="scheduler", daemon=True)
    t.start()
    log.info("hourly scheduler thread started (interval=%dmin)", config.COLLECT_INTERVAL_MIN)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    db.get_conn()  # create schema early
    if config.ENABLE_SCHEDULER:
        _start_scheduler()
    yield


app = FastAPI(title="Malaysia Solar News Collector", lifespan=lifespan)

# ------------------------------------------------------------------ security
# 1) WEB_ACCESS_TOKEN —— 保护看板和 API（设置后必须带密钥才能访问）
#    浏览器首次访问 /?key=<token> 会种下 cookie，之后无需重复带。
# 2) WEBHOOK_TOKEN    —— 保护 POST /webhook（由 endpoint 本身校验）
# 3) webhook 限流     —— 每 IP 每小时最多 60 次，防滥用
_webhook_window: dict[str, list[float]] = {}


@app.middleware("http")
async def access_guard(request: Request, call_next):
    path = request.url.path

    # webhook 已有自己的 token 时从看板鉴权中豁免（由 endpoint 校验）；
    # 否则也必须过看板鉴权，不给匿名入口留洞。
    webhook_self_protected = path == "/webhook" and bool(config.WEBHOOK_TOKEN)

    if config.WEB_ACCESS_TOKEN and not webhook_self_protected:
        given = (
            request.headers.get("x-access-token")
            or request.query_params.get("key")
            or request.cookies.get("access_key")
        )
        if given != config.WEB_ACCESS_TOKEN:
            if "text/html" in request.headers.get("accept", ""):
                return HTMLResponse(
                    "<meta charset='utf-8'><h1>401 · 需要访问密钥</h1>"
                    "<p>请访问 <code>/?key=你的 WEB_ACCESS_TOKEN</code></p>",
                    status_code=401,
                )
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
        response = await call_next(request)
        if request.query_params.get("key"):  # 首次带 key 访问 → 种 cookie
            response.set_cookie(
                "access_key", config.WEB_ACCESS_TOKEN,
                httponly=True, samesite="lax", max_age=30 * 86400,
            )
        return response

    if path == "/webhook" and request.method == "POST":
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        hits = _webhook_window.setdefault(ip, [])
        hits[:] = [t for t in hits if now - t < 3600]
        if len(hits) >= 60:
            return JSONResponse({"detail": "rate limited, max 60/hour"}, status_code=429)
        hits.append(now)
        if len(_webhook_window) > 500:  # 防内存缓慢增长
            _webhook_window.clear()

    return await call_next(request)


# ------------------------------------------------------------------ UI
@app.get("/")
async def index():
    path = config.STATIC_DIR / "index.html"
    if not path.exists():
        raise HTTPException(404, "index.html not found")
    return FileResponse(path)


@app.get("/articles.json")
async def articles_json():
    """Snapshot for static hosting (GitHub Pages) and the UI fallback."""
    if not config.SNAPSHOT_PATH.exists():
        return JSONResponse({"generated_at": None, "articles": []})
    return JSONResponse(json.loads(config.SNAPSHOT_PATH.read_text(encoding="utf-8")))


# ------------------------------------------------------------------ API
@app.get("/api/articles")
async def api_articles(
    search: str = "",
    source: str = "",
    unread: bool = False,
    limit: int = 200,
    offset: int = 0,
):
    return {
        "articles": db.list_articles(
            search=search, source=source, unread_only=unread,
            limit=min(limit, 500), offset=max(offset, 0),
        )
    }


@app.get("/api/stats")
async def api_stats():
    return db.stats()


@app.post("/api/read")
async def api_read(request: Request):
    body = await request.json()
    if body.get("all"):
        n = db.mark_read(None)
    else:
        n = db.mark_read([int(i) for i in body.get("ids", [])])
    return {"marked": n}


@app.post("/api/refresh")
async def api_refresh():
    """Manual 'collect now' — runs in the background and returns at once."""
    def _run():
        try:
            run_once()
        except Exception as exc:
            log.error("manual refresh failed: %s", exc)

    threading.Thread(target=_run, name="manual-refresh", daemon=True).start()
    return {"started": True}


# ------------------------------------------------------------------ webhook
def _normalize(item: dict[str, Any]) -> Optional[dict[str, Any]]:
    title = (item.get("title") or item.get("name") or "").strip()
    if not title:
        return None
    return {
        "title": title,
        "url": (item.get("url") or item.get("link") or "").strip(),
        "source": (item.get("source") or item.get("site") or "webhook").strip(),
        "summary": (item.get("summary") or item.get("content") or item.get("text") or "")[:500],
        "published_at": item.get("published_at") or item.get("time"),
        "collected_at": db.now_iso(),
    }


@app.post("/webhook")
async def webhook(request: Request):
    """Ingest items from any external tool (n8n, changedetection.io, Zapier,
    a scraper of your own ...). Auth via X-Webhook-Token header when
    WEBHOOK_TOKEN is set. Accepts a single object or a list."""
    if config.WEBHOOK_TOKEN:
        if request.headers.get("x-webhook-token") != config.WEBHOOK_TOKEN:
            raise HTTPException(401, "invalid webhook token")
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(400, "body must be JSON")
    items = payload if isinstance(payload, list) else [payload]

    conn = db.get_conn()
    created, skipped = [], 0
    for raw in items:
        if not isinstance(raw, dict):
            skipped += 1
            continue
        art = _normalize(raw)
        if not art:
            skipped += 1
            continue
        if db.insert_article(conn, art):
            created.append(art)
        else:
            skipped += 1
    conn.commit()
    notified = notify_new(created) if created else 0
    db.export_snapshot()
    return {"created": len(created), "skipped": skipped, "notified": notified}
