# -*- coding: utf-8 -*-
"""
HKEX Scraper Worker

Standalone long-running process that periodically fetches HKEX filings
and upserts them into the hkex_news MySQL table.

Environment variables:
  MYSQL_PUBLIC_URL          – Railway MySQL connection string (required)
  SCRAPE_INTERVAL_SECONDS   – seconds between scrape runs (default: 1800 = 30 min)

Author: jasperchan
"""

import os
import time
import logging
import sys

# ── Logging ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("scraper_worker")

# ── Config ─────────────────────────────────────────────────────
SCRAPE_INTERVAL = int(os.getenv("SCRAPE_INTERVAL_SECONDS", "1800"))


def main():
    from database import create_database_engine
    from scraper import init_hkex_table, scrape_hkex_news

    logger.info("Starting HKEX scraper worker")
    logger.info(f"Scrape interval: {SCRAPE_INTERVAL}s ({SCRAPE_INTERVAL // 60} min)")

    engine = create_database_engine()
    init_hkex_table(engine)
    logger.info("Database connection established, hkex_news table ready")

    run = 0
    while True:
        run += 1
        logger.info(f"── Scrape run #{run} starting ──")
        try:
            result = scrape_hkex_news(engine)
            logger.info(
                f"Run #{run} complete – "
                f"inserted={result['inserted']}, "
                f"updated={result['updated']}, "
                f"total_fetched={result['total']}"
            )
        except Exception as exc:
            logger.error(f"Run #{run} failed: {exc}", exc_info=True)

        logger.info(f"Sleeping {SCRAPE_INTERVAL}s until next run …")
        time.sleep(SCRAPE_INTERVAL)


if __name__ == "__main__":
    main()
