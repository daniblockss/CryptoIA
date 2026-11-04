from __future__ import annotations

import time
from typing import Any

from app import firebase_store as store
from app.llm7 import ask
from app.memory import create_memory, read_memory


def check_reminders(market: dict[str, Any]) -> None:
    reminders = store.get_value("reminders", {}) or {}
    for reminder_id, reminder in reminders.items():
        if not isinstance(reminder, dict) or reminder.get("status", "active") != "active":
            continue
        symbol = str(reminder.get("symbol", "")).upper()
        quote = market.get(symbol) or {}
        try:
            price = float(quote.get("price_brl") or 0)
            target = float(reminder.get("target"))
            change = quote.get("change_24h")
        except (TypeError, ValueError):
            continue

        condition = reminder.get("condition")
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
            "Explique os dados, as incertezas e o contexto. Não recomende operações "
            "reais; a carteira é apenas simulada."
        )
        analysis = ask(prompt)
        filename = create_memory(
            f"Alerta {symbol} {int(time.time())}",
            analysis,
            "LLM7-reminder",
        )
        store.update_value(f"reminders/{reminder_id}", {
            "status": "triggered",
            "triggered_at": int(time.time()),
            "trigger_price_brl": price,
            "analysis": analysis[:5000],
            "result_memory_file": filename,
        })
        store.push_value("events", {
            "type": "reminder_triggered",
            "symbol": symbol,
            "reminder_id": reminder_id,
            "message": f"Lembrete acionado para {symbol}.",
            "analysis": analysis[:5000],
            "at": int(time.time()),
        })
