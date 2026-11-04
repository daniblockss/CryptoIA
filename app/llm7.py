from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import requests

from app import firebase_store as store

BASE_URL = os.getenv("LLM7_BASE_URL", "https://api.llm7.io/v1").rstrip("/")
MODEL = os.getenv("LLM7_MODEL", "DeepSeek-V4.1-Flash")
MAX_CALLS = max(0, int(os.getenv("LLM7_MAX_CALLS_PER_DAY", "8")))
MIN_INTERVAL = max(60, int(os.getenv("LLM7_MIN_INTERVAL_SECONDS", "300")))
MAX_TOKENS = min(1200, max(100, int(os.getenv("LLM7_MAX_TOKENS", "700"))))


def _quota_path() -> str:
    return "usage/llm7/" + datetime.now(timezone.utc).strftime("%Y-%m-%d")


def ask(
    prompt: str,
    system: str = "Você é o analista educacional do CryptoIA. Não dê ordens de compra ou venda; explique incertezas e riscos. A carteira é apenas simulada.",
    json_mode: bool = False,
) -> str:
    api_key = os.getenv("LLM7_API_KEY", "").strip()
    if not api_key:
        return "LLM7 não configurado: adicione LLM7_API_KEY no arquivo .env do servidor."

    quota_path = _quota_path()
    quota = store.get_value(quota_path, {}) or {}
    calls = int(quota.get("calls", 0))
    last_call = int(quota.get("last_call_at", 0))
    now = int(time.time())

    if calls >= MAX_CALLS:
        return f"Limite diário do LLM7 atingido ({MAX_CALLS} chamadas)."
    if now - last_call < MIN_INTERVAL:
        return f"Limite de intervalo ativo. Aguarde {MIN_INTERVAL - (now-last_call)} segundos."

    quota.update(calls=calls + 1, last_call_at=now, model=MODEL)
    store.set_value(quota_path, quota)

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system[:3000]},
            {"role": "user", "content": prompt[:10000]},
        ],
        "temperature": 0.2,
        "max_tokens": MAX_TOKENS,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    response = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("LLM7 retornou uma resposta sem choices.")
    content = choices[0].get("message", {}).get("content")
    if isinstance(content, list):
        content = " ".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
    return str(content or "LLM7 retornou conteúdo vazio.")[:12000]
