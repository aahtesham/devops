from __future__ import annotations

from typing import Any, Dict, List

from crypton.binance import BinancePublicClient


def fetch_spot_usdt_symbols(client: BinancePublicClient) -> List[str]:
    """
    Return Binance *spot* USDT symbols that are TRADING and include SPOT permission.

    Uses: GET /api/v3/exchangeInfo
    """
    data: Dict[str, Any] = client.get_json("/api/v3/exchangeInfo")
    symbols_out: List[str] = []
    for row in data.get("symbols", []):
        if row.get("status") != "TRADING":
            continue
        if row.get("quoteAsset") != "USDT":
            continue
        perms = row.get("permissions") or []
        if "SPOT" not in perms:
            continue
        sym = row.get("symbol")
        if isinstance(sym, str) and sym.endswith("USDT"):
            symbols_out.append(sym)

    symbols_out.sort()
    return symbols_out
