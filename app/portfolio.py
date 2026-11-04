from __future__ import annotations

import os
import time
from typing import Any

from app import firebase_store as store


def _money(value: Any) -> float:
    try:
        return round(float(value), 8)
    except (TypeError, ValueError):
        return 0.0


def ensure_portfolio() -> dict[str, Any]:
    portfolio = store.get_value("portfolio")
    if portfolio:
        return portfolio
    initial = max(0.0, float(os.getenv("INITIAL_SIMULATED_BRL", "10.00")))
    portfolio = {
        "mode": "SIMULATED",
        "initial_capital_brl": initial,
        "cash_brl": initial,
        "positions": {},
        "transactions": [],
        "expenses_brl": 0.0,
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
    }
    store.set_value("portfolio", portfolio)
    return portfolio


def _finish_command(command_id: str, status: str, message: str) -> None:
    store.update_value(f"commands/{command_id}", {
        "status": status, "result": message, "processed_at": int(time.time())
    })


def process_commands(market: dict[str, dict[str, Any]]) -> None:
    commands = store.get_value("commands", {}) or {}
    for command_id, command in commands.items():
        if not isinstance(command, dict) or command.get("status") != "pending":
            continue
        try:
            kind = command.get("type")
            if kind == "ask_ai":
                # The agent loop handles AI requests separately.
                continue
            portfolio = ensure_portfolio()
            cash = _money(portfolio.get("cash_brl"))
            positions = portfolio.setdefault("positions", {})
            txs = portfolio.setdefault("transactions", [])

            if kind == "buy":
                symbol = str(command.get("symbol", "")).upper()
                amount = _money(command.get("brl_amount"))
                price = _money((market.get(symbol) or {}).get("price_brl"))
                if not symbol or amount <= 0 or price <= 0:
                    raise ValueError("Moeda, valor ou cotação inválida.")
                if amount > cash:
                    raise ValueError("Saldo simulado insuficiente.")
                quantity = amount / price
                position = positions.setdefault(symbol, {"quantity": 0.0, "cost_brl": 0.0})
                position["quantity"] = _money(position["quantity"] + quantity)
                position["cost_brl"] = _money(position["cost_brl"] + amount)
                portfolio["cash_brl"] = _money(cash - amount)
                txs.append({"type": "buy", "symbol": symbol, "quantity": quantity,
                            "value_brl": amount, "price_brl": price, "at": int(time.time()),
                            "mode": "SIMULATED"})
                message = f"Compra simulada registrada: R$ {amount:.2f} em {symbol}."

            elif kind == "sell":
                symbol = str(command.get("symbol", "")).upper()
                quantity = _money(command.get("quantity"))
                price = _money((market.get(symbol) or {}).get("price_brl"))
                position = positions.get(symbol) or {}
                held = _money(position.get("quantity"))
                if quantity <= 0 or price <= 0 or quantity > held:
                    raise ValueError("Quantidade inválida ou maior que a posição simulada.")
                proceeds = quantity * price
                ratio = quantity / held if held else 0
                position["quantity"] = _money(held - quantity)
                position["cost_brl"] = _money(_money(position.get("cost_brl")) * (1 - ratio))
                portfolio["cash_brl"] = _money(cash + proceeds)
                txs.append({"type": "sell", "symbol": symbol, "quantity": quantity,
                            "value_brl": proceeds, "price_brl": price, "at": int(time.time()),
                            "mode": "SIMULATED"})
                message = f"Venda simulada registrada: {quantity:.8f} {symbol}."

            elif kind == "simulated_expense":
                amount = _money(command.get("amount_brl"))
                label = str(command.get("label") or "Despesa simulada")[:80]
                if amount <= 0 or amount > cash:
                    raise ValueError("Valor da despesa inválido ou saldo insuficiente.")
                portfolio["cash_brl"] = _money(cash - amount)
                portfolio["expenses_brl"] = _money(portfolio.get("expenses_brl", 0) + amount)
                txs.append({"type": "expense", "label": label, "value_brl": amount,
                            "at": int(time.time()), "mode": "SIMULATED"})
                message = f"Despesa simulada registrada: R$ {amount:.2f}."

            else:
                raise ValueError("Comando desconhecido.")

            portfolio["transactions"] = txs[-300:]
            portfolio["updated_at"] = int(time.time())
            store.set_value("portfolio", portfolio)
            _finish_command(command_id, "done", message)
        except Exception as exc:
            _finish_command(command_id, "error", str(exc))


def publish_valuation(market: dict[str, dict[str, Any]]) -> None:
    portfolio = ensure_portfolio()
    positions = portfolio.get("positions", {})
    market_value = 0.0
    unrealized = 0.0
    for symbol, position in positions.items():
        price = _money((market.get(symbol) or {}).get("price_brl"))
        quantity = _money(position.get("quantity"))
        value = price * quantity
        market_value += value
        unrealized += value - _money(position.get("cost_brl"))
    total = _money(portfolio.get("cash_brl")) + market_value
    portfolio.update({
        "market_value_brl": _money(market_value),
        "total_value_brl": _money(total),
        "unrealized_pnl_brl": _money(unrealized),
        "total_pnl_brl": _money(total - _money(portfolio.get("initial_capital_brl"))),
        "updated_at": int(time.time()),
    })
    store.set_value("portfolio", portfolio)
