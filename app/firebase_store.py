from __future__ import annotations

import os
import time
from typing import Any

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


def set_value(path: str, value: Any) -> None:
    assert_active_lease()
    ref(path).set(value)


def update_value(path: str, value: dict[str, Any]) -> None:
    assert_active_lease()
    ref(path).update(value)


def push_value(path: str, value: Any) -> str:
    assert_active_lease()
    item = ref(path).push(value)
    return str(item.key)


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
