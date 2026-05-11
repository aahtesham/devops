# Crypton (scanner skeleton)

Python project that:

1. Loads **Binance Spot** `USDT` symbols (`TRADING` + `SPOT` permission) via `exchangeInfo`
2. Fetches **1h klines** **one symbol at a time** (with a small delay to reduce rate limits)
3. Drops the **in-progress** last candle, checks **minimum history**, computes **Wilder RSI(14)**
4. Strategy: **default** = last **4** closed RSI bars must be **≥ 52, 53, 54, 55** (floors) and **strictly increasing** each bar (`STRATEGY_STAIRCASE_LEVELS`, default `52,53,54,55`). Set `STRATEGY_STAIRCASE_LEVELS=off` to use legacy **RSI > min + rising** instead.

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

### Render build: `pydantic-core` / Rust / read-only filesystem

If the build uses **Python 3.14**, `pydantic-core` may try to **compile from source** (Rust/maturin) and fail with **read-only file system** for Cargo. Fix: use **Python 3.12.x** so pip gets **binary wheels**.

1. In the Render service: **Environment → add** `PYTHON_VERSION` = `3.12.8` (or another **3.12** patch Render supports).
2. Commit **`runtime.txt`** (`python-3.12.8`) and **`.python-version`** from this repo so the platform picks 3.12 when supported.
3. Redeploy (clear build cache if the old 3.14 venv sticks).

## Notes

- Uses **public** endpoints only (no API keys).
- If you see `httpx.ProxyError` / `403` through a corporate proxy, the default is **not** to trust `HTTP(S)_PROXY`. To force using system proxy settings: `export HTTPX_TRUST_ENV=1`.
- This is a **filtering tool**, not trading advice.
- For production scheduling on Render, run as a **Cron Job** or background worker if scans exceed HTTP timeouts.
