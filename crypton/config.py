from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Tuple


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def parse_staircase_levels_string(raw: str) -> Optional[Tuple[float, ...]]:
    """Parse '52,53,54,55' or return None for 'off' / invalid."""
    raw = raw.strip()
    if raw.lower() in ("", "off", "none", "0"):
        return None
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) < 2:
        return None
    try:
        return tuple(float(p) for p in parts)
    except ValueError:
        return None


def _parse_staircase_env() -> Optional[Tuple[float, ...]]:
    """
    STRATEGY_STAIRCASE_LEVELS default 52,53,54,55.
    Set to 'off' / empty / 'none' to use legacy RSI-min + rising rule instead.
    """
    raw = os.environ.get("STRATEGY_STAIRCASE_LEVELS", "52,53,54,55")
    return parse_staircase_levels_string(raw)


def _parse_fallback_base_urls(raw: Optional[str]) -> Tuple[str, ...]:
    """
    Extra Binance Spot REST bases to try if the primary returns 451/403 (geo / legal).
    Default: api1–api3 mirrors. Set BINANCE_FALLBACK_BASE_URLS=off to disable.
    """
    if raw is None:
        raw = "https://api1.binance.com,https://api2.binance.com,https://api3.binance.com"
    raw = raw.strip()
    if raw.lower() in ("", "off", "none", "0"):
        return ()
    parts = [p.strip().rstrip("/") for p in raw.split(",") if p.strip()]
    return tuple(parts)


@dataclass(frozen=True)
class Settings:
    """Tune scanning without code changes (env vars optional)."""

    # If false, httpx ignores HTTP(S)_PROXY env (helps when a corporate proxy blocks Binance).
    httpx_trust_env: bool = False
    base_url: str = "https://api.binance.com"
    # Tried in order after base_url when Binance returns 451/403 (see binance.py).
    binance_fallback_base_urls: Tuple[str, ...] = ()
    interval: str = "1h"
    kline_limit: int = 300
    rsi_period: int = 14
    # Minimum *closed* bars after dropping the in-progress candle
    min_bars_for_rsi: int = 60
    # Sleep between kline requests to reduce 429 risk (seconds)
    request_delay_s: float = 0.08
    # After 451/403, sleep before trying next Binance mirror (seconds).
    binance_mirror_retry_delay_s: float = 0.35
    # 0 = no cap (all symbols); else only first N after stable sort
    max_symbols: int = 0
    # If set (default 52,53,54,55): strategy = staircase strict-up on last N RSI bars.
    # If None (env STRATEGY_STAIRCASE_LEVELS=off): use strategy_rsi_min + strategy_require_rising.
    strategy_staircase_levels: Optional[Tuple[float, ...]] = None
    # Optional legacy strategy when staircase disabled
    strategy_rsi_min: float = 50.0
    strategy_require_rising: bool = True
    # If true, print every RSI-eligible symbol (not only strategy matches)
    output_all_rsi_eligible: bool = False

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            httpx_trust_env=os.environ.get("HTTPX_TRUST_ENV", "0") in ("1", "true", "True"),
            base_url=os.environ.get("BINANCE_BASE_URL", "https://api.binance.com"),
            binance_fallback_base_urls=_parse_fallback_base_urls(os.environ.get("BINANCE_FALLBACK_BASE_URLS")),
            interval=os.environ.get("BINANCE_INTERVAL", "1h"),
            kline_limit=_env_int("BINANCE_KLINE_LIMIT", 300),
            rsi_period=_env_int("RSI_PERIOD", 14),
            min_bars_for_rsi=_env_int("MIN_BARS_FOR_RSI", 60),
            request_delay_s=_env_float("REQUEST_DELAY_S", 0.08),
            binance_mirror_retry_delay_s=_env_float("BINANCE_MIRROR_RETRY_DELAY_S", 0.35),
            max_symbols=_env_int("MAX_SYMBOLS", 0),
            strategy_staircase_levels=_parse_staircase_env(),
            strategy_rsi_min=_env_float("STRATEGY_RSI_MIN", 50.0),
            strategy_require_rising=os.environ.get("STRATEGY_REQUIRE_RISING", "1")
            not in ("0", "false", "False"),
            output_all_rsi_eligible=os.environ.get("OUTPUT_ALL_RSI_ELIGIBLE", "0")
            in ("1", "true", "True"),
        )
