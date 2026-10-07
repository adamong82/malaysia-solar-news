"""Collection pipeline — one full pass:
import snapshot → collect → score → dedupe/store → notify → export.

Run manually:      python -m app.pipeline
Run without push:  python -m app.pipeline --no-notify
Used by: local scheduler, GitHub Actions (hourly), cron.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback

from . import config, db
from .collectors import collect_all
from .notify import notify_new

log = logging.getLogger("pipeline")


def run_once(notify: bool = True, use_snapshot: bool = True) -> dict:
    started = db.now_iso()
    error = ""
    created: list[dict] = []
    seen = 0
    notified = 0
    try:
        if use_snapshot:
            restored = db.import_snapshot()
            if restored:
                log.info("restored %d articles from snapshot", restored)
        articles, seen = collect_all()
        conn = db.get_conn()
        for a in articles:
            if db.insert_article(conn, a):
                created.append(a)
        conn.commit()
        log.info("seen=%d relevant=%d new=%d", seen, len(articles), len(created))
        if created and notify:
            created.sort(key=lambda x: x.get("published_at") or "", reverse=True)
            notified = notify_new(created)
        db.export_snapshot()
    except Exception as exc:
        error = f"{exc}"
        log.error("pipeline failed: %s\n%s", exc, traceback.format_exc())
    finally:
        db.record_run(started, seen, len(created), notified, error)
    return {"new": len(created), "seen": seen, "notified": notified, "error": error}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one collection pass")
    parser.add_argument("--no-notify", action="store_true", help="skip Telegram push")
    parser.add_argument("--no-snapshot", action="store_true", help="skip snapshot import")
    parser.add_argument("--json", action="store_true", help="print result as JSON")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    result = run_once(notify=not args.no_notify, use_snapshot=not args.no_snapshot)
    if args.json:
        print(json.dumps(result))
    else:
        print(f"done: {result}")
    return 1 if result["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
