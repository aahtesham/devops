from __future__ import annotations

from typing import List, Optional, Tuple


def staircase_strict_up(
    rsi_series: List[Optional[float]], levels: Tuple[float, ...]
) -> Tuple[bool, List[float]]:
    """
    Last len(levels) *closed-bar* RSI values must:
    - each be >= the corresponding floor (levels[0] on oldest of window, ...),
    - strictly increase bar-to-bar (momentum 'keeps moving upward').
    """
    k = len(levels)
    if len(rsi_series) < k:
        return False, []

    window = rsi_series[-k:]
    if any(v is None for v in window):
        return False, []

    vals = [float(v) for v in window]
    for v, floor in zip(vals, levels):
        if v < floor:
            return False, vals

    for i in range(1, k):
        if vals[i] <= vals[i - 1]:
            return False, vals

    return True, vals


def legacy_rising_above(rsi_last: float, rsi_prev: float, rsi_min: float, require_rising: bool) -> bool:
    if require_rising:
        return (rsi_last > rsi_min) and (rsi_last > rsi_prev)
    return rsi_last > rsi_min
