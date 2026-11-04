"""CryptoIA supervisor: elect one active server through a Firebase RTDB lease.

Never commit the Firebase service-account JSON. Set
GOOGLE_APPLICATION_CREDENTIALS to a file stored outside this repository.
"""
from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import credentials, db

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL", "").strip()
CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
SERVER_ID = os.getenv("SERVER_ID", "").strip()
LEASE_TTL = max(20, int(os.getenv("LEASE_TTL_SECONDS", "45")))
HEARTBEAT_INTERVAL = max(5, int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "10")))
RESTART_DELAY = max(1, int(os.getenv("AGENT_RESTART_DELAY_SECONDS", "5")))
LEASE_PATH = "/coordination/active_lease"

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("cryptoia.supervisor")


def initialize_firebase() -> None:
    if not DATABASE_URL:
        raise RuntimeError("FIREBASE_DATABASE_URL não foi configurada.")
    if not CREDENTIALS_PATH or not Path(CREDENTIALS_PATH).is_file():
        raise RuntimeError(
            "Defina GOOGLE_APPLICATION_CREDENTIALS apontando para o JSON "
            "da conta de serviço, guardado fora do repositório."
        )
    if not SERVER_ID or SERVER_ID == "change-this-to-a-unique-server-id":
        raise RuntimeError("Defina um SERVER_ID único para este servidor.")

    if not firebase_admin._apps:
        cred = credentials.Certificate(CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})


def acquire_lease() -> bool:
    """Atomic RTDB transaction: only one server can acquire an unexpired lease."""
    ref = db.reference(LEASE_PATH)
    now = int(time.time())

    def claim(current: Any) -> Any:
        if current and current.get("owner") != SERVER_ID:
            if int(current.get("expires_at", 0)) > now:
                return current
        generation = int((current or {}).get("generation", 0)) + 1
        return {
            "owner": SERVER_ID,
            "heartbeat_at": now,
            "expires_at": now + LEASE_TTL,
            "generation": generation,
        }

    result = ref.transaction(claim)
    return bool(result and result.get("owner") == SERVER_ID)


def renew_lease() -> bool:
    """Renew only if this server still owns the lease; never overwrite a new owner."""
    ref = db.reference(LEASE_PATH)
    now = int(time.time())

    def renew(current: Any) -> Any:
        if not current or current.get("owner") != SERVER_ID:
            return current
        updated = dict(current)
        updated["heartbeat_at"] = now
        updated["expires_at"] = now + LEASE_TTL
        return updated

    result = ref.transaction(renew)
    return bool(result and result.get("owner") == SERVER_ID)


def release_lease() -> None:
    ref = db.reference(LEASE_PATH)

    def release(current: Any) -> Any:
        if not current or current.get("owner") != SERVER_ID:
            return current
        return {
            "owner": None,
            "heartbeat_at": int(time.time()),
            "expires_at": 0,
            "generation": int(current.get("generation", 0)),
        }

    ref.transaction(release)


def run_agent() -> int:
    command = [sys.executable, str(ROOT / "main.py")]
    log.info("Iniciando agente CryptoIA: %s", SERVER_ID)
    process = subprocess.Popen(command, cwd=ROOT)
    try:
        while process.poll() is None:
            time.sleep(HEARTBEAT_INTERVAL)
            if not renew_lease():
                log.warning("Lease perdido; encerrando o agente por segurança.")
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                return 2
        return int(process.returncode or 0)
    finally:
        if process.poll() is None:
            process.terminate()


def main() -> None:
    initialize_firebase()
    log.info("Servidor %s aguardando lease exclusivo.", SERVER_ID)

    while True:
        try:
            if not acquire_lease():
                log.info("Outro servidor já está ativo. Este ficará em espera.")
                time.sleep(HEARTBEAT_INTERVAL)
                continue

            log.info("Lease adquirido; este é o único agente ativo.")
            code = run_agent()
            log.info("Agente finalizado com código %s.", code)
            release_lease()
            time.sleep(RESTART_DELAY)
        except KeyboardInterrupt:
            log.info("Encerramento solicitado.")
            break
        except Exception:
            log.exception("Falha no supervisor; tentando novamente.")
            time.sleep(RESTART_DELAY)

    try:
        release_lease()
    except Exception:
        log.exception("Não foi possível liberar o lease durante o encerramento.")


if __name__ == "__main__":
    main()
