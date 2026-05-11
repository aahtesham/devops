from __future__ import annotations

from typing import List, Optional


def wilder_rsi(closes: List[float], period: int = 14) -> List[Optional[float]]:
    """
    Wilder RSI on closing prices.

    Returns a list aligned with `closes`: first `period` values are None
    (not enough history). Later indices are RSI in [0, 100].
    """
    n = len(closes)
    rsi: List[Optional[float]] = [None] * n
    if period <= 0 or n < period + 1:
        return rsi

    changes: list[float] = [closes[i] - closes[i - 1] for i in range(1, n)]
    gains = [max(c, 0.0) for c in changes]
    losses = [max(-c, 0.0) for c in changes]

    avg_gain = sum(gains[0:period]) / period
    avg_loss = sum(losses[0:period]) / period

    def rsi_from_avgs(ag: float, al: float) -> float:
        if al == 0.0:
            return 100.0 if ag > 0.0 else 50.0
        rs = ag / al
        return 100.0 - (100.0 / (1.0 + rs))

    rsi[period] = rsi_from_avgs(avg_gain, avg_loss)

    for close_idx in range(period + 1, n):
        ch_idx = close_idx - 1
        avg_gain = (avg_gain * (period - 1) + gains[ch_idx]) / period
        avg_loss = (avg_loss * (period - 1) + losses[ch_idx]) / period
        rsi[close_idx] = rsi_from_avgs(avg_gain, avg_loss)

    return rsi
