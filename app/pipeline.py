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


def run_once(notify: bool = True, use_snapshot: bool = True,
             topic: str = "") -> dict:
    """One collection pass. topic='' runs every topic in config.TOPICS;
    topic='ai' runs only that topic. Each topic is collected, stored and
    recorded as its own run so the dashboard shows per-topic last-run."""
    topics = [topic] if topic else config.topic_keys()
    totals = {"new": 0, "seen": 0, "notified": 0}
    errors: list[str] = []

    if use_snapshot:
        try:
            restored = db.import_snapshot()
            if restored:
                log.info("restored %d articles from snapshot", restored)
        except Exception as exc:
            errors.append(f"snapshot: {exc}")
            log.error("snapshot import failed: %s", exc)

    for tp in topics:
        started = db.now_iso()
        error = ""
        created: list[dict] = []
        seen = 0
        notified = 0
        try:
            articles, seen = collect_all(tp)
            conn = db.get_conn()
            for a in articles:
                if db.insert_article(conn, a, topic=tp):
                    created.append(a)
            conn.commit()
            log.info("[%s] seen=%d relevant=%d new=%d", tp, seen, len(articles), len(created))
            if created and notify:
                created.sort(key=lambda x: x.get("published_at") or "", reverse=True)
                notified = notify_new(created, topic=tp)
        except Exception as exc:
            error = f"{exc}"
            errors.append(f"{tp}: {exc}")
            log.error("[%s] pipeline failed: %s\n%s", tp, exc, traceback.format_exc())
        finally:
            db.record_run(started, seen, len(created), notified, error, topic=tp)
        totals["new"] += len(created)
        totals["seen"] += seen
        totals["notified"] += notified

    try:
        db.export_snapshot()
    except Exception as exc:
        errors.append(f"export: {exc}")
        log.error("snapshot export failed: %s", exc)

    return {**totals, "error": "; ".join(errors)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one collection pass")
    parser.add_argument("--no-notify", action="store_true", help="skip Telegram push")
    parser.add_argument("--no-snapshot", action="store_true", help="skip snapshot import")
    parser.add_argument("--topic", default="", choices=config.topic_keys(),
                        help="collect only this topic (default: all topics)")
    parser.add_argument("--json", action="store_true", help="print result as JSON")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    result = run_once(notify=not args.no_notify, use_snapshot=not args.no_snapshot,
                      topic=args.topic)
    if args.json:
        print(json.dumps(result))
    else:
        print(f"done: {result}")
    return 1 if result["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
