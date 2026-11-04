"""CryptoIA agent entry point.

This first version is intentionally simulation-only. It does not place orders,
withdraw funds, or initiate PIX transfers.
"""
from __future__ import annotations

import logging
import os
import time

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("cryptoia.agent")


def main() -> None:
    log.info("CryptoIA iniciado em modo educacional/simulado.")
    log.info("Nenhuma ordem real, saque ou transferência PIX será executada.")
    while True:
        # Market-data connectors, memory, reminders and the simulator will be
        # added as separate modules after their API contracts are verified.
        time.sleep(30)


if __name__ == "__main__":
    main()
