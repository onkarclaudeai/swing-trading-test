# =============================================================================
# config.py — All configuration in one place
# If you need to tweak something, it's almost certainly here.
# =============================================================================

# --- API Server ---
API_HOST = "0.0.0.0"   # Listen on all interfaces so you can reach it from outside EC2
API_PORT = 8000

# --- How many top stocks to return ---
TOP_N_RESULTS = 5

# --- NSE F&O Stock List ---
# NSE publishes the official list of stocks with active F&O contracts.
# We cache it locally so we're not hammering NSE on every API call.
FO_LIST_URL = "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv"
FO_CACHE_FILE = "/tmp/fo_stocks_cache.csv"
FO_CACHE_TTL_HOURS = 24   # Re-download the list once a day

# --- Chartink Scanners ---
# Each entry is a named scanner with its Chartink scan clause.
# These are public, no login required.
# You can add/remove scanners here without touching any other file.
#
# How to find scan clauses:
#   1. Go to chartink.com/screener
#   2. Build a scan you like
#   3. Right-click → Inspect → Network tab → look for the POST to /screener/process
#   4. Copy the `scan_clause` from the request payload
CHARTINK_SCANNERS = {
    "volume_breakout": (
        "( {cash} ( volume > 2 * ( avg volume(20) ) "
        "and close > open "
        "and close > ( max(10, close) ) ) "
        "and [nse] )"
    ),
    "rsi_momentum": (
        "( {cash} ( [RSI(14)] >= 60 "
        "and [RSI(14)] <= 75 "
        "and close > open "
        "and volume > 1.5 * ( avg volume(20) ) ) "
        "and [nse] )"
    ),
    "ema_crossover": (
        "( {cash} ( latest ema(9,close) > latest ema(21,close) "
        "and 1 day ago ema(9,close) <= 1 day ago ema(21,close) "
        "and volume > avg volume(10) ) "
        "and [nse] )"
    ),
}

# --- Price range filter ---
# Options are generally liquid only for stocks in this price range.
# Very cheap stocks (<100) rarely have active option chains.
# Very expensive stocks (>5000) have high premium costs.
MIN_STOCK_PRICE = 100
MAX_STOCK_PRICE = 5000

# --- Scoring weights ---
# The final score is a weighted sum. Adjust these to change what matters most.
# All weights should add up to 1.0
SCORE_WEIGHTS = {
    "scanner_count": 0.40,   # How many scanners flagged this stock (more = stronger signal)
    "volume_ratio": 0.35,    # Today's volume vs 20-day average
    "price_range": 0.25,     # Is the price in a sweet spot for options liquidity
}
