"""[NOVO] Cadastro de contatos + disparo SIMULADO de alertas (WhatsApp / e-mail).

Estratégia "sem atrito" para a POC (sem conta Meta Business, Twilio ou SMTP):
  - WhatsApp: link click-to-chat oficial  https://wa.me/<E164>?text=<mensagem codificada>
  - E-mail:   link mailto:<email>?subject=...&body=...
  - Link de compartilhamento geral (https://wa.me/?text=...) para grupos de moradores.
Cada disparo é registrado em logs/dispatch_log.jsonl (telefones MASCARADOS) e na auditoria.
Para produção, basta trocar `_build_links` por uma chamada à WhatsApp Cloud API / provedor SMTP."""
import json
import logging
import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import quote

from ..config import DATA_DIR, LOG_DIR
from ..schemas import ContactIn, ContactOut, DispatchMessage, DispatchOut, RiskLevel
from . import audit
from .privacy import mask_email, mask_phone
from .rag import retriever
from .risk_engine import AREAS, affected_areas

logger = logging.getLogger("aquaguard.notifications")
CONTACTS_FILE = DATA_DIR / "contatos_runtime.json"   # gitignored — dados pessoais não vão para o repositório
DISPATCH_LOG = LOG_DIR / "dispatch_log.jsonl"
_lock = threading.Lock()

LEVEL_ICON = {RiskLevel.VERDE: "🟢", RiskLevel.AMARELO: "🟡", RiskLevel.VERMELHO: "🔴"}
LEVEL_PROTOCOL = {RiskLevel.VERDE: "PROT-02", RiskLevel.AMARELO: "PROT-02", RiskLevel.VERMELHO: "PROT-04"}


# ------------------------------------------------------------------ contatos
class ContactStore:
    def __init__(self):
        self._items: Dict[str, dict] = {}
        try:
            if CONTACTS_FILE.exists():
                self._items = json.loads(CONTACTS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Arquivo de contatos corrompido — iniciando vazio.")

    def _persist(self):
        try:
            CONTACTS_FILE.write_text(json.dumps(self._items, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError as exc:
            logger.error("Falha ao salvar contatos: %s", exc)

    @staticmethod
    def to_out(c: dict) -> ContactOut:
        return ContactOut(id=c["id"], name=c["name"], phone_masked=mask_phone(c.get("phone")),
                          email_masked=mask_email(c.get("email")), area_id=c["area_id"],
                          channels=c["channels"], created_at=c["created_at"])

    def add(self, data: ContactIn) -> ContactOut:
        with _lock:
            # Deduplicação: mesmo telefone/e-mail atualiza o cadastro existente
            existing = next((c for c in self._items.values()
                             if (data.phone and c.get("phone") == data.phone) or (data.email and c.get("email") == data.email)), None)
            cid = existing["id"] if existing else "ct_" + uuid.uuid4().hex[:8]
            self._items[cid] = {"id": cid, **data.model_dump(exclude={"consent"}),
                                "consent_at": datetime.now(timezone.utc).isoformat(),
                                "created_at": existing["created_at"] if existing else datetime.now(timezone.utc).isoformat()}
            self._persist()
            return self.to_out(self._items[cid])

    def list(self) -> List[ContactOut]:
        return [self.to_out(c) for c in self._items.values()]

    def delete(self, cid: str) -> bool:  # direito de eliminação (LGPD art. 18, VI)
        with _lock:
            ok = self._items.pop(cid, None) is not None
            self._persist()
            return ok

    def by_areas(self, area_ids: List[str]) -> List[dict]:
        return [c for c in self._items.values() if c["area_id"] in area_ids]


contacts = ContactStore()
DISPATCHES: List[DispatchOut] = []   # memória: contém links (com telefone) — não vai para disco


# ------------------------------------------------------------------ mensagem
def _first_sentence(text: str) -> str:
    return re.split(r"(?<=[a-zà-ú)])\.\s+", text)[0].rstrip(".") + "."


def build_message(level: RiskLevel, area: Optional[dict], test: bool, note: Optional[str] = None) -> tuple[str, List[str]]:
    """Mensagem 100% montada a partir da base local (sem IA generativa => sem alucinação)."""
    refs = [LEVEL_PROTOCOL[level], "PROT-05"]
    head = {RiskLevel.VERMELHO: "ALERTA MÁXIMO DE ENCHENTE", RiskLevel.AMARELO: "ATENÇÃO: RISCO DE ALAGAMENTO",
            RiskLevel.VERDE: "Aviso preventivo"}[level]
    lines = []
    if test:
        lines.append("[SIMULAÇÃO — TESTE DO SISTEMA AQUAGUARD]")
    lines.append(f"{LEVEL_ICON[level]} *{head}* — Defesa Civil")
    if area:
        lines.append(f"📍 Área: {area['nome']} ({area['id']})")
    lines.append("")
    lines.append("✅ " + _first_sentence(retriever.get(LEVEL_PROTOCOL[level])["texto"]))
    if area and level == RiskLevel.VERMELHO:
        rota = retriever.get(area["rota"])
        refs.append(area["rota"])
        lines.append("🧭 Rota: " + rota["texto"].split(":", 1)[-1].strip())
    if level == RiskLevel.VERMELHO:
        tip = _first_sentence(retriever.get("PROT-03")["texto"].split(":", 1)[-1].strip())
        lines.append("⚡ " + tip[0].upper() + tip[1:])
        refs.append("PROT-03")
    if note:
        lines.append(f"ℹ️ {note}")
    lines.append("")
    lines.append("📞 Defesa Civil 199 · Bombeiros 193 · SAMU 192")
    return "\n".join(lines), refs


def _build_links(contact: dict, text: str, level: RiskLevel) -> List[DispatchMessage]:
    msgs = []
    if "whatsapp" in contact["channels"] and contact.get("phone"):
        msgs.append(DispatchMessage(contact_id=contact["id"], contact_name=contact["name"], channel="whatsapp",
                                    recipient_masked=mask_phone(contact["phone"]),
                                    link=f"https://wa.me/{contact['phone']}?text={quote(text)}"))
    if "email" in contact["channels"] and contact.get("email"):
        subject = quote(f"[AquaGuard] Alerta {level.value} - Defesa Civil")
        msgs.append(DispatchMessage(contact_id=contact["id"], contact_name=contact["name"], channel="email",
                                    recipient_masked=mask_email(contact["email"]),
                                    link=f"mailto:{contact['email']}?subject={subject}&body={quote(text)}"))
    return msgs


# ------------------------------------------------------------------ disparo
def dispatch(level: RiskLevel, area_ids: Optional[List[str]], trigger: str, test: bool = True,
             note: Optional[str] = None) -> DispatchOut:
    areas = [a for a in AREAS["areas"] if a["id"] in area_ids] if area_ids else affected_areas(level)
    if not areas:  # ex.: VERDE sem área afetada => avisa todas
        areas = AREAS["areas"]
    messages: List[DispatchMessage] = []
    all_refs: set = set()
    texts = {}
    for area in areas:
        text, refs = build_message(level, area, test, note)
        texts[area["id"]] = text
        all_refs.update(refs)
        for c in contacts.by_areas([area["id"]]):
            messages.extend(_build_links(c, text, level))
    general_text, _ = build_message(level, None if len(areas) > 1 else areas[0], test, note)
    out = DispatchOut(id="dp_" + uuid.uuid4().hex[:8], created_at=datetime.now(timezone.utc), trigger=trigger,
                      level=level, area_ids=[a["id"] for a in areas], text=general_text,
                      protocol_refs=sorted(all_refs), messages=messages, total=len(messages),
                      share_link=f"https://wa.me/?text={quote(general_text)}")
    DISPATCHES.append(out)
    del DISPATCHES[:-100]
    # Log em disco SEM links (que contêm o telefone) — apenas destinatários mascarados
    record = {"id": out.id, "ts": out.created_at.isoformat(), "trigger": trigger, "level": level.value,
              "areas": out.area_ids, "test": test, "total": out.total,
              "recipients": [f"{m.channel}:{m.recipient_masked}" for m in messages], "refs": out.protocol_refs}
    try:
        with _lock, DISPATCH_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.error("Falha ao gravar log de disparo: %s", exc)
    audit.log_decision("dispatch", {"trigger": trigger, "level": level.value, "areas": out.area_ids, "test": test},
                       {"dispatch_id": out.id, "total": out.total, "refs": out.protocol_refs})
    logger.info("Disparo %s (%s) nível %s para %d destinatário(s)", out.id, trigger, level.value, out.total)
    return out
