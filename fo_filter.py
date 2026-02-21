# =============================================================================
# fo_filter.py — NSE F&O Stock List Management
#
# NSE publishes an official list of all stocks that have active F&O contracts.
# This module downloads that list, caches it, and exposes a simple function
# to check whether any given stock symbol is F&O eligible.
#
# Why this matters: If a stock isn't on this list, it has no option chain,
# and there's nothing actionable for us.
# =============================================================================

import os
import time
import logging
import requests
import pandas as pd

from config import FO_LIST_URL, FO_CACHE_FILE, FO_CACHE_TTL_HOURS

logger = logging.getLogger(__name__)


def _cache_is_fresh() -> bool:
    """Check if the cached F&O list file exists and is recent enough to use."""
    if not os.path.exists(FO_CACHE_FILE):
        return False
    file_age_hours = (time.time() - os.path.getmtime(FO_CACHE_FILE)) / 3600
    return file_age_hours < FO_CACHE_TTL_HOURS


def _download_fo_list() -> pd.DataFrame:
    """
    Download the F&O lot size CSV from NSE and save it to disk.
    The CSV has a column 'SYMBOL' with all eligible stock symbols.
    """
    logger.info("Downloading fresh F&O list from NSE...")
    headers = {
        # NSE blocks requests without a browser-like User-Agent
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.nseindia.com/",
    }
    response = requests.get(FO_LIST_URL, headers=headers, timeout=15)
    response.raise_for_status()

    # Save raw bytes to cache file
    with open(FO_CACHE_FILE, "wb") as f:
        f.write(response.content)

    logger.info(f"F&O list saved to {FO_CACHE_FILE}")
    return _load_fo_list_from_cache()


def _load_fo_list_from_cache() -> pd.DataFrame:
    """Load the cached F&O CSV into a DataFrame."""
    # The NSE CSV has a quirky format — first row is a header we skip,
    # and symbol column is named 'SYMBOL'
    df = pd.read_csv(FO_CACHE_FILE)
    df.columns = df.columns.str.strip().str.upper()
    return df


def get_fo_symbols() -> set:
    """
    Return the set of all NSE symbols that have active F&O contracts.
    Uses cached data if it's fresh; downloads fresh data otherwise.

    Returns:
        A set of uppercase symbol strings, e.g. {'RELIANCE', 'TCS', 'INFY', ...}
    """
    try:
        if _cache_is_fresh():
            logger.info("Using cached F&O list")
            df = _load_fo_list_from_cache()
        else:
            df = _download_fo_list()

        symbols = set(df["SYMBOL"].dropna().str.strip().str.upper())
        logger.info(f"F&O list loaded: {len(symbols)} symbols")
        return symbols

    except Exception as e:
        logger.error(f"Failed to load F&O list: {e}")
        # If download fails, return an empty set — the caller handles this gracefully
        return set()


def filter_to_fo_stocks(symbols: list[str], fo_symbols: set) -> list[str]:
    """
    Filter a list of stock symbols to only those that have F&O contracts.

    Args:
        symbols:    Raw list of symbols from scanners
        fo_symbols: The set returned by get_fo_symbols()

    Returns:
        Filtered list containing only F&O-eligible symbols
    """
    filtered = [s.upper() for s in symbols if s.upper() in fo_symbols]
    removed = len(symbols) - len(filtered)
    logger.info(f"F&O filter: kept {len(filtered)}, removed {removed} non-F&O stocks")
    return filtered
