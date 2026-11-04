from __future__ import annotations

import re
import time
from pathlib import Path

from app import firebase_store as store

MEMORY_DIR = Path(__file__).resolve().parent.parent / "data" / "memories"


def _safe_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "-", value)[:48] or str(int(time.time()))


def create_memory(title: str, body: str, source: str = "agent") -> str:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    memory_id = f"{int(time.time())}-{_safe_id(title)}"
    filename = f"{memory_id}.md"
    content = f"# {title[:100]}\n\n{body[:6000]}\n"
    (MEMORY_DIR / filename).write_text(content, encoding="utf-8")
    store.set_value(f"memories/{memory_id}", {
        "title": title[:100],
        "file": filename,
        "body_preview": body[:500],
        "source": source,
        "created_at": int(time.time()),
    })
    return filename


def read_memory(filename: str | None) -> str:
    if not filename:
        return ""
    name = Path(filename).name
    path = MEMORY_DIR / name
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")[:6000]
