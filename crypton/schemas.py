from __future__ import annotations

from typing import Any, Dict, Optional

from crypton.scanner import SymbolScan


def symbol_scan_to_dict(r: SymbolScan) -> Dict[str, Any]:
    return {
        "symbol": r.symbol,
        "reason": r.reason,
        "rsi_eligible": r.rsi_eligible,
        "strategy_match": r.strategy_match,
        "rsi_last_closed": r.rsi_last_closed,
        "rsi_prev_closed": r.rsi_prev_closed,
        "last_close": r.last_close,
        "rsi_staircase_window": r.rsi_staircase_window,
    }


def upstream_map_dict(base_url: str) -> Dict[str, Any]:
    return {
        "base_url": base_url,
        "exchange_info": "GET /api/v3/exchangeInfo",
        "klines": "GET /api/v3/klines",
        "ticker_24h": "GET /api/v3/ticker/24hr",
    }
