"""Armazenamento de telemetria + Modo Simulação / Fallback Inteligente.

Regras de resiliência:
1. Leitura REAL recente (< TELEMETRY_TIMEOUT_S)  -> usada normalmente (source=real).
2. Leitura SIMULADA recente (iot_simulator.py)   -> usada e rotulada (source=simulated).
3. Nenhuma leitura recente (ESP32 offline)       -> backend gera leitura sintética do cenário
   ativo (source=simulated_fallback). A API NUNCA quebra por falta de hardware."""
import random
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict

from ..config import settings
from ..schemas import DataSource, Scenario, TelemetryIn, TelemetryOut
from .privacy import generalize_location, pseudonymize

SCENARIO_PROFILES: Dict[str, Dict[str, tuple]] = {
    Scenario.NORMAL.value:          {"river": (80, 140),  "rain": (0, 5)},
    Scenario.CHUVA_MODERADA.value:  {"river": (220, 280), "rain": (35, 60)},
    Scenario.TRANSBORDAMENTO.value: {"river": (340, 400), "rain": (80, 100)},
}


class TelemetryStore:
    def __init__(self, maxlen: int = 500):
        self._history: Deque[dict] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self.scenario: str = Scenario.NORMAL.value

    def add(self, t: TelemetryIn) -> dict:
        rec = {
            "device_ref": pseudonymize(t.device_id),
            "river_level_cm": t.river_level_cm,
            "rain_intensity": t.rain_intensity,
            "rain_detected": t.rain_detected,
            "source": t.source,
            "zone": generalize_location(t.lat, t.lon),   # lat/lon brutos NÃO são armazenados
            "received_at": datetime.now(timezone.utc),
        }
        with self._lock:
            self._history.append(rec)
        return rec

    def set_scenario(self, scenario: Scenario) -> dict:
        """Usado pelo painel da Defesa Civil: troca o cenário e injeta leitura imediata."""
        self.scenario = scenario.value
        return self.add(self.synthetic(DataSource.SIMULATED))

    def synthetic(self, source: DataSource) -> TelemetryIn:
        p = SCENARIO_PROFILES[self.scenario]
        rain = round(random.uniform(*p["rain"]), 1)
        return TelemetryIn(device_id="virtual-esp32-01", river_level_cm=round(random.uniform(*p["river"]), 1),
                           rain_intensity=rain, rain_detected=rain > 10, source=source,
                           lat=-23.5505, lon=-46.6333)

    def latest(self) -> TelemetryOut:
        with self._lock:
            last = self._history[-1] if self._history else None
        now = datetime.now(timezone.utc)
        stale = (now - last["received_at"]).total_seconds() if last else float("inf")
        online = stale <= settings.telemetry_timeout_s

        if not online:  # Graceful degradation: ESP32 offline => leitura sintética rotulada
            fb = self.synthetic(DataSource.FALLBACK)
            last = {"device_ref": pseudonymize(fb.device_id), "river_level_cm": fb.river_level_cm,
                    "rain_intensity": fb.rain_intensity, "rain_detected": fb.rain_detected,
                    "source": DataSource.FALLBACK, "zone": generalize_location(fb.lat, fb.lon),
                    "received_at": now}
        return TelemetryOut(
            **last,
            river_level_pct=round(100 * last["river_level_cm"] / settings.river_overflow_cm, 1),
            online=online,
            stale_seconds=round(stale, 1) if stale != float("inf") else -1,
        )

    def history(self, n: int = 50) -> list:
        with self._lock:
            return [dict(r, received_at=r["received_at"].isoformat()) for r in list(self._history)[-n:]]


store = TelemetryStore()
