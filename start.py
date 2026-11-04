"""CryptoIA single-active-server supervisor.

All server credentials stay outside the repository. The lease is acquired and
renewed with Firebase RTDB transactions. The generation token fences stale
processes from writing after a lease has moved to another server.
"""
from __future__ import annotations

import logging
import os
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
LEASE_TTL = max(30, int(os.getenv("LEASE_TTL_SECONDS", "60")))
HEARTBEAT = max(5, int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "10")))
RESTART_DELAY = 5
LEASE_PATH = "/cryptoia/control/lease"

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("cryptoia.supervisor")


def initialize() -> None:
    if not DATABASE_URL:
        raise RuntimeError("FIREBASE_DATABASE_URL ausente.")
    if not CREDENTIALS_PATH or not Path(CREDENTIALS_PATH).is_file():
        raise RuntimeError("Configure GOOGLE_APPLICATION_CREDENTIALS com o JSON de serviço fora do GitHub.")
    if not SERVER_ID or SERVER_ID.startswith("change-this"):
        raise RuntimeError("Configure um SERVER_ID único em cada máquina.")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            credentials.Certificate(CREDENTIALS_PATH),
            {"databaseURL": DATABASE_URL},
        )


def acquire() -> dict[str, Any] | None:
    ref = db.reference(LEASE_PATH)
    now = int(time.time())

    def txn(current: Any) -> Any:
        current = current or {}
        if current.get("owner") not in (None, "", SERVER_ID) and int(current.get("expires_at", 0)) > now:
            return current
        return {
            "owner": SERVER_ID,
            "heartbeat_at": now,
            "expires_at": now + LEASE_TTL,
            "generation": int(current.get("generation", 0)) + 1,
        }

    result = ref.transaction(txn)
    if result and result.get("owner") == SERVER_ID and int(result.get("expires_at", 0)) > now:
        return result
    return None


def renew(generation: int) -> bool:
    ref = db.reference(LEASE_PATH)
    now = int(time.time())

    def txn(current: Any) -> Any:
        if not current or current.get("owner") != SERVER_ID or int(current.get("generation", -1)) != generation:
            return current
        updated = dict(current)
        updated.update(heartbeat_at=now, expires_at=now + LEASE_TTL)
        return updated

    result = ref.transaction(txn)
    return bool(result and result.get("owner") == SERVER_ID
                and int(result.get("generation", -1)) == generation
                and int(result.get("expires_at", 0)) > now)


def release(generation: int) -> None:
    ref = db.reference(LEASE_PATH)

    def txn(current: Any) -> Any:
        if not current or current.get("owner") != SERVER_ID or int(current.get("generation", -1)) != generation:
            return current
        return {"owner": None, "heartbeat_at": int(time.time()), "expires_at": 0,
                "generation": generation}
    ref.transaction(txn)


def run_agent(generation: int) -> int:
    env = os.environ.copy()
    env["CRYPTOIA_LEASE_GENERATION"] = str(generation)
    env["CRYPTOIA_SERVER_ID"] = SERVER_ID
    proc = subprocess.Popen([sys.executable, str(ROOT / "main.py")], cwd=ROOT, env=env)
    try:
        while proc.poll() is None:
            time.sleep(HEARTBEAT)
            if not renew(generation):
                log.error("Lease perdido; encerrando agente para evitar execução dupla.")
                proc.terminate()
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
                return 2
        return int(proc.returncode or 0)
    finally:
        if proc.poll() is None:
            proc.terminate()


def main() -> None:
    initialize()
    log.info("Servidor %s em espera pela eleição.", SERVER_ID)
    while True:
        try:
            lease = acquire()
            if not lease:
                log.info("Outro servidor possui o lease ativo.")
                time.sleep(HEARTBEAT)
                continue
            generation = int(lease["generation"])
            log.info("Lease adquirido. Geração %s.", generation)
            try:
                run_agent(generation)
            finally:
                release(generation)
            time.sleep(RESTART_DELAY)
        except KeyboardInterrupt:
            log.info("Encerrando supervisor.")
            break
        except Exception:
            log.exception("Erro no supervisor; nova tentativa em alguns segundos.")
            time.sleep(RESTART_DELAY)


if __name__ == "__main__":
    main()
