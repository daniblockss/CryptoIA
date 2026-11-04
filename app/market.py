from __future__ import annotations

import os
import time
from typing import Any

import requests

BB_BASE = "https://brasilbitcoin.com.br/api/v2"
CMC_BASE = "https://pro-api.coinmarketcap.com"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "CryptoIA-Educational-Simulator/1.0"})


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        data = payload.get("data", payload)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            if isinstance(data.get("data"), list):
                return [x for x in data["data"] if isinstance(x, dict)]
            return [v for v in data.values() if isinstance(v, dict)]
    return []


def _number(value: Any) -> float | None:
    try:
        n = float(str(value).replace(",", "."))
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def _change(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def brasil_bitcoin_tickers() -> dict[str, dict[str, Any]]:
    response = SESSION.get(f"{BB_BASE}/ticker24h", timeout=15)
    response.raise_for_status()
    rows = _rows(response.json())
    found: dict[str, dict[str, Any]] = {}
    for row in rows:
        pair = str(row.get("market") or row.get("symbol") or row.get("pair") or "").upper()
        if not pair.endswith("BRL"):
            continue
        symbol = pair[:-3]
        price = None
        for key in ("lastPrice", "last", "price", "close", "last_price"):
            price = _number(row.get(key))
            if price:
                break
        if not price:
            continue
        found[symbol] = {
            "symbol": symbol,
            "price_brl": price,
            "change_24h": _change(row.get("priceChangePercent") if row.get("priceChangePercent") is not None else row.get("changePercent") if row.get("changePercent") is not None else row.get("change_24h")),
            "source": "Brasil Bitcoin",
            "updated_at": int(time.time()),
        }
    return found


def coinmarketcap_quotes(symbols: list[str]) -> dict[str, dict[str, Any]]:
    symbols = [s.upper() for s in symbols if s]
    if not symbols:
        return {}
    api_key = os.getenv("CMC_API_KEY", "").strip()
    if api_key:
        url = f"{CMC_BASE}/v3/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": api_key}
        params = {"symbol": ",".join(symbols), "convert": "BRL", "skip_invalid": "true"}
    else:
        # CoinMarketCap documents this public endpoint as keyless.
        url = f"{CMC_BASE}/public-api/v2/simple/price"
        headers = {}
        params = {"symbol": ",".join(symbols), "convert": "BRL"}

    response = SESSION.get(url, params=params, headers=headers, timeout=20)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data", [])
    result: dict[str, dict[str, Any]] = {}

    if isinstance(data, dict):
        iterable = list(data.values())
    elif isinstance(data, list):
        iterable = data
    else:
        iterable = []

    for coin in iterable:
        if not isinstance(coin, dict):
            continue
        symbol = str(coin.get("symbol", "")).upper()
        if not symbol:
            continue
        quote = coin.get("quote", {})
        brl = quote.get("BRL", {}) if isinstance(quote, dict) else {}
        price = _number(brl.get("price")) if isinstance(brl, dict) else None
        change = _change(brl.get("percent_change_24h")) if isinstance(brl, dict) else None

        # Keyless simple-price response variants
        if not price:
            price = _number(coin.get("price") or coin.get("price_brl"))
        if price:
            result[symbol] = {
                "symbol": symbol,
                "price_brl": price,
                "change_24h": change,
                "source": "CoinMarketCap",
                "updated_at": int(time.time()),
            }
    return result


def fetch_market(symbols: list[str]) -> dict[str, dict[str, Any]]:
    market: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    try:
        market.update(brasil_bitcoin_tickers())
    except Exception as exc:
        errors.append(f"Brasil Bitcoin: {type(exc).__name__}: {exc}")

    missing = [s for s in symbols if s.upper() not in market]
    try:
        market.update(coinmarketcap_quotes(missing or symbols))
    except Exception as exc:
        errors.append(f"CoinMarketCap: {type(exc).__name__}: {exc}")

    if errors:
        market["_meta"] = {
            "errors": errors,
            "updated_at": int(time.time()),
        }
    return market
