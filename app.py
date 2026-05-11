"""
Starlette HTTP API (no Pydantic / no pydantic-core → no Rust build on Render).

Run locally:
  uvicorn app:app --reload --host 127.0.0.1 --port 8000

Render:
  uvicorn app:app --host 0.0.0.0 --port $PORT
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, List, Optional

import httpx
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from crypton.binance import BinancePublicClient
from crypton.config import Settings, parse_staircase_levels_string
from crypton.scanner import scan_one_symbol, scan_symbols
from crypton.schemas import (
    BINANCE_SPOT_KLINE_ARRAY_FIELDS,
    klines_arrays_to_objects,
    symbol_scan_to_dict,
    upstream_map_dict,
)
from crypton.symbols import fetch_spot_usdt_symbols


def _json(data: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(data, status_code=status_code)


def _parse_int(
    qp: Any, key: str, default: Optional[int], *, min_v: Optional[int] = None, max_v: Optional[int] = None
) -> int:
    raw = qp.get(key)
    if raw is None or raw == "":
        if default is None:
            raise ValueError(f"missing {key}")
        return default
    n = int(raw)
    if min_v is not None and n < min_v:
        raise ValueError(f"{key} must be >= {min_v}")
    if max_v is not None and n > max_v:
        raise ValueError(f"{key} must be <= {max_v}")
    return n


def _parse_float(qp: Any, key: str, default: Optional[float]) -> Optional[float]:
    raw = qp.get(key)
    if raw is None or raw == "":
        return default
    return float(raw)


def _parse_bool(qp: Any, key: str, default: bool) -> bool:
    raw = qp.get(key)
    if raw is None or raw == "":
        return default
    return raw.lower() in ("1", "true", "yes", "on")


def _public_origin(request: Request) -> str:
    """No trailing slash — safe to concatenate ``/path``."""
    return str(request.base_url).rstrip("/")


class DedupeSlashMiddleware(BaseHTTPMiddleware):
    """Turn ``//api/v1/...`` (double slash) into ``/api/v1/...`` so routes match."""

    async def dispatch(self, request: Request, call_next):
        p = request.url.path
        if "//" in p:
            fixed = "/" + "/".join(segment for segment in p.split("/") if segment)
            request.scope["path"] = fixed
        return await call_next(request)


def _norm_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if not s.endswith("USDT") or len(s) < 6:
        raise ValueError("symbol must look like BTCUSDT (spot USDT pair)")
    return s


def health(request: Request) -> JSONResponse:
    return _json({"status": "ok"})


def meta(request: Request) -> JSONResponse:
    s = Settings.from_env()
    return _json(
        {
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
            "klines_endpoint": {
                "path": "GET /api/v1/klines/{symbol}",
                "query": {
                    "interval": "Binance interval (default from env BINANCE_INTERVAL)",
                    "limit": "2..1000 (default 300)",
                    "format": "array | objects — array mirrors Binance; objects use kline_array_field_order keys",
                },
                "kline_array_field_order": list(BINANCE_SPOT_KLINE_ARRAY_FIELDS),
                "scan_row_fields": [
                    "symbol",
                    "reason",
                    "rsi_eligible",
                    "strategy_match",
                    "rsi_last_closed",
                    "rsi_prev_closed",
                    "last_close",
                    "rsi_staircase_window",
                ],
            },
        }
    )


def upstream(request: Request) -> JSONResponse:
    s = Settings.from_env()
    return _json(upstream_map_dict(s.base_url))


def api_symbols(request: Request) -> JSONResponse:
    try:
        max_n = _parse_int(request.query_params, "max", 0, min_v=0)
    except ValueError as e:
        return _json({"detail": str(e)}, 400)
    s = Settings.from_env()
    try:
        with BinancePublicClient(s) as client:
            symbols = fetch_spot_usdt_symbols(client)
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        return _json(
            {
                "detail": f"Binance HTTP {code} from Render/server IP (your browser can still work from home).",
                "binance_url": str(e.request.url),
                "hint_451_403": "Set Render env BINANCE_BASE_URL (e.g. https://api.binance.us for US). Mirrors retry with a short delay.",
            },
            502,
        )
    if max_n > 0:
        symbols = symbols[:max_n]
    return _json(
        {
            "upstream": upstream_map_dict(s.base_url),
            "count": len(symbols),
            "symbols": symbols,
        }
    )


def api_klines(request: Request) -> JSONResponse:
    symbol = request.path_params["symbol"]
    qp = request.query_params
    try:
        sym = _norm_symbol(symbol)
        interval = qp.get("interval") or "1h"
        limit = _parse_int(qp, "limit", 300, min_v=2, max_v=1000)
        fmt = (qp.get("format") or "array").strip().lower()
        if fmt not in ("array", "objects"):
            raise ValueError("format must be 'array' or 'objects'")
    except ValueError as e:
        return _json({"detail": str(e)}, 400)
    s = replace(Settings.from_env(), interval=interval, kline_limit=limit)
    with BinancePublicClient(s) as client:
        klines = client.get_json(
            "/api/v3/klines",
            params={"symbol": sym, "interval": s.interval, "limit": limit},
        )
    payload_klines: Any = klines
    if fmt == "objects":
        payload_klines = klines_arrays_to_objects(klines)
    return _json(
        {
            "upstream": upstream_map_dict(s.base_url),
            "symbol": sym,
            "interval": interval,
            "limit": limit,
            "format": fmt,
            "kline_array_field_order": list(BINANCE_SPOT_KLINE_ARRAY_FIELDS),
            "count": len(klines),
            "klines": payload_klines,
        }
    )


def api_ticker_top_volume(request: Request) -> JSONResponse:
    try:
        top = _parse_int(request.query_params, "top", 50, min_v=1, max_v=500)
    except ValueError as e:
        return _json({"detail": str(e)}, 400)
    s = Settings.from_env()
    with BinancePublicClient(s) as client:
        tickers: List[Dict[str, Any]] = client.get_json("/api/v3/ticker/24hr")
    usdt = [t for t in tickers if str(t.get("symbol", "")).endswith("USDT")]
    try:
        usdt.sort(key=lambda t: float(t.get("quoteVolume", 0.0)), reverse=True)
    except (TypeError, ValueError):
        usdt.sort(key=lambda t: str(t.get("quoteVolume", "0")), reverse=True)
    usdt = usdt[:top]
    return _json(
        {
            "upstream": f"{s.base_url}/api/v3/ticker/24hr",
            "count": len(usdt),
            "tickers": usdt,
        }
    )


def api_rsi_snapshot(request: Request) -> JSONResponse:
    symbol = request.path_params["symbol"]
    qp = request.query_params
    try:
        sym = _norm_symbol(symbol)
    except ValueError as e:
        return _json({"detail": str(e)}, 400)
    base = Settings.from_env()
    s = base
    if qp.get("staircase") is not None:
        s = replace(base, strategy_staircase_levels=parse_staircase_levels_string(qp["staircase"]))
    with BinancePublicClient(s) as client:
        row = scan_one_symbol(client, s, sym)
    return _json(
        {
            "upstream": f"{s.base_url}/api/v3/klines + local RSI",
            "symbol": sym,
            "interval": s.interval,
            "rsi_period": s.rsi_period,
            "scan": symbol_scan_to_dict(row),
        }
    )


def api_scan(request: Request) -> JSONResponse:
    qp = request.query_params
    try:
        max_symbols = _parse_int(qp, "max_symbols", 80, min_v=1, max_v=500)
        output_all = _parse_bool(qp, "output_all", False)
        request_delay_s = _parse_float(qp, "request_delay_s", None)
        if request_delay_s is not None and (request_delay_s < 0.0 or request_delay_s > 2.0):
            raise ValueError("request_delay_s must be between 0 and 2")
    except ValueError as e:
        return _json({"detail": str(e)}, 400)

    base = Settings.from_env()
    s = replace(
        base,
        max_symbols=max_symbols,
        output_all_rsi_eligible=output_all or base.output_all_rsi_eligible,
    )
    if request_delay_s is not None:
        s = replace(s, request_delay_s=float(request_delay_s))
    if qp.get("staircase") is not None:
        s = replace(s, strategy_staircase_levels=parse_staircase_levels_string(qp["staircase"]))

    with BinancePublicClient(s) as client:
        symbols = fetch_spot_usdt_symbols(client)
        symbols = symbols[: s.max_symbols] if s.max_symbols > 0 else symbols
        rows = scan_symbols(client, s, symbols)

    listed = [r for r in rows if r.rsi_eligible and (r.strategy_match or s.output_all_rsi_eligible)]
    listed.sort(key=lambda r: (r.rsi_last_closed or 0.0), reverse=True)
    strategy_hits = sum(1 for r in rows if r.rsi_eligible and r.strategy_match)

    reasons: Dict[str, int] = {}
    for r in rows:
        if r.rsi_eligible:
            continue
        key = r.reason.split(":", 1)[0]
        reasons[key] = reasons.get(key, 0) + 1

    return _json(
        {
            "upstream": f"{s.base_url}/api/v3/exchangeInfo + /api/v3/klines",
            "interval": s.interval,
            "symbols_in_universe": len(symbols),
            "scanned": len(rows),
            "strategy_matches": strategy_hits,
            "listed": len(listed),
            "rows": [symbol_scan_to_dict(r) for r in listed],
            "excluded_summary": reasons,
            "strategy_staircase_levels": list(s.strategy_staircase_levels)
            if s.strategy_staircase_levels
            else None,
        }
    )


def root(request: Request) -> JSONResponse:
    o = _public_origin(request)
    rel = [
        "/health",
        "/api/v1/meta",
        "/api/v1/upstream",
        "/api/v1/symbols?max=10",
        "/api/v1/klines/BTCUSDT?interval=1h&limit=50&format=array",
        "/api/v1/klines/BTCUSDT?interval=1h&limit=50&format=objects",
        "/api/v1/ticker/top-volume?top=20",
        "/api/v1/rsi/BTCUSDT",
        "/api/v1/scan?max_symbols=15",
    ]
    return _json(
        {
            "service": "crypton",
            "framework": "starlette",
            "note": "Use paths with a single leading slash. Copy from full_urls to avoid //api typos.",
            "paths_relative": rel,
            "full_urls": [f"{o}{p}" for p in rel],
        }
    )


routes = [
    Route("/health", health, methods=["GET"]),
    Route("/api/v1/meta", meta, methods=["GET"]),
    Route("/api/v1/upstream", upstream, methods=["GET"]),
    Route("/api/v1/symbols", api_symbols, methods=["GET"]),
    Route("/api/v1/klines/{symbol}", api_klines, methods=["GET"]),
    Route("/api/v1/ticker/top-volume", api_ticker_top_volume, methods=["GET"]),
    Route("/api/v1/rsi/{symbol}", api_rsi_snapshot, methods=["GET"]),
    Route("/api/v1/scan", api_scan, methods=["GET"]),
    Route("/", root, methods=["GET"]),
]

app = Starlette(
    routes=routes,
    middleware=[Middleware(DedupeSlashMiddleware)],
)
