# Options Scanner

On-demand swing trade scanner that returns the top 5 F&O-eligible stock ideas — triggered from your phone via a single curl call.

---

## File Structure

```
options_scanner/
├── config.py            ← All settings (prices, weights, scanner clauses)
├── fo_filter.py         ← Downloads and caches the NSE F&O stock list
├── chartink_scraper.py  ← Fetches ideas from Chartink scanners
├── scorer.py            ← Scores and ranks candidates
├── main.py              ← FastAPI app (the entry point)
└── requirements.txt
```

---

## Setup on EC2

```bash
# 1. Copy files to your EC2
scp -r options_scanner/ ec2-user@<your-ec2-ip>:~/

# 2. Install dependencies
cd ~/options_scanner
pip install -r requirements.txt

# 3. Run the server
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Run as a background service (so it survives SSH disconnect)

```bash
# Using nohup
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > scanner.log 2>&1 &

# Or using screen
screen -S scanner
uvicorn main:app --host 0.0.0.0 --port 8000
# Ctrl+A, D to detach
```

### Open port 8000 in EC2 Security Group
In the AWS console → EC2 → Security Groups → Inbound Rules:
- Type: Custom TCP, Port: 8000, Source: My IP (or 0.0.0.0/0 for access from anywhere)

---

## Usage

### Health check
```bash
curl http://<your-ec2-ip>:8000/
```

### Run analysis
```bash
curl http://<your-ec2-ip>:8000/analyze
```

### Pretty-print the JSON output (requires `jq`)
```bash
curl http://<your-ec2-ip>:8000/analyze | jq
```

### On your phone
Save this as a browser bookmark or a Shortcut:
```
http://<your-ec2-ip>:8000/analyze
```

---

## Sample Output

```json
{
  "status": "ok",
  "generated_at": "2026-01-21 10:32:45 IST",
  "elapsed_seconds": 18.3,
  "total_candidates_scanned": 47,
  "fo_eligible_count": 12,
  "top_picks": [
    {
      "rank": 1,
      "symbol": "RELIANCE",
      "price": 2450.5,
      "change_pct": "+2.30%",
      "volume_ratio": "3.2x avg volume",
      "score": 78.5,
      "scanners_hit": ["volume_breakout", "rsi_momentum"],
      "strategy_hint": "Bullish — consider ATM/OTM Call (CE)"
    },
    ...
  ]
}
```

---

## Customizing

**Add a new Chartink scanner:**
Open `config.py`, add an entry to `CHARTINK_SCANNERS`. No other file needs to change.

**Change the number of results:**
In `config.py`, change `TOP_N_RESULTS`.

**Adjust scoring weights:**
In `config.py`, tweak `SCORE_WEIGHTS`. The three values must add up to 1.0.

**Change price range filter:**
In `config.py`, change `MIN_STOCK_PRICE` and `MAX_STOCK_PRICE`.

---

## Troubleshooting

| Error | Likely Cause | Fix |
|-------|-------------|-----|
| `503 - Could not load NSE F&O list` | NSE server unreachable | Wait and retry; NSE site may be down |
| `503 - No results from Chartink` | Market closed or Chartink down | Check if market is open; retry later |
| Connection refused on curl | Server not running or port blocked | Check EC2 security group; restart uvicorn |
