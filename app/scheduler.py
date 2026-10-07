"""Standalone scheduler: run the pipeline every hour.

    python -m app.scheduler

If ENABLE_SCHEDULER=1 (default), the same loop is also started inside the
web server, so `uvicorn app.web:app` alone gives you dashboard + hourly
collection in one process.
"""
from __future__ import annotations

import logging
import time

from . import config
from .pipeline import run_once

log = logging.getLogger("scheduler")


def _sleep_to_next_boundary(interval_min: int) -> None:
    interval = max(1, interval_min) * 60
    now = time.time()
    next_run = (int(now // interval) + 1) * interval
    time.sleep(max(1.0, next_run - now))


def loop(run_immediately: bool = True) -> None:
    if run_immediately:
        try:
            run_once()
        except Exception as exc:
            log.error("run failed: %s", exc)
    while True:
        _sleep_to_next_boundary(config.COLLECT_INTERVAL_MIN)
        try:
            run_once()
        except Exception as exc:
            log.error("run failed: %s", exc)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    log.info("scheduler started, interval=%dmin", config.COLLECT_INTERVAL_MIN)
    loop(run_immediately=config.RUN_ON_START)


if __name__ == "__main__":
    main()
