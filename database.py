# -*- coding: utf-8 -*-
"""
Database Configuration Module for Web UI

Handles MySQL database connection for Gelonghui HK Stock data.
Uses environment variables for database credentials (Railway compatible).

Author: jasperchan
"""

import os
import logging
import json
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, Column, String, BigInteger, Text, Boolean, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# SQLAlchemy Base
Base = declarative_base()

# ────────────────────────────────────────────────
# Database Table Schema
# ────────────────────────────────────────────────

class HKStockLive(Base):
    """SQLAlchemy model for HK Stock Live data from Gelonghui"""
    __tablename__ = 'hk_stock_lives'
    
    id = Column(String(50), primary_key=True)
    title = Column(Text, nullable=True)
    create_timestamp = Column(BigInteger, nullable=True, index=True)
    update_timestamp = Column(BigInteger, nullable=True)
    count = Column(Text, nullable=True)  # JSON string
    statistic = Column(Text, nullable=True)  # JSON string
    content = Column(Text, nullable=True)
    content_prefix = Column(Text, nullable=True)
    related_stocks = Column(Text, nullable=True)  # JSON string
    related_infos = Column(Text, nullable=True)  # JSON string
    pictures = Column(Text, nullable=True)  # JSON string
    related_articles = Column(Text, nullable=True)  # JSON string
    source = Column(Text, nullable=True)  # JSON string
    interpretation = Column(Text, nullable=True)
    level = Column(BigInteger, nullable=True)
    route = Column(Text, nullable=True)
    close_comment = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

# ────────────────────────────────────────────────
# Database Connection
# ────────────────────────────────────────────────

def get_database_url():
    """
    Build database URL from environment variables.
    Supports both Railway's MYSQL_PUBLIC_URL and individual MySQL credentials.
    """
    # Try Railway's MYSQL_PUBLIC_URL first
    database_url = os.getenv("MYSQL_PUBLIC_URL")
    if database_url:
        # Fix for SQLAlchemy 2.0+ (Railway uses mysql://, need mysql+pymysql://)
        if database_url.startswith("mysql://"):
            database_url = database_url.replace("mysql://", "mysql+pymysql://", 1)
        logger.info("Using MYSQL_PUBLIC_URL from environment")
        return database_url
    
    # Fall back to individual credentials
    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = os.getenv("MYSQL_DATABASE", "gelonghui")
    
    database_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
    logger.info(f"Using MySQL connection: {host}:{port}/{database}")
    return database_url

def create_database_engine():
    """Create SQLAlchemy engine with connection pooling"""
    database_url = get_database_url()
    
    engine = create_engine(
        database_url,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,  # Recycle connections after 30 minutes
        echo=False
    )
    
    return engine

def get_session(engine):
    """Create a new database session"""
    Session = sessionmaker(bind=engine)
    return Session()

# ────────────────────────────────────────────────
# Utility Functions
# ────────────────────────────────────────────────

def timestamp_to_hkt(timestamp_sec):
    """Convert Unix timestamp (sec) to HKT datetime string"""
    if not timestamp_sec:
        return "N/A"
    utc_time = datetime.fromtimestamp(timestamp_sec, tz=timezone.utc)
    hkt_time = utc_time + timedelta(hours=8)
    return hkt_time.strftime("%Y-%m-%d %H:%M:%S HKT")

def safe_json_loads(json_str):
    """Safely parse JSON string"""
    if not json_str:
        return []
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return []

def extract_stock_codes(related_stocks_json):
    """Extract stock codes from related_stocks JSON"""
    stocks = safe_json_loads(related_stocks_json)
    return [stock.get("code", "") for stock in stocks if stock.get("code")]

def extract_info_names(related_infos_json):
    """Extract info names from related_infos JSON"""
    infos = safe_json_loads(related_infos_json)
    return [info.get("name", "") for info in infos if info.get("name")]