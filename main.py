# =============================================================================
# main.py — FastAPI application entry point
#
# Run this on your EC2:
#   uvicorn main:app --host 0.0.0.0 --port 8000
#
# Then trigger from your phone:
#   curl http://<your-ec2-ip>:8000/analyze
#
# Endpoints:
#   GET /           → Health check, confirms server is alive
#   GET /analyze    → Run full analysis, returns top 5 F&O stock ideas
# =============================================================================

import logging
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from config import TOP_N_RESULTS
from chartink_scraper import fetch_all_scanner_results, aggregate_scanner_results
from fo_filter import get_fo_symbols, filter_to_fo_stocks
from scorer import rank_and_select, build_strategy_hint

# ---------------------------------------------------------------------------
# Logging setup — logs appear in your terminal / EC2 systemd journal
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App initialization
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Options Scanner",
    description="On-demand swing trade idea scanner — F&O stocks only",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def health_check():
    """Quick ping to confirm the server is running."""
    return {"status": "ok", "message": "Options scanner is alive"}


@app.get("/analyze")
def analyze():
    """
    Main endpoint. When called, it:
      1. Fetches swing trade ideas from Chartink scanners
      2. Filters to only F&O-eligible stocks (those with option chains)
      3. Scores and ranks candidates
      4. Returns the top N as clean JSON

    Typical response time: 15–30 seconds
    """
    started_at = datetime.now()
    logger.info("=== Analysis triggered ===")

    # ------------------------------------------------------------------
    # Step 1: Get F&O-eligible symbols from NSE
    # ------------------------------------------------------------------
    fo_symbols = get_fo_symbols()
    if not fo_symbols:
        # If we can't load the F&O list, we can't guarantee option chain availability
        raise HTTPException(
            status_code=503,
            detail="Could not load NSE F&O list. Try again in a minute."
        )

    # ------------------------------------------------------------------
    # Step 2: Run all Chartink scanners and aggregate results
    # ------------------------------------------------------------------
    raw_results = fetch_all_scanner_results()

    # Check if all scanners failed (likely a network/Chartink issue)
    total_stocks_found = sum(len(v) for v in raw_results.values())
    if total_stocks_found == 0:
        raise HTTPException(
            status_code=503,
            detail="No results from Chartink scanners. Chartink may be down or market may be closed."
        )

    aggregated = aggregate_scanner_results(raw_results)

    # ------------------------------------------------------------------
    # Step 3: Keep only stocks that have F&O contracts
    # ------------------------------------------------------------------
    fo_eligible_symbols = filter_to_fo_stocks(list(aggregated.keys()), fo_symbols)

    if not fo_eligible_symbols:
        return JSONResponse(content={
            "status": "no_results",
            "message": "Scanners returned results but none are F&O eligible. Try again later.",
            "generated_at": started_at.isoformat(),
        })

    # Rebuild the dict to only include F&O eligible stocks
    fo_stocks = {s: aggregated[s] for s in fo_eligible_symbols}

    # ------------------------------------------------------------------
    # Step 4: Score, rank, and pick the top N
    # ------------------------------------------------------------------
    top_stocks = rank_and_select(fo_stocks)

    # ------------------------------------------------------------------
    # Step 5: Format the output cleanly
    # ------------------------------------------------------------------
    results = []
    for rank, stock in enumerate(top_stocks, start=1):
        results.append({
            "rank":          rank,
            "symbol":        stock["symbol"],
            "price":         stock["close"],
            "change_pct":    f"{stock['change_pct']:+.2f}%",
            "volume_ratio":  f"{stock['volume_ratio']:.1f}x avg volume",
            "score":         stock["score"],
            "scanners_hit":  stock["scanners_hit"],
            "strategy_hint": build_strategy_hint(stock),
        })

    elapsed_seconds = (datetime.now() - started_at).total_seconds()

    response = {
        "status": "ok",
        "generated_at": started_at.strftime("%Y-%m-%d %H:%M:%S IST"),
        "elapsed_seconds": round(elapsed_seconds, 1),
        "total_candidates_scanned": len(aggregated),
        "fo_eligible_count": len(fo_stocks),
        "top_picks": results,
    }

    logger.info(f"=== Analysis complete in {elapsed_seconds:.1f}s ===")
    return JSONResponse(content=response)
