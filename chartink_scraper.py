# =============================================================================
# chartink_scraper.py — Fetch swing trade ideas from Chartink scanners
#
# Chartink is a free Indian stock screener. Its public scanners let us POST
# a technical scan clause and get back a list of matching stocks.
#
# We run several different scanners and aggregate the results. A stock that
# shows up in multiple scanners gets a higher signal score.
# =============================================================================

import logging
import requests

from config import CHARTINK_SCANNERS

logger = logging.getLogger(__name__)

# Chartink's screener API endpoint — this is the same URL the website uses internally
CHARTINK_URL = "https://chartink.com/screener/process"

# We need these headers to mimic a browser request; Chartink blocks raw API calls
CHARTINK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://chartink.com/screener/",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded",
}


def _get_csrf_token(session: requests.Session) -> str:
    """
    Chartink requires a CSRF token for POST requests.
    We get it by first loading the screener page and reading the cookie.
    """
    session.get("https://chartink.com/screener/", headers=CHARTINK_HEADERS, timeout=10)
    token = session.cookies.get("_csrf_token", "")
    if not token:
        logger.warning("CSRF token not found — Chartink request may fail")
    return token


def _run_single_scanner(
    session: requests.Session,
    csrf_token: str,
    scanner_name: str,
    scan_clause: str,
) -> list[dict]:
    """
    Run a single Chartink scanner and return the raw results.

    Args:
        session:        Shared requests session (maintains cookies)
        csrf_token:     CSRF token from the session
        scanner_name:   Human-readable name (for logging only)
        scan_clause:    The Chartink scan clause string

    Returns:
        List of dicts, each representing one matching stock.
        Keys include: 'nsecode', 'close', 'volume', 'per_chg' etc.
    """
    payload = {
        "_csrf_token": csrf_token,
        "scan_clause": scan_clause,
    }
    try:
        response = session.post(
            CHARTINK_URL,
            data=payload,
            headers=CHARTINK_HEADERS,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()

        stocks = data.get("data", [])
        logger.info(f"Scanner '{scanner_name}': found {len(stocks)} stocks")
        return stocks

    except requests.exceptions.Timeout:
        logger.warning(f"Scanner '{scanner_name}' timed out")
        return []
    except Exception as e:
        logger.error(f"Scanner '{scanner_name}' failed: {e}")
        return []


def fetch_all_scanner_results() -> dict[str, list[dict]]:
    """
    Run all configured scanners and return results grouped by scanner name.

    Returns:
        Dict mapping scanner_name → list of stock dicts from Chartink
        Example: {
            "volume_breakout": [{"nsecode": "RELIANCE", "close": "2450.5", ...}, ...],
            "rsi_momentum":    [{"nsecode": "TCS", ...}, ...],
        }
    """
    results = {}
    session = requests.Session()

    # Get CSRF token once and reuse it for all scanner requests
    csrf_token = _get_csrf_token(session)

    for scanner_name, scan_clause in CHARTINK_SCANNERS.items():
        stocks = _run_single_scanner(session, csrf_token, scanner_name, scan_clause)
        results[scanner_name] = stocks

    return results


def aggregate_scanner_results(raw_results: dict[str, list[dict]]) -> dict[str, dict]:
    """
    Combine results from all scanners into a single dict keyed by symbol.
    Track how many scanners flagged each stock — this is our primary signal strength.

    Args:
        raw_results: Output of fetch_all_scanner_results()

    Returns:
        Dict mapping symbol → aggregated stock info.
        Example: {
            "RELIANCE": {
                "symbol": "RELIANCE",
                "close": 2450.5,
                "volume": 1234567,
                "volume_ratio": 2.3,        # today's vol / 20-day avg
                "change_pct": 1.8,
                "scanner_count": 2,          # appeared in 2 scanners
                "scanners_hit": ["volume_breakout", "rsi_momentum"],
            },
            ...
        }
    """
    aggregated = {}

    for scanner_name, stocks in raw_results.items():
        for stock in stocks:
            symbol = stock.get("nsecode", "").strip().upper()
            if not symbol:
                continue

            if symbol not in aggregated:
                # First time seeing this stock — initialize its entry
                aggregated[symbol] = {
                    "symbol": symbol,
                    "close": _safe_float(stock.get("close", 0)),
                    "volume": _safe_float(stock.get("volume", 0)),
                    "volume_ratio": _safe_float(stock.get("per_chg_vol", 0)),  # Chartink field name
                    "change_pct": _safe_float(stock.get("per_chg", 0)),
                    "scanner_count": 0,
                    "scanners_hit": [],
                }

            # Increment the count each time a scanner flags this stock
            aggregated[symbol]["scanner_count"] += 1
            aggregated[symbol]["scanners_hit"].append(scanner_name)

    logger.info(f"Aggregated {len(aggregated)} unique stocks across all scanners")
    return aggregated


def _safe_float(value) -> float:
    """Convert a value to float safely, returning 0.0 on failure."""
    try:
        return float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0
