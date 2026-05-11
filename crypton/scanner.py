from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

from crypton.binance import BinancePublicClient
from crypton.config import Settings
from crypton.rsi import wilder_rsi


@dataclass(frozen=True)
class SymbolScan:
    symbol: str
    reason: str
    rsi_eligible: bool = False
    strategy_match: bool = False
    rsi_last_closed: Optional[float] = None
    rsi_prev_closed: Optional[float] = None
    last_close: Optional[float] = None


def _klines_to_closed_closes(klines: List[List[Any]], drop_last_open: bool) -> List[float]:
    """
    Binance klines include the currently forming candle as the last row.
    For stable RSI signals, drop that in-progress bar by default.
    """
    rows = klines[:-1] if (drop_last_open and len(klines) > 0) else klines
    return [float(r[4]) for r in rows]


def scan_one_symbol(
    client: BinancePublicClient, settings: Settings, symbol: str
) -> SymbolScan:
    """
    One symbol: Binance GET /api/v3/klines → closed bars → Wilder RSI + strategy flags.
    """
    need = settings.min_bars_for_rsi
    p = settings.rsi_period

    try:
        klines: List[List[Any]] = client.get_json(
            "/api/v3/klines",
            params={
                "symbol": symbol,
                "interval": settings.interval,
                "limit": settings.kline_limit,
            },
        )
    except Exception as exc:  # noqa: BLE001
        return SymbolScan(
            symbol=symbol,
            reason=f"klines_error:{type(exc).__name__}",
            rsi_eligible=False,
            strategy_match=False,
        )

    closes = _klines_to_closed_closes(klines, drop_last_open=True)

    if len(closes) < max(need, p + 2):
        return SymbolScan(
            symbol=symbol,
            reason=f"insufficient_history:{len(closes)}<{max(need, p + 2)}",
            rsi_eligible=False,
            strategy_match=False,
        )

    if any((c is None) or (c <= 0.0) for c in closes):
        return SymbolScan(
            symbol=symbol,
            reason="invalid_close",
            rsi_eligible=False,
            strategy_match=False,
        )

    rsi_series = wilder_rsi(closes, period=p)
    rsi_last = rsi_series[-1]
    rsi_prev = rsi_series[-2]
    last_close = closes[-1]

    if rsi_last is None or rsi_prev is None:
        return SymbolScan(
            symbol=symbol,
            reason="rsi_unavailable",
            rsi_eligible=False,
            strategy_match=False,
        )

    if settings.strategy_require_rising:
        ok_strategy = (rsi_last > settings.strategy_rsi_min) and (rsi_last > rsi_prev)
    else:
        ok_strategy = rsi_last > settings.strategy_rsi_min

    return SymbolScan(
        symbol=symbol,
        reason="ok" if ok_strategy else "filtered_by_strategy",
        rsi_eligible=True,
        strategy_match=ok_strategy,
        rsi_last_closed=float(rsi_last),
        rsi_prev_closed=float(rsi_prev),
        last_close=float(last_close),
    )


def scan_symbols(
    client: BinancePublicClient, settings: Settings, symbols: List[str]
) -> List[SymbolScan]:
    """
    Fetch 1h klines one-by-one, compute RSI, apply eligibility + optional strategy filter.

    Eligibility: enough closed bars after trimming in-progress candle.
    Strategy (optional): RSI > strategy_rsi_min and rising vs previous closed bar.
    """
    results: List[SymbolScan] = []
    for symbol in symbols:
        results.append(scan_one_symbol(client, settings, symbol))
        client.sleep_between_requests()
    return results
