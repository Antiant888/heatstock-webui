# -*- coding: utf-8 -*-
"""
HKEX News Scraper Module

Fetches the latest HK Exchange filings from the public HKEX JSON API
and upserts them into the hkex_news MySQL table.

API endpoint (paginated):
  https://www1.hkexnews.hk/ncms/json/eds/lcisehk7relsdc_{page}.json?_={epoch_ms}
  Page 1 returns ``maxNumOfFile`` indicating the total number of pages.

Author: jasperchan
"""

import time
import json
import logging
import requests
from datetime import datetime, timezone
from sqlalchemy import inspect, text
from database import Base, HKEXNews

logger = logging.getLogger(__name__)

HKEX_API_URL_TEMPLATE = "https://www1.hkexnews.hk/ncms/json/eds/lcisehk7relsdc_{page}.json"
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

def _fetch_page(page: int) -> dict:
    """Fetch a single HKEX API page and return the parsed JSON."""
    epoch_ms = int(time.time() * 1000)
    url = f"{HKEX_API_URL_TEMPLATE.format(page=page)}?_={epoch_ms}"
    logger.info(f"Fetching HKEX page {page}: {url}")
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
    return resp.json()


def scrape_hkex_news(engine):
    """
    Fetch ALL HKEX filings from the public JSON API (all pages) and upsert
    into hkex_news.

    Strategy: page 1's ``maxNumOfFile`` only reflects recently-generated pages
    and under-counts older historical pages.  Instead we loop pages 1, 2, 3 …
    and stop as soon as a page returns an empty ``newsInfoLst`` or fails to
    parse (HKEX returns an empty body for out-of-range pages).

    Returns:
        dict: {"inserted": N, "updated": N, "total": N}
    """
    news_list = []
    page = 1
    while True:
        try:
            data = _fetch_page(page)
            page_items = data.get("newsInfoLst", [])
        except Exception as exc:
            logger.info(f"  Page {page} returned invalid/empty response – stopping. ({exc})")
            break

        if not page_items:
            logger.info(f"  Page {page} is empty – stopping.")
            break

        logger.info(f"  Page {page}: {len(page_items)} filings")
        news_list.extend(page_items)
        page += 1

    logger.info(f"Total filings fetched across {page - 1} page(s): {len(news_list)}")

    if not news_list:
        logger.warning("Empty newsInfoLst returned – nothing to insert")
        return {"inserted": 0, "updated": 0, "total": 0}

    # Build rows to upsert (deduplicate by news_id, last occurrence wins)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    rows_by_id: dict = {}
    for item in news_list:
        news_id = item.get("newsId")
        if not news_id:
            continue
        rows_by_id[int(news_id)] = {
            "news_id":   int(news_id),
            "title":     (item.get("title") or "")[:500],
            "l_txt":     (item.get("lTxt")  or "")[:1000],
            "s_txt":     (item.get("sTxt")  or "")[:500],
            "ext":       (item.get("ext")   or "")[:10],
            "size_kb":   (item.get("size")  or "")[:20],
            "web_path":  (item.get("webPath") or ""),
            "market":    (item.get("market")  or "")[:10],
            "multi":     int(item.get("multi") or 0),
            "stocks":    json.dumps(item.get("stock") or [], ensure_ascii=False),
            "rel_time":  (item.get("relTime") or "")[:30],
            "t1_code":   (item.get("t1Code")  or "")[:20],
            "t2_code":   (item.get("t2Code")  or "")[:100],
            "scraped_at": now_str,
        }
    rows = list(rows_by_id.values())
    logger.info(f"After deduplication: {len(rows)} unique news_id(s) "
                f"(dropped {len(news_list) - len(rows)} duplicates)")

    logger.info(f"Upserting {len(rows)} rows into hkex_news …")

    upsert_sql = text("""
        INSERT INTO hkex_news
            (news_id, title, l_txt, s_txt, ext, size_kb, web_path,
             market, multi, stocks, rel_time, t1_code, t2_code, scraped_at)
        VALUES
            (:news_id, :title, :l_txt, :s_txt, :ext, :size_kb, :web_path,
             :market, :multi, :stocks, :rel_time, :t1_code, :t2_code, :scraped_at)
        ON DUPLICATE KEY UPDATE
            title      = VALUES(title),
            l_txt      = VALUES(l_txt),
            s_txt      = VALUES(s_txt),
            ext        = VALUES(ext),
            size_kb    = VALUES(size_kb),
            web_path   = VALUES(web_path),
            market     = VALUES(market),
            multi      = VALUES(multi),
            stocks     = VALUES(stocks),
            rel_time   = VALUES(rel_time),
            t1_code    = VALUES(t1_code),
            t2_code    = VALUES(t2_code),
            scraped_at = VALUES(scraped_at)
    """)

    with engine.begin() as conn:
        result = conn.execute(upsert_sql, rows)
        # MySQL rowcount: 1 = inserted, 2 = updated, 0 = unchanged
        rc = result.rowcount
        inserted = sum(1 for _ in range(len(rows)))  # upper bound; exact split below
        # MySQL reports 1 per insert, 2 per update, 0 per no-change
        # Use affected_rows heuristic when available
        inserted = rc if rc <= len(rows) else len(rows)
        updated  = rc - len(rows) if rc > len(rows) else 0

    logger.info(
        f"Scrape complete: ~{inserted} new/unchanged, ~{updated} updated "
        f"(MySQL affected_rows={rc}, total_fetched={len(news_list)})"
    )
    return {"inserted": inserted, "updated": updated, "total": len(news_list)}
