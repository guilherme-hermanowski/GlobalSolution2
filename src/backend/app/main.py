"""AquaGuard / AlertaCidadão — API FastAPI (v2).
Executar:  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
Docs:      http://localhost:8000/docs"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, List

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import LOG_DIR, settings
from .schemas import (AdviceIn, Alert, ChatIn, ChatOut, ContactIn, ContactOut, DispatchIn, DispatchOut, Occurrence,
                      OccurrenceStatusIn, RiskLevel, ScenarioIn, TelemetryIn)
from .services import agent, audit, notifications, triage
from .services.chaves_llm import tem_chave_gemini
from .services.mqtt_listener import iniciar_mqtt_listener
from .services.risk_engine import AREAS
from .services.telemetry import store
from .services.weather import get_weather, weather_status

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                    handlers=[logging.StreamHandler(), logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8")])
logger = logging.getLogger("aquaguard.api")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    iniciar_mqtt_listener()
    yield


app = FastAPI(title="AquaGuard / AlertaCidadão API", version="2.0.0",
              description="POC FIAP Global Solution — prevenção de enchentes (ODS 11 e 13)", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ------------------------------------------------------------- tratamento de erros
@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    logger.warning("Payload rejeitado em %s", request.url.path)  # sem logar o corpo (pode conter PII)
    return JSONResponse(status_code=422, content={"error": "payload_invalido",
                                                  "detail": [{"campo": ".".join(map(str, e["loc"])),
                                                              "msg": e["msg"].replace("Value error, ", "")}
                                                             for e in exc.errors()]})


@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    logger.exception("Erro não tratado em %s", request.url.path)
    return JSONResponse(status_code=500, content={"error": "erro_interno", "detail": "Falha temporária. Tente novamente."})


def verify_device(x_device_token: str = Header(default="")):
    if x_device_token != settings.device_token:
        raise HTTPException(status_code=401, detail="Token de dispositivo inválido")


def snapshot():
    return store.latest(), get_weather(store.scenario)


# ------------------------------------------------------------- status
@app.get("/api/health")
def health():
    tel = store.latest()
    ws = weather_status()
    return {"status": "ok", "esp32_online": tel.online, "telemetry_source": tel.source,
            "weather_mode": ws["mode"], "llm_mode": "llm" if tem_chave_gemini() else "extractive",
            "scenario": store.scenario, "contacts": len(notifications.contacts.list()),
            "open_occurrences": sum(o.status != "encerrada" for o in triage.OCCURRENCES)}


# ------------------------------------------------------------- IoT
@app.post("/api/telemetry", status_code=201, dependencies=[Depends(verify_device)])
def ingest(payload: TelemetryIn):
    if payload.source != "real" and payload.scenario:
        store.scenario = payload.scenario.value
    rec = store.add(payload)
    tel, weather = snapshot()
    alert = agent.proactive_analysis(tel, weather)
    return {"stored": True, "device_ref": rec["device_ref"], "risk_level": alert.level, "score": alert.score}


@app.get("/api/telemetry/latest")
def telemetry_latest():
    return store.latest()


@app.get("/api/telemetry/history")
def telemetry_history(n: int = 50):
    return store.history(min(max(n, 1), 500))


# ------------------------------------------------------------- [1] clima
@app.get("/api/weather")
def weather():
    return get_weather(store.scenario)


@app.get("/api/weather/status")
def weather_diag():
    return weather_status()


# ------------------------------------------------------------- risco / alertas
@app.get("/api/risk", response_model=Alert)
def risk():
    tel, weather = snapshot()
    return agent.proactive_analysis(tel, weather)


@app.get("/api/alerts")
def alerts():
    return list(reversed(agent.ALERTS))


@app.get("/api/areas")
def areas():
    return AREAS


# ------------------------------------------------------------- [2] contatos e disparos
@app.post("/api/contacts", response_model=ContactOut, status_code=201)
def add_contact(body: ContactIn):
    return notifications.contacts.add(body)


@app.get("/api/contacts", response_model=List[ContactOut])
def list_contacts():
    return notifications.contacts.list()


@app.delete("/api/contacts/{contact_id}")
def delete_contact(contact_id: str):
    if not notifications.contacts.delete(contact_id):
        raise HTTPException(404, "Contato não encontrado")
    return {"deleted": True}


@app.post("/api/alerts/dispatch", response_model=DispatchOut)
def dispatch_alert(body: DispatchIn):
    return notifications.dispatch(body.level, body.area_ids, trigger="manual", test=body.test, note=body.note)


@app.post("/api/alerts/dispatch/test", response_model=DispatchOut)
def dispatch_quick_test():
    """Botão de teste rápido: coloca o sistema em 'Transbordamento Crítico' e dispara alerta VERMELHO simulado."""
    store.set_scenario(ScenarioIn(scenario="transbordamento_critico").scenario)
    tel, weather = snapshot()
    agent.proactive_analysis(tel, weather, auto_dispatch=False)  # evita disparo duplicado
    return notifications.dispatch(RiskLevel.VERMELHO, None, trigger="teste_rapido", test=True)


@app.get("/api/alerts/dispatches", response_model=List[DispatchOut])
def list_dispatches():
    return list(reversed(notifications.DISPATCHES))


# ------------------------------------------------------------- [3] chat + triagem
@app.post("/api/chat", response_model=ChatOut)
def chat(body: ChatIn):
    tel, weather = snapshot()
    return agent.chat(body.message, tel, weather, body.area_id, body.session_id)


@app.post("/api/advice", response_model=ChatOut)
def advice(body: AdviceIn):
    """Botão "O que fazer?" (manual) ou alerta vermelho automático (auto_red) — usa a
    última leitura do MQTT/telemetria pra gerar uma orientação via Gemini."""
    tel, weather = snapshot()
    return agent.generate_advice(body.trigger, tel, weather, body.location, body.session_id)


@app.get("/api/occurrences", response_model=List[Occurrence])
def list_occurrences():
    order = {"P1": 0, "P2": 1, "P3": 2}
    return sorted(triage.OCCURRENCES, key=lambda o: (o.status == "encerrada", order[o.priority], -o.created_at.timestamp()))


@app.patch("/api/occurrences/{occ_id}", response_model=Occurrence)
def update_occurrence(occ_id: str, body: OccurrenceStatusIn):
    occ = triage.set_status(occ_id, body.status)
    if not occ:
        raise HTTPException(404, "Ocorrência não encontrada")
    audit.log_decision("occurrence_status", {"occurrence_id": occ_id}, {"status": body.status})
    return occ


# ------------------------------------------------------------- simulação / auditoria
@app.post("/api/simulation/scenario")
def set_scenario(body: ScenarioIn):
    store.set_scenario(body.scenario)
    tel, weather = snapshot()
    alert = agent.proactive_analysis(tel, weather)
    logger.info("Cenário de simulação alterado para %s", body.scenario.value)
    return {"scenario": store.scenario, "telemetry": tel, "alert": alert}


@app.get("/api/simulation/status")
def sim_status():
    return {"scenario": store.scenario, "available": ["normal", "chuva_moderada", "transbordamento_critico"]}


@app.get("/api/audit")
def audit_log(n: int = 20):
    return audit.read_last(min(max(n, 1), 200))
