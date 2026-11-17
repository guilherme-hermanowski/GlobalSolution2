"""Agente de IA AquaGuard.
(a) Análise Proativa: motor de risco + RAG => alerta estruturado com instruções oficiais
    [NOVO] + disparo automático (simulado) aos contatos quando o nível vira VERMELHO.
(b) Assistente Conversacional com roteamento de intenção [NOVO]:
      relato de emergência -> Agente de Triagem (registra ocorrência)
      dúvida               -> RAG (protocolos + áreas/rotas/abrigos)
      fora do escopo       -> recusa segura (199)

Anti-alucinação:
- Limiar mínimo de relevância: sem documento relevante => resposta de recusa segura.
- Nível de risco e números vêm do motor determinístico, nunca do LLM.
- LLM (opcional) recebe prompt restritivo e temperatura 0; qualquer falha => modo extrativo."""
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx

from ..config import settings
from ..schemas import Alert, ChatOut, RiskLevel
from . import audit, notifications, triage
from .privacy import scrub_pii
from .rag import normalize, retriever, strip_accents
from .risk_engine import AREAS, affected_areas, assess, daily_outlook

logger = logging.getLogger("aquaguard.agent")
MIN_RELEVANCE = 1.2
FORECAST_TERMS = {"previsao", "proximos", "dias", "amanha", "semana", "hoje", "risco", "chover", "chuva", "tempo"}
LEVEL_PROTOCOL = {RiskLevel.VERDE: ["PROT-02", "PROT-05"],
                  RiskLevel.AMARELO: ["PROT-08", "PROT-02", "PROT-05"],
                  RiskLevel.VERMELHO: ["PROT-04", "PROT-03", "PROT-05"]}
ALERTS: List[Alert] = []


# ------------------------------------------------------------------ (a) proativo
def _first_sentences(text: str, n: int = 2) -> List[str]:
    parts = [p.strip() for p in re.split(r"(?<=[a-zà-ú)])\.\s+", text) if len(p.strip()) > 15]
    return [p if p.endswith(".") else p + "." for p in parts[:n]]


def proactive_analysis(tel, weather: Dict, auto_dispatch: bool = True) -> Alert:
    score, level, factors, comps = assess(tel, weather)
    refs = LEVEL_PROTOCOL[level]
    instructions: List[str] = []
    for r in refs:
        instructions += _first_sentences(retriever.get(r)["texto"])
    affected = [a["nome"] for a in affected_areas(level)]
    title = {RiskLevel.VERDE: "Situação normal — mantenha-se informado",
             RiskLevel.AMARELO: "ATENÇÃO — risco moderado de alagamento",
             RiskLevel.VERMELHO: "ALERTA MÁXIMO — risco de transbordamento, evacue as áreas indicadas"}[level]
    alert = Alert(id=str(uuid.uuid4())[:8], created_at=datetime.now(timezone.utc), level=level, score=score,
                  title=title, summary="; ".join(factors[:3]), factors=factors, instructions=instructions[:6],
                  protocol_refs=refs, data_source=tel.source, affected_areas=affected)
    if not ALERTS or ALERTS[-1].level != level:   # só registra quando o nível muda
        ALERTS.append(alert)
        del ALERTS[:-50]
        audit.log_decision("risk_assessment",
                           {"telemetry": tel.model_dump(), "weather_source": weather.get("source"),
                            "forecast_48h": [d["rain_mm"] for d in weather.get("forecast", [])[:2]]},
                           {"level": level.value, "score": score, "components": comps, "protocol_refs": refs})
        if level == RiskLevel.VERMELHO and settings.auto_dispatch_on_red and auto_dispatch:
            try:  # disparo nunca derruba a análise
                notifications.dispatch(level, None, trigger="automatico", test=tel.source != "real")
            except Exception as exc:  # noqa: BLE001
                logger.error("Falha no disparo automático: %s", exc)
    return alert


# ------------------------------------------------------------------ (b) conversacional
SYSTEM_PROMPT = (
    "Você é o assistente AlertaCidadão da Defesa Civil. Responda em português, de forma curta e clara, "
    "USANDO EXCLUSIVAMENTE as informações do CONTEXTO. Se a resposta não estiver no contexto, diga que não sabe "
    "e oriente ligar 199. Nunca invente endereços, telefones, horários ou números. Cite os IDs [PROT-xx]/[ROTA-xx] usados."
)


def _call_llm(question: str, context: str) -> Optional[str]:
    if not settings.openai_api_key:
        return None
    try:
        r = httpx.post("https://api.openai.com/v1/chat/completions", timeout=15,
                       headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                       json={"model": settings.openai_model, "temperature": 0,
                             "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                                          {"role": "user", "content": f"CONTEXTO:\n{context}\n\nPERGUNTA: {question}"}]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except (httpx.HTTPError, KeyError, IndexError) as exc:
        logger.warning("LLM indisponível (%s) — usando modo extrativo.", exc)
        return None


def _area_in_text(text: str) -> Optional[dict]:
    t = strip_accents(text)
    return next((a for a in AREAS["areas"] if any(strip_accents(al) in t for al in a.get("aliases", []))), None)


def chat(message: str, tel, weather: Dict, area_id: Optional[str] = None, session_id: Optional[str] = None) -> ChatOut:
    clean = scrub_pii(message)
    score, level, factors, _ = assess(tel, weather)

    # 1) Triagem de ocorrência (relato de emergência)
    tri = triage.handle(clean, session_id, area_id)
    sid = tri["session_id"]
    if tri.get("handled"):
        return ChatOut(answer=tri["answer"], risk_level=level, sources=tri["sources"], grounded=True,
                       mode="triage", session_id=sid, intent="ocorrencia", triage=tri["triage"])

    # 2) Dúvida -> RAG
    docs = [d for d in retriever.search(clean, k=3) if d["score"] >= MIN_RELEVANCE]
    area = _area_in_text(clean) or next((a for a in AREAS["areas"] if a["id"] == area_id), None)
    asks_route = bool({"rota", "fuga", "abrigo", "sair", "evacuar", "ir"} & set(normalize(clean)))
    if area and asks_route and not any(d["id"] == area["rota"] for d in docs):
        docs.insert(0, {**retriever.get(area["rota"]), "score": 99})

    wants_forecast = bool(FORECAST_TERMS & set(normalize(clean)))
    status_line = f"Risco atual: {level.value} (índice {score:.0f}/100). " + factors[0] + "."
    outlook = daily_outlook(weather)
    forecast_txt = "\n".join(f"• {d['date']}: {d['rain_mm']:.0f} mm previstos → {d['level']}" for d in outlook)

    if not docs and not wants_forecast:
        answer = ("Não encontrei essa informação nos protocolos oficiais disponíveis. "
                  "Para orientação, ligue para a Defesa Civil (199) ou, em emergência, Bombeiros (193). "
                  "Se quiser relatar uma ocorrência, descreva o que está acontecendo e onde.")
        out = ChatOut(answer=answer, risk_level=level, sources=[], grounded=False, mode="fallback",
                      session_id=sid, intent="fora_escopo")
    else:
        context = "\n".join(f"[{d['id']}] {d['titulo']}: {d['texto']}" for d in docs)
        context += f"\n[STATUS] {status_line}\n[PREVISAO]\n{forecast_txt}"
        llm = _call_llm(clean, context)
        if llm:
            answer, mode = llm, "llm"
        else:  # Modo extrativo: 100% composto de trechos da base — impossível alucinar
            parts = [status_line]
            if wants_forecast:
                parts.append("Previsão para os próximos dias:\n" + forecast_txt)
            parts += [f"📘 {d['titulo']} [{d['id']}]: {d['texto']}" for d in docs[:2]]
            answer, mode = "\n\n".join(parts), "extractive"
        out = ChatOut(answer=answer, risk_level=level, sources=[d["id"] for d in docs], grounded=True,
                      mode=mode, session_id=sid, intent="duvida")

    audit.log_decision("chat", {"question": clean, "area_id": area_id, "retrieved": [d["id"] for d in docs]},
                       {"mode": out.mode, "grounded": out.grounded, "risk_level": level.value, "intent": out.intent})
    return out
