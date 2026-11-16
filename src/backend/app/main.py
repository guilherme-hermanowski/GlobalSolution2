"""AquaGuard / AlertaCidadão — API FastAPI.
Executar:  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
Docs:      http://localhost:8000/docs"""
import logging

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import LOG_DIR, settings
from .schemas import Alert, ChatIn, ChatOut, ScenarioIn, TelemetryIn
from .services import agent, audit
from .services.risk_engine import AREAS
from .services.telemetry import store
from .services.weather import get_weather

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                    handlers=[logging.StreamHandler(), logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8")])
logger = logging.getLogger("aquaguard.api")

app = FastAPI(title="AquaGuard / AlertaCidadão API", version="1.0.0",
              description="POC FIAP Global Solution — prevenção de enchentes (ODS 11 e 13)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ------------------------------------------------------------- tratamento de erros
@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    logger.warning("Payload rejeitado em %s: %s", request.url.path, exc.errors())
    return JSONResponse(status_code=422, content={"error": "payload_invalido",
                                                  "detail": [{"campo": ".".join(map(str, e["loc"])), "msg": e["msg"]}
                                                             for e in exc.errors()]})


@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    logger.exception("Erro não tratado em %s", request.url.path)
    return JSONResponse(status_code=500, content={"error": "erro_interno", "detail": "Falha temporária. Tente novamente."})


def verify_device(x_device_token: str = Header(default="")):
    if x_device_token != settings.device_token:
        raise HTTPException(status_code=401, detail="Token de dispositivo inválido")


# ------------------------------------------------------------- helpers
def snapshot():
    tel = store.latest()
    weather = get_weather(store.scenario)
    return tel, weather


# ------------------------------------------------------------- rotas
@app.get("/api/health")
def health():
    tel = store.latest()
    return {"status": "ok", "esp32_online": tel.online, "telemetry_source": tel.source,
            "weather_mode": "real" if settings.openweather_api_key else "mock",
            "llm_mode": "llm" if settings.openai_api_key else "extractive", "scenario": store.scenario}


@app.post("/api/telemetry", status_code=201, dependencies=[Depends(verify_device)])
def ingest(payload: TelemetryIn):
    if payload.source != "real" and payload.scenario:
        store.scenario = payload.scenario.value
    rec = store.add(payload)
    tel, weather = snapshot()
    alert = agent.proactive_analysis(tel, weather)  # análise proativa a cada leitura
    return {"stored": True, "device_ref": rec["device_ref"], "risk_level": alert.level, "score": alert.score}


@app.get("/api/telemetry/latest")
def telemetry_latest():
    return store.latest()


@app.get("/api/telemetry/history")
def telemetry_history(n: int = 50):
    return store.history(min(max(n, 1), 500))


@app.get("/api/weather")
def weather():
    return get_weather(store.scenario)


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


@app.post("/api/chat", response_model=ChatOut)
def chat(body: ChatIn):
    tel, weather = snapshot()
    return agent.chat(body.message, tel, weather, body.area_id)


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
