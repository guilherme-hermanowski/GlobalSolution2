"""Contratos de dados (Pydantic v2) — primeira linha de defesa da qualidade de dados.
Qualquer payload fora das faixas físicas plausíveis é rejeitado com HTTP 422."""
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Literal, Optional

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


# ============================================================ IoT
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


# ============================================================ Alertas
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


# ============================================================ [NOVO] Contatos e disparos
Channel = Literal["whatsapp", "email"]


class ContactIn(BaseModel):
    """Cadastro do cidadão. Consentimento LGPD é obrigatório (art. 7º, I)."""
    name: str = Field(..., min_length=2, max_length=60)
    phone: Optional[str] = Field(None, description="Celular/WhatsApp com DDD, ex.: (11) 98765-4321")
    email: Optional[str] = Field(None, max_length=120)
    area_id: str = Field(..., pattern=r"^[A-Z]\d$")
    channels: List[Channel] = ["whatsapp"]
    consent: bool = Field(..., description="Aceite para receber alertas")

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v):
        if v is None or not v.strip():
            return None
        digits = re.sub(r"\D", "", v)
        if digits.startswith("55") and len(digits) in (12, 13):
            digits = digits[2:]
        # DDD válido (11-99) + celular com 9 dígitos começando com 9 (ou fixo de 8 dígitos)
        if not re.fullmatch(r"[1-9][1-9](9\d{8}|[2-5]\d{7})", digits):
            raise ValueError("telefone inválido — use DDD + número, ex.: 11987654321")
        return "55" + digits  # formato E.164 sem '+', exigido pelo wa.me

    @field_validator("email")
    @classmethod
    def check_email(cls, v):
        if v and not re.fullmatch(r"[\w.+-]+@[\w-]+\.[\w.]+", v.strip()):
            raise ValueError("e-mail inválido")
        return v.strip().lower() if v else None

    @model_validator(mode="after")
    def rules(self):
        if not self.consent:
            raise ValueError("é necessário consentir com o recebimento de alertas (LGPD)")
        if "whatsapp" in self.channels and not self.phone:
            raise ValueError("canal WhatsApp exige telefone")
        if "email" in self.channels and not self.email:
            raise ValueError("canal e-mail exige e-mail")
        if not self.phone and not self.email:
            raise ValueError("informe telefone ou e-mail")
        return self


class ContactOut(BaseModel):
    id: str
    name: str
    phone_masked: Optional[str]
    email_masked: Optional[str]
    area_id: str
    channels: List[str]
    created_at: datetime


class DispatchIn(BaseModel):
    level: RiskLevel = RiskLevel.VERMELHO
    area_ids: Optional[List[str]] = None   # None = todas as áreas afetadas
    test: bool = True                      # mensagens de teste recebem o prefixo [SIMULAÇÃO]
    note: Optional[str] = Field(None, max_length=200)


class DispatchMessage(BaseModel):
    contact_id: str
    contact_name: str
    channel: str
    recipient_masked: str
    link: str                 # wa.me / mailto — encaminhamento em 1 clique
    status: Literal["link_gerado"] = "link_gerado"


class DispatchOut(BaseModel):
    id: str
    created_at: datetime
    trigger: Literal["manual", "teste_rapido", "automatico"]
    level: RiskLevel
    area_ids: List[str]
    text: str
    protocol_refs: List[str]
    messages: List[DispatchMessage]
    total: int
    share_link: str           # wa.me sem número: compartilhar em grupos de moradores


# ============================================================ Chat + [NOVO] triagem
class ChatIn(BaseModel):
    message: str = Field(..., min_length=2, max_length=500)
    area_id: Optional[str] = None
    session_id: Optional[str] = Field(None, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")


class TriageInfo(BaseModel):
    status: Literal["coletando", "registrada"]
    occurrence_id: Optional[str] = None
    extracted: Dict[str, object] = {}
    missing: List[str] = []
    priority: Optional[str] = None


class ChatOut(BaseModel):
    answer: str
    risk_level: RiskLevel
    sources: List[str]
    grounded: bool
    mode: Literal["llm", "extractive", "fallback", "triage"]
    session_id: Optional[str] = None
    intent: Literal["duvida", "ocorrencia", "fora_escopo"] = "duvida"
    triage: Optional[TriageInfo] = None


class Occurrence(BaseModel):
    id: str
    created_at: datetime
    area_id: Optional[str]
    area_name: Optional[str]
    location_text: Optional[str]      # referência textual (rua/ponto) — sem GPS
    types: List[str]
    priority: Literal["P1", "P2", "P3"]
    people_at_risk: Optional[int]
    vulnerable: List[str]
    description: str                  # relato com PII removida
    status: Literal["aberta", "em_atendimento", "encerrada"] = "aberta"
    guidance_refs: List[str]
    session_ref: str                  # pseudônimo da sessão


class OccurrenceStatusIn(BaseModel):
    status: Literal["aberta", "em_atendimento", "encerrada"]
