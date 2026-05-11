from __future__ import annotations

import time
from typing import Any, Dict, Optional

import httpx

from crypton.config import Settings


class BinancePublicClient:
    """Minimal Binance Spot REST client (no API key)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.Client(
            base_url=settings.base_url,
            timeout=30.0,
            trust_env=settings.httpx_trust_env,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BinancePublicClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        r = self._client.get(path, params=params or {})
        r.raise_for_status()
        return r.json()

    def sleep_between_requests(self) -> None:
        time.sleep(self._settings.request_delay_s)
