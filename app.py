# -*- coding: utf-8 -*-
"""
FastAPI Web UI for Gelonghui HK Stock News Dashboard

Provides web interface for viewing news, stock frequency analysis,
and info category frequency analysis.

Author: jasperchan
"""

import json
from collections import Counter
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, desc
from database import (
    create_database_engine,
    get_session,
    HKStockLive,
    timestamp_to_hkt,
    safe_json_loads,
    extract_stock_codes,
    extract_info_names,
    extract_stock_names
)

# Initialize FastAPI app
app = FastAPI(title="HK Stock News Dashboard", version="1.0.0")

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")

# Create custom Jinja2 environment with caching disabled
from jinja2 import Environment, FileSystemLoader
jinja_env = Environment(
    loader=FileSystemLoader("templates"),
    cache_size=0,
    auto_reload=True
)
templates = Jinja2Templates(env=jinja_env)

# Database engine
engine = None

@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup"""
    global engine
    engine = create_database_engine()

@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection on shutdown"""
    global engine
    if engine:
        engine.dispose()

# ────────────────────────────────────────────────
# HTML Page Routes
# ────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard overview page"""
    session = get_session(engine)
    try:
        # Get total news count
        total_count = session.query(HKStockLive).count()
        
        # Get today's news count (using HKT timezone for consistency with display)
        # HKT is UTC+8, so we need to calculate today's start in HKT
        from datetime import timezone as tz
        hkt_timezone = tz(timedelta(hours=8))
        today_start_hkt = datetime.now(hkt_timezone).replace(hour=0, minute=0, second=0, microsecond=0)
        # Convert HKT midnight to UTC for database comparison
        today_start_utc = today_start_hkt.astimezone(timezone.utc)
        today_start_ts = int(today_start_utc.timestamp())
        today_count = session.query(HKStockLive)\
            .filter(HKStockLive.create_timestamp >= today_start_ts)\
            .count()
        
        # Get news per day (last 30 days)
        thirty_days_ago = int((datetime.now(timezone.utc) - timedelta(days=30)).timestamp() * 1000)
        daily_counts = session.query(
            func.date(func.from_unixtime(HKStockLive.create_timestamp / 1000)).label('date'),
            func.count(HKStockLive.id).label('count')
        ).filter(
            HKStockLive.create_timestamp >= thirty_days_ago
        ).group_by('date').order_by('date').all()
        
        # Get top 10 stocks for chart (today only)
        stock_frequency = get_stock_frequency_today(session, limit=10)
        
        # Get top 3 stocks for stats card (today only)
        top_3_stocks = get_stock_frequency_today(session, limit=3)
        
        # Get available markets for filtering
        available_markets = get_available_markets(session)
        
        # Get stock frequency by market for each available market
        market_stock_data = {}
        for market in available_markets:
            market_stock_data[market] = get_stock_frequency_by_market(session, market, limit=10)
        
        # Get top 10 info categories for chart
        info_frequency = get_info_frequency(session, limit=10)
        
        # Get top 3 info categories for stats card (today only)
        top_3_infos = get_info_frequency_today(session, limit=3)
        
        # Get recent news (last 15)
        recent_news = session.query(HKStockLive)\
            .order_by(desc(HKStockLive.create_timestamp))\
            .limit(15)\
            .all()
        
        recent_news_data = []
        for news in recent_news:
            recent_news_data.append({
                'id': news.id,
                'title': news.title or 'Untitled',
                'content': (news.content[:100] + '...') if news.content and len(news.content) > 100 else (news.content or ''),
                'timestamp': timestamp_to_hkt(news.create_timestamp),
                'create_timestamp': news.create_timestamp,
                'stocks': extract_stock_codes(news.related_stocks),
                'infos': extract_info_names(news.related_infos)
            })
        
        # Convert all data to JSON strings to avoid Jinja2 caching issues
        # Create simple context dict without request object to avoid unhashable type errors
        # Use only simple types (strings, numbers) to prevent caching issues
        context = {
            "total_count": int(total_count),
            "today_count": int(today_count),
            "daily_counts_json": str(json.dumps([{'date': str(d[0]), 'count': d[1]} for d in daily_counts])),
            "stock_frequency_json": str(json.dumps(stock_frequency)),
            "top_3_stocks_json": str(json.dumps(top_3_stocks)),
            "available_markets_json": str(json.dumps(available_markets)),
            "market_stock_data_json": str(json.dumps(market_stock_data)),
            "info_frequency_json": str(json.dumps(info_frequency)),
            "top_3_infos_json": str(json.dumps(top_3_infos)),
            "recent_news_json": str(json.dumps(recent_news_data))
        }
        
        # Manually render template to bypass TemplateResponse issues
        template = jinja_env.get_template("index.html")
        html_content = template.render(**context)
        return HTMLResponse(content=html_content)
    finally:
        session.close()

@app.get("/news", response_class=HTMLResponse)
async def news_page(request: Request):
    """News feed page"""
    # Manually render template to bypass TemplateResponse issues
    template = jinja_env.get_template("news.html")
    html_content = template.render()
    return HTMLResponse(content=html_content)

@app.get("/stocks", response_class=HTMLResponse)
async def stocks_page(request: Request):
    """Stock frequency analysis page"""
    session = get_session(engine)
    try:
        stock_frequency = get_stock_frequency(session, limit=50)
        context = {
            "stock_frequency_json": json.dumps(stock_frequency)
        }
        
        # Manually render template to bypass TemplateResponse issues
        template = jinja_env.get_template("stocks.html")
        html_content = template.render(**context)
        return HTMLResponse(content=html_content)
    finally:
        session.close()

@app.get("/infos", response_class=HTMLResponse)
async def infos_page(request: Request):
    """Info category frequency analysis page"""
    session = get_session(engine)
    try:
        info_frequency = get_info_frequency(session, limit=50)
        context = {
            "info_frequency_json": json.dumps(info_frequency)
        }
        
        # Manually render template to bypass TemplateResponse issues
        template = jinja_env.get_template("infos.html")
        html_content = template.render(**context)
        return HTMLResponse(content=html_content)
    finally:
        session.close()

# ────────────────────────────────────────────────
# JSON API Routes
# ────────────────────────────────────────────────

@app.get("/api/news")
async def api_news(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query(None),
    stock: str = Query(None),
    info: str = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None)
):
    """API endpoint for news data with pagination and filters"""
    session = get_session(engine)
    try:
        query = session.query(HKStockLive)
        
        # Apply search filter
        if search:
            query = query.filter(
                (HKStockLive.title.contains(search)) |
                (HKStockLive.content.contains(search))
            )
        
        # Apply stock filter
        if stock:
            query = query.filter(HKStockLive.related_stocks.contains(stock))
        
        # Apply info filter
        if info:
            query = query.filter(HKStockLive.related_infos.contains(info))
        
        # Apply date filters
        if date_from:
            try:
                from datetime import datetime as dt
                date_from_ts = int(dt.strptime(date_from, "%Y-%m-%d").timestamp() * 1000)
                query = query.filter(HKStockLive.create_timestamp >= date_from_ts)
            except ValueError:
                pass
        
        if date_to:
            try:
                from datetime import datetime as dt
                date_to_ts = int((dt.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)).timestamp() * 1000)
                query = query.filter(HKStockLive.create_timestamp < date_to_ts)
            except ValueError:
                pass
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        news_items = query.order_by(desc(HKStockLive.create_timestamp))\
            .offset((page - 1) * page_size)\
            .limit(page_size)\
            .all()
        
        # Format response
        items = []
        for news in news_items:
            items.append({
                'id': news.id,
                'title': news.title or 'Untitled',
                'content': news.content or '',
                'timestamp': timestamp_to_hkt(news.create_timestamp),
                'stocks': extract_stock_codes(news.related_stocks),
                'infos': extract_info_names(news.related_infos),
                'route': news.route or ''
            })
        
        return {
            'items': items,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size
        }
    finally:
        session.close()

@app.get("/api/stocks/frequency")
async def api_stocks_frequency(limit: int = Query(50, ge=1, le=200)):
    """API endpoint for stock code frequency"""
    session = get_session(engine)
    try:
        return get_stock_frequency(session, limit=limit)
    finally:
        session.close()

@app.get("/api/infos/frequency")
async def api_infos_frequency(limit: int = Query(50, ge=1, le=200)):
    """API endpoint for info category frequency"""
    session = get_session(engine)
    try:
        return get_info_frequency(session, limit=limit)
    finally:
        session.close()

@app.get("/api/stats/overview")
async def api_stats_overview():
    """API endpoint for dashboard statistics"""
    session = get_session(engine)
    try:
        total_count = session.query(HKStockLive).count()
        
        # Get news per day (last 30 days)
        thirty_days_ago = int((datetime.now(timezone.utc) - timedelta(days=30)).timestamp() * 1000)
        daily_counts = session.query(
            func.date(func.from_unixtime(HKStockLive.create_timestamp / 1000)).label('date'),
            func.count(HKStockLive.id).label('count')
        ).filter(
            HKStockLive.create_timestamp >= thirty_days_ago
        ).group_by('date').order_by('date').all()
        
        return {
            'total_count': total_count,
            'daily_counts': [{'date': str(d[0]), 'count': d[1]} for d in daily_counts],
            'top_stocks': get_stock_frequency(session, limit=10),
            'top_infos': get_info_frequency(session, limit=10)
        }
    finally:
        session.close()

@app.get("/api/test/stock-names")
async def api_test_stock_names():
    """TEST: Extract stock names from related_stocks to see actual data"""
    session = get_session(engine)
    try:
        # Get the most recent news item with related_stocks
        news = session.query(HKStockLive)\
            .filter(HKStockLive.related_stocks.isnot(None))\
            .order_by(desc(HKStockLive.create_timestamp))\
            .first()
        
        if not news:
            return {"error": "No news with related_stocks found"}
        
        # Extract stock names using test function
        stock_names = extract_stock_names(news.related_stocks)
        stock_codes = extract_stock_codes(news.related_stocks)
        
        return {
            "news_id": news.id,
            "news_title": news.title,
            "related_stocks_raw": news.related_stocks,
            "stock_codes_extracted": stock_codes,
            "stock_names_extracted": stock_names
        }
    finally:
        session.close()

@app.get("/api/test/available-markets")
async def api_test_available_markets():
    """TEST: Check if get_available_markets function is working"""
    session = get_session(engine)
    try:
        # Test the get_available_markets function
        available_markets = get_available_markets(session)
        
        # Also get a sample of related_stocks to see the data structure
        sample_news = session.query(HKStockLive.related_stocks)\
            .filter(HKStockLive.related_stocks.isnot(None))\
            .limit(3)\
            .all()
        
        sample_data = []
        for item in sample_news:
            if item[0]:
                stocks = safe_json_loads(item[0])
                sample_data.append({
                    "raw": item[0],
                    "parsed": stocks
                })
        
        return {
            "available_markets": available_markets,
            "sample_data": sample_data
        }
    finally:
        session.close()

@app.get("/api/test/dashboard-context")
async def api_test_dashboard_context():
    """TEST: Check what context is being passed to dashboard template"""
    session = get_session(engine)
    try:
        # Get available markets
        available_markets = get_available_markets(session)
        
        # Get stock frequency by market
        market_stock_data = {}
        for market in available_markets:
            market_stock_data[market] = get_stock_frequency_by_market(session, market, limit=10)
        
        return {
            "available_markets": available_markets,
            "available_markets_json": json.dumps(available_markets),
            "market_stock_data": market_stock_data,
            "market_stock_data_json": json.dumps(market_stock_data)
        }
    finally:
        session.close()

# ────────────────────────────────────────────────
# Helper Functions
# ────────────────────────────────────────────────

def get_stock_frequency(session, limit=50):
    """Get stock code frequency from database"""
    # Get all news with related_stocks
    news_items = session.query(HKStockLive.related_stocks)\
        .filter(HKStockLive.related_stocks.isnot(None))\
        .all()
    
    # Count stock codes
    stock_counter = Counter()
    for item in news_items:
        if item[0]:
            stocks = safe_json_loads(item[0])
            for stock in stocks:
                code = stock.get('code', '')
                name = stock.get('name', '')
                if code:
                    stock_counter[f"{code}|{name}"] += 1
    
    # Return top N
    result = []
    for stock_key, count in stock_counter.most_common(limit):
        code, name = stock_key.split('|', 1)
        result.append({
            'code': code,
            'name': name,
            'frequency': count
        })
    return result

def get_info_frequency(session, limit=50):
    """Get info category frequency from database"""
    # Get all news with related_infos
    news_items = session.query(HKStockLive.related_infos)\
        .filter(HKStockLive.related_infos.isnot(None))\
        .all()
    
    # Count info names
    info_counter = Counter()
    for item in news_items:
        if item[0]:
            infos = safe_json_loads(item[0])
            for info in infos:
                name = info.get('name', '')
                if name:
                    info_counter[name] += 1
    
    # Return top N
    result = []
    for name, count in info_counter.most_common(limit):
        result.append({
            'name': name,
            'frequency': count
        })
    return result

def get_stock_frequency_today(session, limit=50):
    """Get stock code frequency from today's news only"""
    # Calculate today's start in HKT timezone
    from datetime import timezone as tz
    hkt_timezone = tz(timedelta(hours=8))
    today_start_hkt = datetime.now(hkt_timezone).replace(hour=0, minute=0, second=0, microsecond=0)
    # Convert HKT midnight to UTC for database comparison
    today_start_utc = today_start_hkt.astimezone(timezone.utc)
    today_start_ts = int(today_start_utc.timestamp())
    
    # Get today's news with related_stocks
    news_items = session.query(HKStockLive.related_stocks)\
        .filter(HKStockLive.related_stocks.isnot(None))\
        .filter(HKStockLive.create_timestamp >= today_start_ts)\
        .all()
    
    # Count stock codes
    stock_counter = Counter()
    for item in news_items:
        if item[0]:
            stocks = safe_json_loads(item[0])
            for stock in stocks:
                code = stock.get('code', '')
                name = stock.get('name', '')
                if code:
                    stock_counter[f"{code}|{name}"] += 1
    
    # Return top N
    result = []
    for stock_key, count in stock_counter.most_common(limit):
        code, name = stock_key.split('|', 1)
        result.append({
            'code': code,
            'name': name,
            'frequency': count
        })
    return result

def get_info_frequency_today(session, limit=50):
    """Get info category frequency from today's news only"""
    # Calculate today's start in HKT timezone
    from datetime import timezone as tz
    hkt_timezone = tz(timedelta(hours=8))
    today_start_hkt = datetime.now(hkt_timezone).replace(hour=0, minute=0, second=0, microsecond=0)
    # Convert HKT midnight to UTC for database comparison
    today_start_utc = today_start_hkt.astimezone(timezone.utc)
    today_start_ts = int(today_start_utc.timestamp())
    
    # Get today's news with related_infos
    news_items = session.query(HKStockLive.related_infos)\
        .filter(HKStockLive.related_infos.isnot(None))\
        .filter(HKStockLive.create_timestamp >= today_start_ts)\
        .all()
    
    # Count info names
    info_counter = Counter()
    for item in news_items:
        if item[0]:
            infos = safe_json_loads(item[0])
            for info in infos:
                name = info.get('name', '')
                if name:
                    info_counter[name] += 1
    
    # Return top N
    result = []
    for name, count in info_counter.most_common(limit):
        result.append({
            'name': name,
            'frequency': count
        })
    return result

def get_stock_frequency_by_market(session, market, limit=50):
    """Get stock code frequency filtered by specific market"""
    # Get all news with related_stocks
    news_items = session.query(HKStockLive.related_stocks)\
        .filter(HKStockLive.related_stocks.isnot(None))\
        .all()
    
    # Count stock codes for specific market
    stock_counter = Counter()
    for item in news_items:
        if item[0]:
            stocks = safe_json_loads(item[0])
            for stock in stocks:
                code = stock.get('code', '')
                name = stock.get('name', '')
                stock_market = stock.get('market', '')
                if code and stock_market == market:
                    stock_counter[f"{code}|{name}|{stock_market}"] += 1
    
    # Return top N
    result = []
    for stock_key, count in stock_counter.most_common(limit):
        code, name, stock_market = stock_key.split('|', 2)
        result.append({
            'code': code,
            'name': name,
            'market': stock_market,
            'frequency': count
        })
    return result

def get_available_markets(session):
    """Get list of available markets from the data"""
    # Get all news with related_stocks
    news_items = session.query(HKStockLive.related_stocks)\
        .filter(HKStockLive.related_stocks.isnot(None))\
        .all()
    
    # Extract unique markets
    markets = set()
    for item in news_items:
        if item[0]:
            stocks = safe_json_loads(item[0])
            for stock in stocks:
                market = stock.get('market', '')
                if market:
                    markets.add(market)
    
    return sorted(list(markets))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)