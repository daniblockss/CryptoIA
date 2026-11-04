from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

from app import firebase_store as store
from app.llm7 import ask
from app.market import fetch_market
from app.memory import create_memory
from app.portfolio import ensure_portfolio, process_commands, publish_valuation
from app.reminders import check_reminders

load_dotenv()
log = logging.getLogger("cryptoia.agent")


def _local_analysis(market: dict) -> str:
    rows = []
    for symbol, quote in market.items():
        if symbol == "_meta":
            continue
        price = quote.get("price_brl")
        change = quote.get("change_24h")
        if price:
            delta = f"{float(change):+.2f}%" if change is not None else "sem variação informada"
            rows.append(f"{symbol}: R$ {float(price):,.2f} ({delta} em 24h)")
    return "Cotações observadas: " + ("; ".join(rows) if rows else "nenhuma cotação disponível") + ". Dados informativos, não previsão."


def _handle_ai_requests(market: dict) -> None:
    commands = store.get_value("commands", {}) or {}
    for command_id, command in commands.items():
        if not isinstance(command, dict) or command.get("type") != "ask_ai" or command.get("status") != "pending":
            continue
        portfolio = store.get_value("portfolio", {}) or {}
        prompt = (
            "Analise este snapshot de mercado e carteira SIMULADA. "
            f"Mercado: {market}. Carteira simulada: {portfolio}. "
            "Destaque incertezas e riscos. Não recomende compra/venda real, "
            "não prometa lucro e não execute operações."
        )
        answer = ask(prompt)
        store.update_value(f"commands/{command_id}", {
            "status": "done", "result": answer, "processed_at": int(time.time())
        })
        store.push_value("events", {
            "type": "ai_analysis", "message": answer[:5000], "at": int(time.time())
        })
        try:
            create_memory("Análise de mercado " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                          answer, "LLM7")
        except Exception:
            log.exception("Não foi possível salvar memória da análise.")


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
