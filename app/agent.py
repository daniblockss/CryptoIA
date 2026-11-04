from __future__ import annotations

import json
import logging
import os
import time

from dotenv import load_dotenv

from app import firebase_store as store
from app.llm7 import ask
from app.market import fetch_market
from app.memory import create_memory
from app.portfolio import ensure_portfolio, process_commands, publish_valuation
from app.reminders import check_reminders

load_dotenv()
log = logging.getLogger("cryptoia.agent")
ALLOWED_CONDITIONS = {"price_above", "price_below", "change_above", "change_below"}


def _handle_ai_requests(market: dict) -> None:
    commands = store.get_value("commands", {}) or {}
    for command_id, command in commands.items():
        if not isinstance(command, dict) or command.get("type") != "ask_ai" or command.get("status") != "pending":
            continue
        portfolio = store.get_value("portfolio", {}) or {}
        prompt = (
            "Analise este snapshot educacional. Mercado: " + json.dumps(market, ensure_ascii=False)[:4500]
            + ". Carteira simulada: " + json.dumps(portfolio, ensure_ascii=False)[:2500]
            + ". Retorne APENAS um JSON com este formato: "
            '{"analysis":"texto","memory_title":"título curto","memory_body":"nota para memória",'
            '"reminder_suggestions":[{"symbol":"BTC","condition":"price_above","target":123.45,"reason":"motivo"}]}. '
            "Sugira no máximo duas condições de alerta para observar os dados. "
            "Os alertas podem ser ativados automaticamente, mas nunca executam ordens. "
            "Não dê recomendação de compra/venda real, não prometa lucro e destaque incertezas."
        )
        raw = ask(
            prompt,
            system="Você é o analista educacional do CryptoIA. Carteira e operações são apenas simuladas.",
            json_mode=True,
        )
        try:
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError("JSON não é objeto")
        except (json.JSONDecodeError, ValueError):
            result = {"analysis": raw, "memory_title": "Análise CryptoIA",
                      "memory_body": raw, "reminder_suggestions": []}

        analysis = str(result.get("analysis") or raw)[:5000]
        title = str(result.get("memory_title") or "Memória CryptoIA")[:100]
        body = str(result.get("memory_body") or analysis)[:6000]
        memory_file = create_memory(title, body, "LLM7")

        suggestions = result.get("reminder_suggestions", [])
        if isinstance(suggestions, list):
            for suggestion in suggestions[:2]:
                if not isinstance(suggestion, dict):
                    continue
                symbol = str(suggestion.get("symbol", "")).upper()
                condition = suggestion.get("condition")
                quote = market.get(symbol) or {}
                try:
                    target = float(suggestion.get("target"))
                    current = float(quote.get("price_brl") or 0)
                except (TypeError, ValueError):
                    continue
                if symbol not in market or condition not in ALLOWED_CONDITIONS or target <= 0:
                    continue
                # Reject implausibly distant model-generated price alerts.
                if condition.startswith("price_") and (current <= 0 or not current * 0.5 <= target <= current * 2):
                    continue
                if condition.startswith("change_") and not -50 <= target <= 50:
                    continue
                store.push_value("reminders", {
                    "symbol": symbol,
                    "condition": condition,
                    "target": target,
                    "reason": str(suggestion.get("reason") or "")[:500],
                    "memory_file": memory_file,
                    "status": "active",
                    "source": "LLM7",
                    "created_at": int(time.time()),
                })

        store.update_value(f"commands/{command_id}", {
            "status": "done", "result": analysis, "memory_file": memory_file,
            "processed_at": int(time.time())
        })
        store.push_value("events", {
            "type": "ai_analysis", "message": analysis, "at": int(time.time())
        })


def run() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(message)s")
    symbols = [s.strip().upper() for s in os.getenv("MARKET_ASSETS", "BTC,ETH,SOL").split(",") if s.strip()]
    refresh = max(30, int(os.getenv("MARKET_REFRESH_SECONDS", "90")))
    ensure_portfolio()
    log.info("CryptoIA ativo em modo simulado. Ativos: %s", ", ".join(symbols))

    while True:
        try:
            market = fetch_market(symbols)
            market["updated_at"] = int(time.time())
            store.set_value("market", market)
            process_commands(market)
            _handle_ai_requests(market)
            check_reminders(market)
            publish_valuation(market)
            store.server_status("online", {
                "last_cycle_at": int(time.time()),
                "market_sources": ["Brasil Bitcoin", "CoinMarketCap"],
                "mode": "SIMULATED",
            })
            log.info("Ciclo concluído. %s ativos.", len([x for x in market if x != "_meta"]))
        except Exception:
            log.exception("Falha no ciclo do agente.")
            try:
                store.server_status("degraded", {"last_error_at": int(time.time())})
            except Exception:
                log.exception("Falha ao publicar estado.")
        time.sleep(refresh)
