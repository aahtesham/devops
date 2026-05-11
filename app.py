"""
FastAPI: HTTP mapping to Binance Spot public APIs + RSI scanner.

Run locally:
  uvicorn app:app --reload --host 0.0.0.0 --port 8000

Render start command:
  uvicorn app:app --host 0.0.0.0 --port $PORT
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query

from crypton.binance import BinancePublicClient
from crypton.config import Settings, parse_staircase_levels_string
from crypton.scanner import scan_one_symbol, scan_symbols
from crypton.schemas import (
    KlinesResponse,
    RSISnapshotResponse,
    ScanResponse,
    ScanRow,
    SymbolListResponse,
    TickerTopResponse,
    UpstreamMap,
    symbol_scan_to_row,
)
from crypton.symbols import fetch_spot_usdt_symbols

app = FastAPI(title="Crypton", version="0.1.0", description="Binance Spot public data + RSI scan")


def _settings(
    max_symbols: Optional[int] = None,
    output_all_rsi_eligible: Optional[bool] = None,
    request_delay_s: Optional[float] = None,
) -> Settings:
    s = Settings.from_env()
    kwargs: Dict[str, Any] = {}
    if max_symbols is not None:
        kwargs["max_symbols"] = max_symbols
    if output_all_rsi_eligible is not None:
        kwargs["output_all_rsi_eligible"] = output_all_rsi_eligible
    if request_delay_s is not None:
        kwargs["request_delay_s"] = request_delay_s
    return replace(s, **kwargs) if kwargs else s


def _norm_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if not s.endswith("USDT") or len(s) < 6:
        raise HTTPException(
            status_code=400,
            detail="symbol must look like BTCUSDT (spot USDT pair)",
        )
    return s


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/meta")
def meta() -> Dict[str, Any]:
    s = Settings.from_env()
    return {
        "service": "crypton",
        "binance_spot_base_url": s.base_url,
        "mapped_paths": {
            "symbols": "GET /api/v3/exchangeInfo → filtered TRADING + USDT + SPOT",
            "klines": "GET /api/v3/klines",
            "ticker_24h": "GET /api/v3/ticker/24hr",
        },
        "scanner": {
            "interval_default": s.interval,
            "rsi_period": s.rsi_period,
            "min_bars_for_rsi": s.min_bars_for_rsi,
            "strategy_staircase_levels": list(s.strategy_staircase_levels)
            if s.strategy_staircase_levels
            else None,
            "strategy_legacy": {
                "rsi_min": s.strategy_rsi_min,
                "require_rising": s.strategy_require_rising,
            },
        },
    }


@app.get("/api/v1/upstream", response_model=UpstreamMap)
def upstream_map() -> UpstreamMap:
    s = Settings.from_env()
    return UpstreamMap(base_url=s.base_url)


@app.get("/api/v1/symbols", response_model=SymbolListResponse)
def api_symbols(
    max: int = Query(0, ge=0, description="0 = return all; else cap list after sort"),
) -> SymbolListResponse:
    s = Settings.from_env()
    with BinancePublicClient(s) as client:
        symbols = fetch_spot_usdt_symbols(client)
    if max > 0:
        symbols = symbols[:max]
    return SymbolListResponse(
        upstream=UpstreamMap(base_url=s.base_url),
        count=len(symbols),
        symbols=symbols,
    )


@app.get("/api/v1/klines/{symbol}", response_model=KlinesResponse)
def api_klines(
    symbol: str,
    interval: str = Query("1h", description="Binance kline interval, e.g. 1h, 4h, 1d"),
    limit: int = Query(300, ge=2, le=1000),
) -> KlinesResponse:
    sym = _norm_symbol(symbol)
    s = replace(Settings.from_env(), interval=interval, kline_limit=limit)
    with BinancePublicClient(s) as client:
        klines = client.get_json(
            "/api/v3/klines",
            params={"symbol": sym, "interval": s.interval, "limit": limit},
        )
    return KlinesResponse(
        upstream=f"{s.base_url}/api/v3/klines",
        symbol=sym,
        interval=interval,
        count=len(klines),
        klines=klines,
    )


@app.get("/api/v1/ticker/top-volume", response_model=TickerTopResponse)
def api_ticker_top_volume(
    top: int = Query(50, ge=1, le=500),
) -> TickerTopResponse:
    s = Settings.from_env()
    with BinancePublicClient(s) as client:
        tickers: List[Dict[str, Any]] = client.get_json("/api/v3/ticker/24hr")
    usdt = [t for t in tickers if str(t.get("symbol", "")).endswith("USDT")]
    try:
        usdt.sort(key=lambda t: float(t.get("quoteVolume", 0.0)), reverse=True)
    except (TypeError, ValueError):
        usdt.sort(key=lambda t: str(t.get("quoteVolume", "0")), reverse=True)
    usdt = usdt[:top]
    return TickerTopResponse(
        upstream=f"{s.base_url}/api/v3/ticker/24hr",
        count=len(usdt),
        tickers=usdt,
    )


@app.get("/api/v1/rsi/{symbol}", response_model=RSISnapshotResponse)
def api_rsi_snapshot(
    symbol: str,
    staircase: Optional[str] = Query(
        None,
        description="Override staircase e.g. 52,53,54,55; omit uses env. Use 'off' for legacy RSI rule.",
    ),
) -> RSISnapshotResponse:
    sym = _norm_symbol(symbol)
    base = Settings.from_env()
    s = base
    if staircase is not None:
        s = replace(base, strategy_staircase_levels=parse_staircase_levels_string(staircase))
    with BinancePublicClient(s) as client:
        row = scan_one_symbol(client, s, sym)
    payload = symbol_scan_to_row(row).model_dump()
    return RSISnapshotResponse(
        upstream=f"{s.base_url}/api/v3/klines + local RSI",
        symbol=sym,
        interval=s.interval,
        rsi_period=s.rsi_period,
        scan=payload,
    )


@app.get("/api/v1/scan", response_model=ScanResponse)
def api_scan(
    max_symbols: int = Query(80, ge=1, le=500, description="How many symbols to scan (rate limits)"),
    output_all: bool = Query(
        False,
        description="If true, list every RSI-eligible row with strategy_match flag; else only strategy matches + eligible rows per env OUTPUT_ALL_RSI_ELIGIBLE",
    ),
    request_delay_s: Optional[float] = Query(
        None,
        ge=0.0,
        le=2.0,
        description="Override delay between kline calls (seconds)",
    ),
    staircase: Optional[str] = Query(
        None,
        description="e.g. 52,53,54,55 overrides env for this request; 'off' = legacy RSI>min rising",
    ),
) -> ScanResponse:
    base = Settings.from_env()
    s = replace(
        base,
        max_symbols=max_symbols,
        output_all_rsi_eligible=output_all or base.output_all_rsi_eligible,
    )
    if request_delay_s is not None:
        s = replace(s, request_delay_s=float(request_delay_s))
    if staircase is not None:
        s = replace(s, strategy_staircase_levels=parse_staircase_levels_string(staircase))

    with BinancePublicClient(s) as client:
        symbols = fetch_spot_usdt_symbols(client)
        symbols = symbols[: s.max_symbols] if s.max_symbols > 0 else symbols
        rows = scan_symbols(client, s, symbols)

    listed = [
        r
        for r in rows
        if r.rsi_eligible and (r.strategy_match or s.output_all_rsi_eligible)
    ]
    listed.sort(key=lambda r: (r.rsi_last_closed or 0.0), reverse=True)
    strategy_hits = sum(1 for r in rows if r.rsi_eligible and r.strategy_match)

    reasons: Dict[str, int] = {}
    for r in rows:
        if r.rsi_eligible:
            continue
        key = r.reason.split(":", 1)[0]
        reasons[key] = reasons.get(key, 0) + 1

    return ScanResponse(
        upstream=f"{s.base_url}/api/v3/exchangeInfo + /api/v3/klines",
        interval=s.interval,
        symbols_in_universe=len(symbols),
        scanned=len(rows),
        strategy_matches=strategy_hits,
        listed=len(listed),
        rows=[symbol_scan_to_row(r) for r in listed],
        excluded_summary=reasons,
        strategy_staircase_levels=list(s.strategy_staircase_levels)
        if s.strategy_staircase_levels
        else None,
    )


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "service": "crypton",
        "docs": "/docs",
        "health": "/health",
        "endpoints": [
            "GET /api/v1/meta",
            "GET /api/v1/upstream",
            "GET /api/v1/symbols?max=0",
            "GET /api/v1/klines/{symbol}?interval=1h&limit=300",
            "GET /api/v1/ticker/top-volume?top=50",
            "GET /api/v1/rsi/{symbol}",
            "GET /api/v1/scan?max_symbols=80&output_all=false&staircase=52,53,54,55",
        ],
    }
