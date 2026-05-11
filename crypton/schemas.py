from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from crypton.scanner import SymbolScan


class UpstreamMap(BaseModel):
    """Documents which Binance Spot REST paths the app calls."""

    base_url: str = Field(description="Binance Spot REST base")
    exchange_info: str = Field(default="GET /api/v3/exchangeInfo")
    klines: str = Field(default="GET /api/v3/klines")
    ticker_24h: str = Field(default="GET /api/v3/ticker/24hr")


class SymbolListResponse(BaseModel):
    upstream: UpstreamMap
    count: int
    symbols: List[str]


class KlinesResponse(BaseModel):
    upstream: str
    symbol: str
    interval: str
    count: int
    klines: List[List[Any]]


class RSISnapshotResponse(BaseModel):
    upstream: str
    symbol: str
    interval: str
    rsi_period: int
    scan: Dict[str, Any]


class ScanRow(BaseModel):
    symbol: str
    reason: str
    rsi_eligible: bool
    strategy_match: bool
    rsi_last_closed: Optional[float] = None
    rsi_prev_closed: Optional[float] = None
    last_close: Optional[float] = None


class ScanResponse(BaseModel):
    upstream: str
    interval: str
    scanned: int
    strategy_matches: int
    listed: int
    rows: List[ScanRow]
    excluded_summary: Dict[str, int]


def symbol_scan_to_row(r: SymbolScan) -> ScanRow:
    return ScanRow(
        symbol=r.symbol,
        reason=r.reason,
        rsi_eligible=r.rsi_eligible,
        strategy_match=r.strategy_match,
        rsi_last_closed=r.rsi_last_closed,
        rsi_prev_closed=r.rsi_prev_closed,
        last_close=r.last_close,
    )


class TickerTopResponse(BaseModel):
    upstream: str
    count: int
    tickers: List[Dict[str, Any]]
