"""[NOVO] Agente de Triagem de Ocorrências.

Fluxo (máquina de estados por sessão de chat):
  1. Detecta INTENÇÃO: relato de emergência x dúvida.
  2. Extrai SLOTS do texto livre: área (via aliases de areas_risco.json), referência de local (rua/av.),
     tipo(s) de emergência, nº de pessoas e pessoas vulneráveis.
  3. Pergunta apenas o que falta (localização e/ou o que está acontecendo).
  4. Registra a OCORRÊNCIA com prioridade P1/P2/P3 e devolve orientações extraídas
     SOMENTE dos protocolos locais + rota/abrigo da área (sem texto gerado => sem alucinação).

A extração é determinística (regex + dicionário) para rodar offline e ser auditável.
Ponto de extensão: `extract()` pode ser substituído por um LLM com saída JSON (function calling)."""
import json
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from ..config import LOG_DIR
from ..schemas import Occurrence, TriageInfo
from . import audit
from .privacy import pseudonymize, scrub_pii
from .rag import retriever, strip_accents
from .risk_engine import AREAS

OCC_LOG = LOG_DIR / "ocorrencias.jsonl"
SESSION_TTL_S = 30 * 60
_lock = threading.Lock()
SESSIONS: Dict[str, dict] = {}
OCCURRENCES: List[Occurrence] = []

# tipo -> (padrões em texto sem acento, protocolos de orientação, peso de prioridade)
EMERGENCY_TYPES: Dict[str, Tuple[List[str], List[str], int]] = {
    "pessoa_ilhada":     ([r"ilhad", r"\bpres[oa]s?\b", r"no telhado", r"na laje", r"nao consigo sair", r"nao conseguimos sair", r"cercad"], ["PROT-09", "PROT-05"], 1),
    "pessoa_arrastada":  ([r"arrastad", r"correnteza levou", r"levad[oa] pela agua", r"caiu no rio", r"afogand"], ["PROT-09", "PROT-05"], 1),
    "ferido":            ([r"ferid", r"machucad", r"sangr", r"desmai", r"inconscien"], ["PROT-05"], 1),
    "desabamento":       ([r"desab", r"desmoron", r"deslizament", r"barranco", r"rachadura", r"parede (caiu|cedeu|trincou)"], ["PROT-10", "PROT-05"], 1),
    "agua_em_imovel":    ([r"agua (entrou|invadiu|esta entrando|ta entrando|esta subindo|ta subindo|subindo|na casa|dentro)", r"(casa|imovel|apartamento|comercio) (alagad|inundad|cheia)", r"(alagou|inundou) (a |minha |nossa )?casa", r"na altura d[oa]", r"na cintura", r"no joelho"], ["PROT-03", "PROT-04"], 2),
    "risco_eletrico":    ([r"\bfios?\b", r"poste", r"choque", r"faisca", r"curto"], ["PROT-10", "PROT-03"], 2),
    "via_alagada":       ([r"rua (esta |ta )?(alagad|inundad|cheia)", r"avenida (alagad|inundad)", r"alagament", r"alagad", r"inundad", r"transbord", r"rio (subiu|encheu|transbordou)", r"enchente"], ["PROT-03"], 3),
    "animal_em_risco":   ([r"\b(cachorro|gato|animal|animais|cavalo|pet)s?\b"], ["PROT-07"], 3),
}
VULNERABLE = {"criancas": r"crianc|bebe|filh[oa]s? pequen", "idosos": r"idos|avo\b|avos\b|senhor[a]? de idade",
              "gestantes": r"gravida|gestante", "pcd": r"cadeirante|deficien|acamad|cadeira de rodas"}
NUM_WORDS = {"uma": 1, "um": 1, "duas": 2, "dois": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6,
             "sete": 7, "oito": 8, "nove": 9, "dez": 10}
REPORT_TRIGGERS = [r"\bsocorro\b", r"\bajuda\b.*\b(urgente|agora|rapido)\b", r"quero (registrar|relatar|reportar|informar|denunciar)",
                   r"(registrar|abrir) (uma )?ocorrencia", r"\bestou\b", r"\bestamos\b", r"\baqui (na|no|em)\b",
                   r"\b(entrou|invadiu|subiu|caiu|desabou|alagou|inundou|transbordou)\b", r"\btem agua\b", r"\btem (um|uma|gente|pessoas?)\b", r"\bcaid[oa]s?\b", r"\b(esta|ta) (subindo|entrando|alagando|enchendo|desabando)\b", r"\bcomigo\b", r"\bminha (casa|rua)\b.*\b(alagad|inundad|cheia|agua)"]
STREET_STOP = {"ta", "esta", "estao", "cheia", "aqui", "ficou", "encheu", "virou", "subiu", "tem", "com"}
QUESTION_PATTERNS = [r"^(o que|como|qual|quais|onde|quando|devo|posso|vai|tem risco)\b", r"\bse (a agua|o rio|chover|eu)\b"]
STREET_RE = re.compile(r"\b((?:rua|r\.|avenida|av\.?|travessa|tv\.|praca|estrada|viela|alameda|beco)\s+[a-z0-9 ]{2,40}?)"
                       r"(?=\s*(?:,|\.|;|!|\?|$|\bn[ou]?\b|\bnumero\b|\bperto\b|\bproximo\b|\bao lado\b|\besquina\b|\bem frente\b|\be\b|\bcom\b|\bpois\b|\bporque\b))")


# ------------------------------------------------------------------ extração
def detect_intent(text: str, session: dict) -> str:
    t = strip_accents(text)
    is_question = text.strip().endswith("?") or any(re.search(p, t) for p in QUESTION_PATTERNS)
    has_emergency = any(re.search(p, t) for pats, _, _ in EMERGENCY_TYPES.values() for p in pats)
    strong = any(re.search(p, t) for p in REPORT_TRIGGERS[:4])
    reportish = any(re.search(p, t) for p in REPORT_TRIGGERS[4:])
    if strong:
        return "ocorrencia"
    if session.get("status") == "coletando" and not is_question:
        return "ocorrencia"   # usuário respondendo à pergunta da triagem
    if has_emergency and reportish and not is_question:
        return "ocorrencia"
    return "duvida"


def extract(text: str) -> Dict[str, object]:
    t = strip_accents(text)
    out: Dict[str, object] = {}
    for a in AREAS["areas"]:
        if any(strip_accents(al) in t for al in a.get("aliases", [])) or re.search(rf"\barea {a['id'].lower()}\b", t):
            out["area_id"], out["area_name"] = a["id"], a["nome"]
            break
    m = STREET_RE.search(t)
    if m:
        words = []
        for w in m.group(1).split():  # corta no primeiro verbo/advérbio ("rua ta alagada aqui" -> descartado)
            if w in STREET_STOP or w.startswith(("alagad", "inundad")):
                break
            words.append(w)
        if len(words) >= 2:
            out["location_text"] = " ".join(words).title()
    types = [k for k, (pats, _, _) in EMERGENCY_TYPES.items() if any(re.search(p, t) for p in pats)]
    if types:
        out["types"] = types
    m = re.search(r"\b(\d{1,3}|" + "|".join(NUM_WORDS) + r")\s+(pessoas|moradores|familias|adultos|criancas|idosos)", t)
    if m:
        n = m.group(1)
        out["people_at_risk"] = int(n) if n.isdigit() else NUM_WORDS[n]
    vul = [k for k, p in VULNERABLE.items() if re.search(p, t)]
    if vul:
        out["vulnerable"] = vul
    return out


def _priority(types: List[str], vulnerable: List[str]) -> str:
    best = min((EMERGENCY_TYPES[t][2] for t in types), default=3)
    if best == 2 and vulnerable:
        best = 1  # água dentro de casa + vulneráveis => P1
    return f"P{best}"


# ------------------------------------------------------------------ sessão
def get_session(session_id: Optional[str]) -> Tuple[str, dict]:
    now = time.time()
    with _lock:
        for sid in [s for s, v in SESSIONS.items() if now - v["updated"] > SESSION_TTL_S]:
            SESSIONS.pop(sid, None)
        sid = session_id or uuid.uuid4().hex[:12]
        sess = SESSIONS.setdefault(sid, {"status": None, "slots": {}, "texts": [], "updated": now, "occurrence_id": None})
        sess["updated"] = now
        return sid, sess


def _merge(slots: dict, new: dict):
    for k, v in new.items():
        if isinstance(v, list):
            slots[k] = sorted(set(slots.get(k, [])) | set(v))
        elif v is not None:
            slots[k] = v


# ------------------------------------------------------------------ fluxo principal
def handle(message: str, session_id: Optional[str], default_area: Optional[str]) -> Optional[dict]:
    """Retorna dict com resposta de triagem, ou None se a mensagem for uma dúvida (vai para o RAG)."""
    sid, sess = get_session(session_id)
    clean = scrub_pii(message)
    intent = detect_intent(clean, sess)
    if intent != "ocorrencia":
        return {"session_id": sid, "handled": False}

    if sess["status"] == "registrada":  # nova ocorrência na mesma sessão
        sess.update(status=None, slots={}, texts=[], occurrence_id=None)
    sess["status"] = "coletando"
    sess["texts"].append(clean)
    _merge(sess["slots"], extract(clean))
    slots = sess["slots"]
    if "area_id" not in slots and default_area:   # área escolhida no app (sem GPS)
        area = next((a for a in AREAS["areas"] if a["id"] == default_area), None)
        if area:
            slots.update(area_id=area["id"], area_name=area["nome"], area_from_profile=True)

    missing = []
    if "area_id" not in slots and "location_text" not in slots:
        missing.append("localizacao")
    if "types" not in slots:
        missing.append("tipo_emergencia")

    urgent = any(t in slots.get("types", []) for t in ("pessoa_ilhada", "pessoa_arrastada", "ferido", "desabamento"))
    if missing and len(sess["texts"]) < 3:
        questions = {"localizacao": "📍 Em qual bairro/área você está? (ex.: Jardim Ribeirinho, Vila Baixada, Parque das Águas) Se puder, informe a rua ou um ponto de referência.",
                     "tipo_emergencia": "📝 O que está acontecendo? (ex.: água entrando em casa, pessoa ilhada, rua alagada, fio caído, deslizamento)"}
        answer = "Vou registrar sua ocorrência para a Defesa Civil.\n\n" + "\n".join(questions[m] for m in missing)
        if urgent:
            answer = "🚨 Se houver risco de vida, LIGUE 193 (Bombeiros) AGORA.\n\n" + answer
        info = TriageInfo(status="coletando", extracted=_public(slots), missing=missing)
        audit.log_decision("triage", {"message": clean, "session": pseudonymize(sid, "ses")},
                           {"status": "coletando", "missing": missing, "extracted": _public(slots)})
        return {"session_id": sid, "handled": True, "answer": answer, "triage": info, "sources": []}

    # ---------- registrar ocorrência (mesmo incompleta após 3 tentativas: melhor registrar do que perder)
    types = slots.get("types", ["nao_classificado"])
    vulnerable = slots.get("vulnerable", [])
    priority = _priority([t for t in types if t in EMERGENCY_TYPES], vulnerable)
    refs: List[str] = []
    for t in types:
        for r in EMERGENCY_TYPES.get(t, ([], ["PROT-05"], 3))[1]:
            if r not in refs:
                refs.append(r)
    area = next((a for a in AREAS["areas"] if a["id"] == slots.get("area_id")), None)
    if area:
        refs.append(area["rota"])
    occ = Occurrence(id="OC-" + uuid.uuid4().hex[:6].upper(), created_at=datetime.now(timezone.utc),
                     area_id=slots.get("area_id"), area_name=slots.get("area_name"),
                     location_text=slots.get("location_text"), types=types, priority=priority,
                     people_at_risk=slots.get("people_at_risk"), vulnerable=vulnerable,
                     description=" | ".join(sess["texts"])[:600], guidance_refs=refs,
                     session_ref=pseudonymize(sid, "ses"))
    with _lock:
        OCCURRENCES.append(occ)
        del OCCURRENCES[:-500]
        try:
            with OCC_LOG.open("a", encoding="utf-8") as f:
                f.write(occ.model_dump_json() + "\n")
        except OSError:
            pass
    sess.update(status="registrada", occurrence_id=occ.id)

    # ---------- resposta extrativa: somente trechos da base local
    header = {"P1": "🚨 PRIORIDADE MÁXIMA (P1) — se houver risco de vida, LIGUE 193 AGORA.",
              "P2": "⚠️ Prioridade alta (P2) — equipe da Defesa Civil notificada.",
              "P3": "ℹ️ Prioridade moderada (P3) — ocorrência em acompanhamento."}[priority]
    lines = [f"✅ Ocorrência {occ.id} registrada.", header, "",
             f"Resumo: {', '.join(t.replace('_', ' ') for t in types)}"
             + (f" · {occ.area_name}" if occ.area_name else "")
             + (f" · {occ.location_text}" if occ.location_text else "")
             + (f" · {occ.people_at_risk} pessoa(s)" if occ.people_at_risk else "")
             + (f" · vulneráveis: {', '.join(vulnerable)}" if vulnerable else ""), "",
             "O que fazer agora (protocolos oficiais):"]
    for r in refs[:3]:
        d = retriever.get(r)
        if d:
            lines.append(f"📘 [{d['id']}] {d['texto']}")
    answer = "\n".join(lines)
    info = TriageInfo(status="registrada", occurrence_id=occ.id, extracted=_public(slots), missing=[], priority=priority)
    audit.log_decision("triage", {"message": clean, "session": occ.session_ref},
                       {"status": "registrada", "occurrence_id": occ.id, "priority": priority, "types": types, "refs": refs})
    return {"session_id": sid, "handled": True, "answer": answer, "triage": info, "sources": refs[:3]}


def _public(slots: dict) -> dict:
    return {k: v for k, v in slots.items() if k != "area_from_profile"}


def set_status(occ_id: str, status: str) -> Optional[Occurrence]:
    with _lock:
        for o in OCCURRENCES:
            if o.id == occ_id:
                o.status = status
                return o
    return None
