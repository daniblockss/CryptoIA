from __future__ import annotations

import time
from typing import Any

from app import firebase_store as store
from app.llm7 import ask
from app.memory import read_memory


def check_reminders(market: dict[str, dict[str, Any]]) -> None:
    reminders = store.get_value("reminders", {}) or {}
    for reminder_id, reminder in reminders.items():
        if not isinstance(reminder, dict) or reminder.get("status", "active") != "active":
            continue
        symbol = str(reminder.get("symbol", "")).upper()
        quote = market.get(symbol) or {}
        price = float(quote.get("price_brl") or 0)
        change = quote.get("change_24h")
        condition = reminder.get("condition")
        try:
            target = float(reminder.get("target"))
        except (TypeError, ValueError):
            continue
        triggered = (
            (condition == "price_above" and price >= target)
            or (condition == "price_below" and price > 0 and price <= target)
            or (condition == "change_above" and change is not None and float(change) >= target)
            or (condition == "change_below" and change is not None and float(change) <= target)
        )
        if not triggered:
            continue

        context = read_memory(reminder.get("memory_file"))
        prompt = (
            f"Um lembrete educacional foi acionado. Ativo: {symbol}. "
            f"Preço atual em BRL: {price}. Variação 24h: {change}. "
            f"Condição: {condition} {target}. Memória relacionada: {context[:3500]}. "
            "Explique o que os dados mostram, sem recomendar operação real. "
            "Lembre que a carteira é simulada."
        )
        analysis = ask(prompt)
        store.update_value(f"reminders/{reminder_id}", {
            "status": "triggered",
            "triggered_at": int(time.time()),
            "trigger_price_brl": price,
            "analysis": analysis[:5000],
        })
        store.push_value("events", {
            "type": "reminder_triggered",
            "symbol": symbol,
            "reminder_id": reminder_id,
            "message": f"Lembrete acionado para {symbol}.",
            "analysis": analysis[:5000],
            "at": int(time.time()),
        })
