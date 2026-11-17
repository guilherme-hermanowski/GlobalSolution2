"""Motor de risco explicável (determinístico) — a IA generativa NÃO decide o nível de risco,
apenas o comunica. Isso evita alucinação em uma decisão crítica de segurança.

score (0-100) = 45% nível do rio + 20% chuva no sensor + 25% previsão 24-48h + 10% histórico da área"""
import json
from typing import Dict, List, Tuple

from ..config import DATA_DIR, settings
from ..schemas import RiskLevel, TelemetryOut

_HIST = json.loads((DATA_DIR / "historico_alagamentos.json").read_text(encoding="utf-8"))["ocorrencias"]
AREAS = json.loads((DATA_DIR / "areas_risco.json").read_text(encoding="utf-8"))


def historical_factor(area_id: str) -> float:
    occ = [o for o in _HIST if o["area"] == area_id]
    weight = {"baixa": 0.3, "media": 0.6, "alta": 1.0}
    return min(1.0, sum(weight[o["gravidade"]] for o in occ) / 3)


def assess(tel: TelemetryOut, weather: Dict) -> Tuple[float, RiskLevel, List[str], Dict[str, float]]:
    factors: List[str] = []
    river = min(1.0, tel.river_level_cm / settings.river_overflow_cm)
    rain_sensor = tel.rain_intensity / 100
    fc = weather.get("forecast", [])
    rain_48h = sum(d["rain_mm"] for d in fc[:2])
    forecast = min(1.0, rain_48h / 100)  # 100 mm em 48h => saturação
    hist = max(historical_factor(a["id"]) for a in AREAS["areas"])

    score = round(100 * (0.45 * river + 0.20 * rain_sensor + 0.25 * forecast + 0.10 * hist), 1)

    if tel.river_level_cm >= settings.river_overflow_cm:
        factors.append(f"Rio em {tel.river_level_cm:.0f} cm — ACIMA da cota de transbordamento ({settings.river_overflow_cm:.0f} cm)")
    elif tel.river_level_cm >= settings.river_alert_cm:
        factors.append(f"Rio em {tel.river_level_cm:.0f} cm — acima da cota de alerta ({settings.river_alert_cm:.0f} cm)")
    else:
        factors.append(f"Rio em {tel.river_level_cm:.0f} cm — dentro da normalidade")
    if tel.rain_detected:
        factors.append(f"Sensor detecta chuva ({tel.rain_intensity:.0f}% de intensidade)")
    if fc:
        factors.append(f"Previsão de {rain_48h:.0f} mm de chuva nas próximas 48h ({weather.get('source')})")
    if hist >= 0.6:
        factors.append("Áreas com histórico recorrente de alagamento")

    if tel.river_level_cm >= settings.river_overflow_cm or score >= 75:
        level = RiskLevel.VERMELHO
    elif tel.river_level_cm >= settings.river_alert_cm or score >= 40 or (fc and fc[0]["rain_mm"] >= 30):
        level = RiskLevel.AMARELO
    else:
        level = RiskLevel.VERDE
    if tel.source != "real":
        factors.append(f"Dados do sensor: {tel.source.upper()} (não provenientes de hardware físico)")
    components = {"rio": round(river, 2), "chuva_sensor": round(rain_sensor, 2),
                  "previsao_48h": round(forecast, 2), "historico": round(hist, 2)}
    return score, level, factors, components


def daily_outlook(weather: Dict) -> List[Dict]:
    out = []
    for d in weather.get("forecast", []):
        lvl = RiskLevel.VERMELHO if d["rain_mm"] >= 50 else RiskLevel.AMARELO if d["rain_mm"] >= 30 else RiskLevel.VERDE
        out.append({**d, "level": lvl.value})
    return out


def affected_areas(level: RiskLevel) -> List[Dict]:
    return [a for a in AREAS["areas"]
            if level == RiskLevel.VERMELHO or (level == RiskLevel.AMARELO and a["vulnerabilidade"] >= 0.7)]
