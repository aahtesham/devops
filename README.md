# Crypton (scanner skeleton)

Python project that:

1. Loads **Binance Spot** `USDT` symbols (`TRADING` + `SPOT` permission) via `exchangeInfo`
2. Fetches **1h klines** **one symbol at a time** (with a small delay to reduce rate limits)
3. Drops the **in-progress** last candle, checks **minimum history**, computes **Wilder RSI(14)**
4. Builds a **list** of RSI-eligible symbols; by default prints only **strategy matches** (RSI > 50 and rising). Set `OUTPUT_ALL_RSI_ELIGIBLE=1` to print every eligible row with a `strategy=Y/N` flag.

## Setup

```bash
cd crypton
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## Safer testing (recommended)

Scanning *all* spot USDT pairs can take a long time and may hit Binance limits.

```bash
export MAX_SYMBOLS=80
export REQUEST_DELAY_S=0.12
python main.py
```

```bash
# Print every RSI-eligible symbol (still computes strategy_match for the flag)
export OUTPUT_ALL_RSI_ELIGIBLE=1
export MAX_SYMBOLS=200
python main.py
```

## HTTP API (FastAPI)

Maps **Binance Spot** public REST paths under `/api/v1/*` (no API keys).

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

| Route | Binance / behavior |
|-------|--------------------|
| `GET /api/v1/meta` | Service config + which upstream paths are used |
| `GET /api/v1/upstream` | Base URL + path names |
| `GET /api/v1/symbols?max=0` | `GET /api/v3/exchangeInfo` → TRADING + USDT + `SPOT` |
| `GET /api/v1/klines/{symbol}` | `GET /api/v3/klines` |
| `GET /api/v1/ticker/top-volume?top=50` | `GET /api/v3/ticker/24hr` → USDT, sorted by `quoteVolume` |
| `GET /api/v1/rsi/{symbol}` | klines + local Wilder RSI snapshot |
| `GET /api/v1/scan?max_symbols=80` | full scan (slow; keep `max_symbols` small on Render free) |

**Render start command:** `uvicorn app:app --host 0.0.0.0 --port $PORT`

## Notes

- Uses **public** endpoints only (no API keys).
- If you see `httpx.ProxyError` / `403` through a corporate proxy, the default is **not** to trust `HTTP(S)_PROXY`. To force using system proxy settings: `export HTTPX_TRUST_ENV=1`.
- This is a **filtering tool**, not trading advice.
- For production scheduling on Render, run as a **Cron Job** or background worker if scans exceed HTTP timeouts.
