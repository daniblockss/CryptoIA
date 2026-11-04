from __future__ import annotations

import os
import time
import uuid
from typing import Any, Callable

import firebase_admin
from firebase_admin import db


def ref(path: str = ""):
    return db.reference("/cryptoia" + ("/" + path.strip("/") if path else ""))


def server_identity() -> tuple[str, int]:
    return (
        os.getenv("CRYPTOIA_SERVER_ID", ""),
        int(os.getenv("CRYPTOIA_LEASE_GENERATION", "0")),
    )


def assert_active_lease() -> None:
    owner, generation = server_identity()
    lease = ref("control/lease").get() or {}
    if (
        not owner
        or lease.get("owner") != owner
        or int(lease.get("generation", -1)) != generation
        or int(lease.get("expires_at", 0)) <= int(time.time())
    ):
        raise RuntimeError("Lease inválido: este processo não pode gravar no Firebase.")


def _atomic_write(path: str, operation: Callable[[dict[str, Any]], None]) -> None:
    """Check lease and mutate the subtree in one root-level RTDB transaction.

    This prevents a stale worker from passing a separate lease check and then
    writing after another server has acquired a newer generation.
    """
    owner, generation = server_identity()
    if not owner or generation <= 0:
        raise RuntimeError("Identidade/geração do servidor ausente.")
    parts = [part for part in path.strip("/").split("/") if part]
    if not parts:
        raise ValueError("Caminho de gravação vazio.")

    root = db.reference("/cryptoia")

    def transaction(current: Any) -> Any:
        data = dict(current or {})
        lease = ((data.get("control") or {}).get("lease") or {})
        now = int(time.time())
        if (
            lease.get("owner") != owner
            or int(lease.get("generation", -1)) != generation
            or int(lease.get("expires_at", 0)) <= now
        ):
            raise RuntimeError("Lease perdido: gravação cancelada.")

        node = data
        for part in parts[:-1]:
            child = node.get(part)
            if not isinstance(child, dict):
                child = {}
                node[part] = child
            node = child
        operation(node)
        return data

    root.transaction(transaction)


def set_value(path: str, value: Any) -> None:
    _atomic_write(path, lambda node: node.__setitem__(path.strip("/").split("/")[-1], value))


def update_value(path: str, value: dict[str, Any]) -> None:
    def update(node: dict[str, Any]) -> None:
        key = path.strip("/").split("/")[-1]
        current = node.get(key)
        if not isinstance(current, dict):
            current = {}
        current.update(value)
        node[key] = current
    _atomic_write(path, update)


def push_value(path: str, value: Any) -> str:
    key = uuid.uuid4().hex
    _atomic_write(path, lambda node: node.__setitem__(key, value))
    return key


def get_value(path: str, default: Any = None) -> Any:
    value = ref(path).get()
    return default if value is None else value


def server_status(state: str, extra: dict[str, Any] | None = None) -> None:
    owner, generation = server_identity()
    payload = {
        "server_id": owner,
        "generation": generation,
        "state": state,
        "updated_at": int(time.time()),
    }
    if extra:
        payload.update(extra)
    set_value("servers/active", payload)
