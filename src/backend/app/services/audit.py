"""Log de auditoria das decisões da IA (append-only, JSON Lines).
Cada decisão registra entradas, regras disparadas, documentos RAG usados e o modo
(LLM / extrativo / fallback) — garantindo rastreabilidade e explicabilidade."""
import hashlib
import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from ..config import LOG_DIR
from .privacy import scrub_pii

AUDIT_FILE = LOG_DIR / "audit_ia.jsonl"
_lock = threading.Lock()
logger = logging.getLogger("aquaguard.audit")


def log_decision(kind: str, inputs: Dict[str, Any], output: Dict[str, Any]) -> str:
    decision_id = str(uuid.uuid4())
    safe_inputs = json.loads(scrub_pii(json.dumps(inputs, default=str, ensure_ascii=False)))
    record = {
        "decision_id": decision_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": kind,  # "risk_assessment" | "chat"
        "inputs": safe_inputs,
        "inputs_sha256": hashlib.sha256(json.dumps(safe_inputs, sort_keys=True, default=str).encode()).hexdigest(),
        "output": output,
    }
    try:
        with _lock, AUDIT_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except OSError as exc:  # auditoria nunca derruba a aplicação
        logger.error("Falha ao gravar auditoria: %s", exc)
    return decision_id


def read_last(n: int = 20) -> List[Dict[str, Any]]:
    if not AUDIT_FILE.exists():
        return []
    with AUDIT_FILE.open(encoding="utf-8") as f:
        lines = f.readlines()[-n:]
    out = []
    for line in reversed(lines):
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
