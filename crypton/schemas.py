from __future__ import annotations

from typing import Any, Dict, List

from crypton.binance import BinancePublicClient


def _symbol_has_spot(row: Dict[str, Any]) -> bool:
    """
    Binance often returns `"permissions": []` and uses `permissionSets` + flags instead.
    See: https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md
    """
    if row.get("isSpotTradingAllowed") is True:
        return True
    perms = row.get("permissions") or []
    if "SPOT" in perms:
        return True
    for group in row.get("permissionSets") or []:
        if isinstance(group, (list, tuple)) and "SPOT" in group:
            return True
    return False


def fetch_spot_usdt_symbols(client: BinancePublicClient) -> List[str]:
    """
    Return Binance *spot* USDT symbols that are TRADING and spot-eligible.

    Uses: GET /api/v3/exchangeInfo (with permissions=SPOT when supported).
    """
    data: Dict[str, Any] = client.get_json(
        "/api/v3/exchangeInfo",
        params={"permissions": "SPOT"},
    )
    symbols_out: List[str] = []
    for row in data.get("symbols", []):
        if row.get("status") != "TRADING":
            continue
        if row.get("quoteAsset") != "USDT":
            continue
        if not _symbol_has_spot(row):
            continue
        sym = row.get("symbol")
        if isinstance(sym, str) and sym.endswith("USDT"):
            symbols_out.append(sym)

    symbols_out.sort()
    return symbols_out
