# -*- coding: utf-8 -*-
"""
HKEX News Scraper Module

Fetches the latest HK Exchange filings from the public HKEX JSON API
and upserts them into the hkex_news MySQL table.

API endpoint:
  https://www1.hkexnews.hk/ncms/json/eds/lcisehk7relsdc_1.json?_={epoch_ms}

Author: jasperchan
"""

import time
import json
import logging
import requests
from sqlalchemy import inspect
from database import Base, HKEXNews

logger = logging.getLogger(__name__)

HKEX_API_URL = "https://www1.hkexnews.hk/ncms/json/eds/lcisehk7relsdc_1.json"
HKEX_BASE_URL = "https://www1.hkexnews.hk"


# ────────────────────────────────────────────────────────────────
# Table Initialisation
# ────────────────────────────────────────────────────────────────

def init_hkex_table(engine):
    """Create hkex_news table if it does not already exist."""
    inspector = inspect(engine)
    if "hkex_news" not in inspector.get_table_names():
        Base.metadata.create_all(engine, tables=[HKEXNews.__table__])
        logger.info("Created hkex_news table")
    else:
        logger.info("hkex_news table already exists")


# ────────────────────────────────────────────────────────────────
# Scraper
# ────────────────────────────────────────────────────────────────

def scrape_hkex_news(engine):
    """
    Fetch HKEX filings from the public JSON API and upsert into hkex_news.

    Returns:
        dict: {"inserted": N, "updated": N, "total": N}
    """
    from database import get_session

    epoch_ms = int(time.time() * 1000)
    url = f"{HKEX_API_URL}?_={epoch_ms}"

    logger.info(f"Fetching HKEX filings from {url}")
    resp = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, */*",
            "Referer": "https://www1.hkexnews.hk/",
        },
    )
    resp.raise_for_status()
    data = resp.json()

    news_list = data.get("newsInfoLst", [])
    logger.info(f"Received {len(news_list)} filings from HKEX API")

    session = get_session(engine)
    inserted = 0
    updated = 0

    try:
        for item in news_list:
            news_id = item.get("newsId")
            if not news_id:
                continue

            stocks_json = json.dumps(item.get("stock", []), ensure_ascii=False)

            existing = session.query(HKEXNews).filter_by(news_id=news_id).first()
            if existing:
                existing.title   = item.get("title", "")
                existing.l_txt   = item.get("lTxt", "")
                existing.s_txt   = item.get("sTxt", "")
                existing.ext     = item.get("ext", "")
                existing.size_kb = item.get("size", "")
                existing.web_path = item.get("webPath", "")
                existing.market  = item.get("market", "")
                existing.multi   = item.get("multi", 0)
                existing.stocks  = stocks_json
                existing.rel_time = item.get("relTime", "")
                existing.t1_code  = item.get("t1Code", "")
                existing.t2_code  = item.get("t2Code", "")
                updated += 1
            else:
                record = HKEXNews(
                    news_id   = news_id,
                    title     = item.get("title", ""),
                    l_txt     = item.get("lTxt", ""),
                    s_txt     = item.get("sTxt", ""),
                    ext       = item.get("ext", ""),
                    size_kb   = item.get("size", ""),
                    web_path  = item.get("webPath", ""),
                    market    = item.get("market", ""),
                    multi     = item.get("multi", 0),
                    stocks    = stocks_json,
                    rel_time  = item.get("relTime", ""),
                    t1_code   = item.get("t1Code", ""),
                    t2_code   = item.get("t2Code", ""),
                )
                session.add(record)
                inserted += 1

        session.commit()
        logger.info(f"Scrape complete: {inserted} inserted, {updated} updated")
        return {"inserted": inserted, "updated": updated, "total": len(news_list)}

    except Exception as exc:
        session.rollback()
        logger.exception("Scrape failed, rolling back transaction")
        raise exc

    finally:
        session.close()
