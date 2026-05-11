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

## HTTP API (Starlette)

Maps **Binance Spot** public REST paths under `/api/v1/*` (no API keys). Uses **Starlette** only (no FastAPI / Pydantic → **no `pydantic-core`**, so Render **Python 3.14** builds do not need Rust).

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

There is **no `/docs` Swagger** in this stack; call routes directly or use `GET /` for the route list.

| Route | Binance / behavior |
|-------|--------------------|
| `GET /api/v1/meta` | Service config + which upstream paths are used |
| `GET /api/v1/upstream` | Base URL + path names |
| `GET /api/v1/symbols?max=0` | `GET /api/v3/exchangeInfo` → TRADING + USDT + SPOT |
| `GET /api/v1/klines/{symbol}` | `GET /api/v3/klines` |
| `GET /api/v1/ticker/top-volume?top=50` | `GET /api/v3/ticker/24hr` → USDT, sorted by `quoteVolume` |
| `GET /api/v1/rsi/{symbol}` | klines + local Wilder RSI snapshot |
| `GET /api/v1/scan?max_symbols=80` | full scan (slow; keep `max_symbols` small on Render free) |

**Render build command (use this instead of plain `pip install` until you confirm no extra manifests):**

```bash
bash build.sh
```

`build.sh` installs `requirements.txt` and **exits with an error if Pydantic is present** (so you catch a stale `pyproject.toml` / wrong file on the service root).

If the script fails with “pydantic must not be installed”, search your **deploy root** for anything that still pins FastAPI/Pydantic:

- `requirements.txt`, `requirements-dev.txt`
- `pyproject.toml` / `poetry.lock` / `Pipfile` / `Pipfile.lock`

Render may install from **`pyproject.toml`** even when `requirements.txt` exists, depending on how the service is configured—**remove or fix** those files in the repo you actually deploy.

**Start command:** `uvicorn app:app --host 0.0.0.0 --port $PORT`

### Render build: `pydantic-core` / Rust (legacy)

This project **no longer uses Pydantic** for the web API, so **`pip install -r requirements.txt` should not compile Rust**, even on **Python 3.14**.

**Optional — Docker or Python 3.12** (if you reintroduce compiled deps later):

**Option A — Docker:** **Settings → Runtime → Docker**; use the repo **`Dockerfile`** (`python:3.12-slim-bookworm`). **Clear build cache** → deploy. Leave the dashboard **Build Command empty** for Docker (installs happen in the Dockerfile).

**Option B — Native Python 3.12:** Set **`PYTHON_VERSION=3.12.8`** and/or **`NIXPACKS_PYTHON_VERSION=3.12`**, then clear cache and redeploy.

## Notes

- Uses **public** endpoints only (no API keys).
- If Binance returns **HTTP 451** (or **403**) from your Render region, set **`BINANCE_BASE_URL`** (e.g. US: **`https://api.binance.us`**) or rely on **`BINANCE_FALLBACK_BASE_URLS`** (defaults to `api1`–`api3` mirrors; set to **`off`** to disable). **`BINANCE_MIRROR_RETRY_DELAY_S`** (default `0.35`) pauses between mirror attempts.
- **`EXCHANGE_INFO_CACHE_SECONDS`** (default `300`): cache `exchangeInfo` in memory so repeat `/api/v1/symbols` calls do not hit Binance every time (first request still needs a working IP).
- **Browser URL works but Render code fails (451/403):** the **IP is different** (your PC vs datacenter). It is not a bug in httpx vs browser. Set **`BINANCE_BASE_URL`** (e.g. **`https://api.binance.us`** for US). Optional **`BINANCE_USER_AGENT`** if a CDN only blocks the default Python UA (rare; will not fix real geo **451**).
- This is a **filtering tool**, not trading advice.
- For production scheduling on Render, run as a **Cron Job** or background worker if scans exceed HTTP timeouts.
