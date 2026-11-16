"""Contratos de dados (Pydantic v2) — primeira linha de defesa da qualidade de dados.
Qualquer payload fora das faixas físicas plausíveis é rejeitado com HTTP 422."""
from datetime import datetime, timezone
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class DataSource(str, Enum):
    REAL = "real"                       # veio do ESP32 físico
    SIMULATED = "simulated"             # veio do iot_simulator.py / painel
    FALLBACK = "simulated_fallback"     # gerado pelo backend porque o ESP32 está offline


class Scenario(str, Enum):
    NORMAL = "normal"
    CHUVA_MODERADA = "chuva_moderada"
    TRANSBORDAMENTO = "transbordamento_critico"


class RiskLevel(str, Enum):
    VERDE = "VERDE"
    AMARELO = "AMARELO"
    VERMELHO = "VERMELHO"


class TelemetryIn(BaseModel):
    """Payload enviado pelo ESP32 (ou simulador)."""
    device_id: str = Field(..., min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_\-]+$")
    river_level_cm: float = Field(..., ge=0, le=1000, description="Nível do rio (cm acima do leito)")
    rain_intensity: float = Field(..., ge=0, le=100, description="Intensidade de chuva 0-100% (sensor resistivo)")
    rain_detected: bool
    battery_v: Optional[float] = Field(None, ge=0, le=5)
    rssi: Optional[int] = Field(None, ge=-120, le=0)
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lon: Optional[float] = Field(None, ge=-180, le=180)
    source: DataSource = DataSource.REAL
    scenario: Optional[Scenario] = None  # apenas simulador: sincroniza o mock de clima com o cenário
    timestamp: Optional[datetime] = None

    @field_validator("timestamp")
    @classmethod
    def no_future(cls, v):
        if v and v.tzinfo and v > datetime.now(timezone.utc):
            raise ValueError("timestamp no futuro")
        return v

    @model_validator(mode="after")
    def coherence(self):
        # Regra de qualidade: sensor de chuva digital e analógico devem ser coerentes
        if self.rain_detected is False and self.rain_intensity > 60:
            raise ValueError("incoerência: rain_detected=false com intensidade > 60%")
        return self


class TelemetryOut(BaseModel):
    device_ref: str              # ID pseudonimizado
    river_level_cm: float
    river_level_pct: float       # % da cota de transbordamento
    rain_intensity: float
    rain_detected: bool
    source: DataSource
    received_at: datetime
    zone: str                    # localização generalizada (grade ~1 km)
    online: bool
    stale_seconds: float


class ScenarioIn(BaseModel):
    scenario: Scenario


class ChatIn(BaseModel):
    message: str = Field(..., min_length=2, max_length=500)
    area_id: Optional[str] = None


class ChatOut(BaseModel):
    answer: str
    risk_level: RiskLevel
    sources: List[str]
    grounded: bool
    mode: Literal["llm", "extractive", "fallback"]


class Alert(BaseModel):
    id: str
    created_at: datetime
    level: RiskLevel
    score: float
    title: str
    summary: str
    factors: List[str]
    instructions: List[str]
    protocol_refs: List[str]
    data_source: DataSource
    affected_areas: List[str]
