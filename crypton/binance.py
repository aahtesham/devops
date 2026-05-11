from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import httpx

from crypton.config import Settings


def _dedupe_urls(urls: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for u in urls:
        u = u.rstrip("/")
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


class BinancePublicClient:
    """Minimal Binance Spot REST client (no API key). Retries alternate bases on 451/403."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        bases = [settings.base_url.rstrip("/")] + [u.rstrip("/") for u in settings.binance_fallback_base_urls]
        self._bases = _dedupe_urls(bases)
        if not self._bases:
            self._bases = ["https://api.binance.com"]
        self._base_idx = 0
        self._client = self._new_client()

    def _new_client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self._bases[self._base_idx],
            timeout=30.0,
            trust_env=self._settings.httpx_trust_env,
        )

    def _advance_base(self) -> bool:
        if self._base_idx + 1 >= len(self._bases):
            return False
        self._client.close()
        self._base_idx += 1
        self._client = self._new_client()
        return True

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BinancePublicClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        GET JSON; on HTTP 451/403 (common geo / regulatory block), try next configured base URL.
        """
        params = params or {}
        last_err: Optional[httpx.HTTPStatusError] = None
        for attempt in range(len(self._bases)):
            r = self._client.get(path, params=params)
            if r.status_code in (451, 403):
                try:
                    r.raise_for_status()
                except httpx.HTTPStatusError as e:
                    last_err = e
                if self._advance_base():
                    continue
                if last_err:
                    raise last_err
                raise RuntimeError("Binance returned 451/403 with no stored error")
            r.raise_for_status()
            return r.json()
        if last_err:
            raise last_err
        raise RuntimeError("BinancePublicClient: no bases configured")

    def sleep_between_requests(self) -> None:
        time.sleep(self._settings.request_delay_s)
