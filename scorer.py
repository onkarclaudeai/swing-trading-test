# =============================================================================
# scorer.py — Score and rank stocks, then pick the top N
#
# The scoring logic is intentionally simple and transparent.
# Each factor is normalized to a 0–1 range, then combined using weights
# defined in config.py. This makes it easy to tune — if you think volume
# matters more than scanner count, just bump up its weight.
# =============================================================================

import logging
from config import SCORE_WEIGHTS, MIN_STOCK_PRICE, MAX_STOCK_PRICE, TOP_N_RESULTS

logger = logging.getLogger(__name__)

# Maximum number of scanners a stock could appear in (used for normalization)
MAX_SCANNER_COUNT = 3   # Update this if you add more scanners in config.py


def _normalize_scanner_count(count: int) -> float:
    """
    Convert scanner count to a 0–1 score.
    A stock appearing in all scanners gets 1.0, appearing in one gets ~0.33.
    """
    return min(count / MAX_SCANNER_COUNT, 1.0)


def _normalize_volume_ratio(ratio: float) -> float:
    """
    Convert volume ratio (today's volume / 20-day avg) to a 0–1 score.
    We cap at 5x volume — anything above that is treated as maximum signal.
    A ratio of 1.0 (normal volume) scores 0, ratio of 3x scores ~0.5.
    """
    if ratio <= 1.0:
        return 0.0
    return min((ratio - 1.0) / 4.0, 1.0)   # (ratio - 1) because 1x is baseline


def _normalize_price_range(price: float) -> float:
    """
    Give higher scores to stocks in the "sweet spot" for options liquidity.
    Stocks priced 200–2000 tend to have the most active option chains.
    Outside this range the score tapers off.
    """
    if price < MIN_STOCK_PRICE or price > MAX_STOCK_PRICE:
        return 0.0   # Outside our tradeable range entirely
    if 200 <= price <= 2000:
        return 1.0   # Sweet spot — full score
    if price < 200:
        return (price - MIN_STOCK_PRICE) / (200 - MIN_STOCK_PRICE)
    # price > 2000
    return 1.0 - (price - 2000) / (MAX_STOCK_PRICE - 2000)


def score_stock(stock: dict) -> float:
    """
    Calculate a composite score (0–100) for a single stock.

    Args:
        stock: A stock dict from chartink_scraper.aggregate_scanner_results()

    Returns:
        Float score between 0 and 100. Higher = stronger signal.
    """
    scanner_score = _normalize_scanner_count(stock["scanner_count"])
    volume_score  = _normalize_volume_ratio(stock["volume_ratio"])
    price_score   = _normalize_price_range(stock["close"])

    # Weighted sum, then scale to 0–100
    composite = (
        SCORE_WEIGHTS["scanner_count"] * scanner_score +
        SCORE_WEIGHTS["volume_ratio"]  * volume_score  +
        SCORE_WEIGHTS["price_range"]   * price_score
    )
    return round(composite * 100, 1)


def rank_and_select(stocks: dict[str, dict]) -> list[dict]:
    """
    Score all stocks, sort by score descending, and return the top N.

    Args:
        stocks: Dict of symbol → stock info (output of aggregate_scanner_results)

    Returns:
        List of top N stock dicts, each with a 'score' field added.
        Sorted best-first.
    """
    scored = []
    for symbol, stock in stocks.items():
        stock["score"] = score_stock(stock)
        scored.append(stock)

    # Sort highest score first
    scored.sort(key=lambda s: s["score"], reverse=True)

    top = scored[:TOP_N_RESULTS]
    logger.info(f"Top {len(top)} stocks selected from {len(scored)} candidates")
    return top


def build_strategy_hint(stock: dict) -> str:
    """
    Generate a simple directional hint based on price change and volume.
    This is NOT a buy/sell recommendation — it's a starting point for your research.

    Rules:
      - Strong positive move + high volume → lean Bullish (consider CE)
      - Strong negative move + high volume → lean Bearish (consider PE)
      - Ambiguous → Neutral (consider Straddle if IV is low)
    """
    change = stock.get("change_pct", 0)
    volume_ratio = stock.get("volume_ratio", 1)

    if change > 1.5 and volume_ratio > 1.5:
        return "Bullish — consider ATM/OTM Call (CE)"
    elif change < -1.5 and volume_ratio > 1.5:
        return "Bearish — consider ATM/OTM Put (PE)"
    else:
        return "Neutral — watch price action; Straddle if IV is low"
