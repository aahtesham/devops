from __future__ import annotations

import os
from dataclasses import dataclass


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


@dataclass(frozen=True)
class Settings:
    """Tune scanning without code changes (env vars optional)."""

    # If false, httpx ignores HTTP(S)_PROXY env (helps when a corporate proxy blocks Binance).
    httpx_trust_env: bool = False
    base_url: str = "https://api.binance.com"
    interval: str = "1h"
    kline_limit: int = 300
    rsi_period: int = 14
    # Minimum *closed* bars after dropping the in-progress candle
    min_bars_for_rsi: int = 60
    # Sleep between kline requests to reduce 429 risk (seconds)
    request_delay_s: float = 0.08
    # 0 = no cap (all symbols); else only first N after stable sort
    max_symbols: int = 0
    # Optional strategy filter: only include if RSI > threshold and rising
    strategy_rsi_min: float = 50.0
    strategy_require_rising: bool = True
    # If true, print every RSI-eligible symbol (not only strategy matches)
    output_all_rsi_eligible: bool = False

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            httpx_trust_env=os.environ.get("HTTPX_TRUST_ENV", "0") in ("1", "true", "True"),
            base_url=os.environ.get("BINANCE_BASE_URL", "https://api.binance.com"),
            interval=os.environ.get("BINANCE_INTERVAL", "1h"),
            kline_limit=_env_int("BINANCE_KLINE_LIMIT", 300),
            rsi_period=_env_int("RSI_PERIOD", 14),
            min_bars_for_rsi=_env_int("MIN_BARS_FOR_RSI", 60),
            request_delay_s=_env_float("REQUEST_DELAY_S", 0.08),
            max_symbols=_env_int("MAX_SYMBOLS", 0),
            strategy_rsi_min=_env_float("STRATEGY_RSI_MIN", 50.0),
            strategy_require_rising=os.environ.get("STRATEGY_REQUIRE_RISING", "1")
            not in ("0", "false", "False"),
            output_all_rsi_eligible=os.environ.get("OUTPUT_ALL_RSI_ELIGIBLE", "0")
            in ("1", "true", "True"),
        )
