from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from crypton.scanner import SymbolScan

# Binance Spot GET /api/v3/klines — each row is a fixed-order array (newest last).
# https://developers.binance.com/docs/binance-spot-api-docs/rest-api#klinecandlestick-data
BINANCE_SPOT_KLINE_ARRAY_FIELDS: Sequence[str] = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_asset_volume",
    "number_of_trades",
    "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
    "ignore",
)


def binance_kline_array_to_object(row: Sequence[Any]) -> Dict[str, Any]:
    """Map one Binance kline array row to a JSON object (keys match array index order)."""
    return {BINANCE_SPOT_KLINE_ARRAY_FIELDS[i]: row[i] for i in range(min(len(row), len(BINANCE_SPOT_KLINE_ARRAY_FIELDS)))}


def klines_arrays_to_objects(klines: List[List[Any]]) -> List[Dict[str, Any]]:
    return [binance_kline_array_to_object(row) for row in klines]


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
