"""Integração OpenWeatherMap (clima atual + previsão 5 dias / 3h) com fallback mockado.
Degradação graciosa: sem chave, timeout ou erro HTTP => dados mock coerentes com o cenário."""
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict

import httpx

from ..config import settings

logger = logging.getLogger("aquaguard.weather")
OWM = "https://api.openweathermap.org/data/2.5"
_CACHE: Dict[str, Any] = {"ts": 0, "data": None}
CACHE_TTL_S = 600  # respeita limites do plano gratuito

# Perfis de mock alinhados aos cenários do simulador IoT
_MOCK_PROFILES = {
    "normal":                  {"temp": 26, "desc": "parcialmente nublado", "rain_1h": 0.0, "daily": [2, 0, 5, 1, 0]},
    "chuva_moderada":          {"temp": 22, "desc": "chuva moderada",       "rain_1h": 6.0, "daily": [35, 28, 12, 5, 2]},
    "transbordamento_critico": {"temp": 20, "desc": "chuva muito forte",    "rain_1h": 25.0, "daily": [78, 55, 30, 10, 4]},
}


def _mock(scenario: str) -> Dict[str, Any]:
    p = _MOCK_PROFILES.get(scenario, _MOCK_PROFILES["normal"])
    today = datetime.now().date()
    return {
        "source": "mock",
        "city": settings.city_name,
        "current": {"temp_c": p["temp"], "description": p["desc"], "humidity": 85 if p["rain_1h"] else 60,
                    "rain_1h_mm": p["rain_1h"]},
        "forecast": [
            {"date": (today + timedelta(days=i)).isoformat(), "rain_mm": mm, "pop": min(1.0, mm / 40),
             "temp_min": p["temp"] - 4, "temp_max": p["temp"] + 3}
            for i, mm in enumerate(p["daily"])
        ],
    }


def _aggregate_forecast(raw: Dict[str, Any]) -> list:
    """A API gratuita retorna blocos de 3h; agregamos por dia (chuva acumulada, POP máx.)."""
    days: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"rain_mm": 0.0, "pop": 0.0, "temps": []})
    for item in raw.get("list", []):
        d = item["dt_txt"][:10]
        days[d]["rain_mm"] += item.get("rain", {}).get("3h", 0.0)
        days[d]["pop"] = max(days[d]["pop"], item.get("pop", 0.0))
        days[d]["temps"].append(item["main"]["temp"])
    return [{"date": d, "rain_mm": round(v["rain_mm"], 1), "pop": round(v["pop"], 2),
             "temp_min": round(min(v["temps"]), 1), "temp_max": round(max(v["temps"]), 1)}
            for d, v in sorted(days.items())][:5]


def get_weather(scenario: str = "normal") -> Dict[str, Any]:
    if not settings.openweather_api_key:
        return _mock(scenario)
    if _CACHE["data"] and time.time() - _CACHE["ts"] < CACHE_TTL_S:
        return _CACHE["data"]
    params = {"lat": settings.city_lat, "lon": settings.city_lon, "appid": settings.openweather_api_key,
              "units": "metric", "lang": "pt_br"}
    try:
        with httpx.Client(timeout=5.0) as client:
            cur = client.get(f"{OWM}/weather", params=params); cur.raise_for_status()
            fc = client.get(f"{OWM}/forecast", params=params); fc.raise_for_status()
        c = cur.json()
        data = {
            "source": "openweathermap",
            "city": c.get("name", settings.city_name),
            "current": {"temp_c": c["main"]["temp"], "description": c["weather"][0]["description"],
                        "humidity": c["main"]["humidity"], "rain_1h_mm": c.get("rain", {}).get("1h", 0.0)},
            "forecast": _aggregate_forecast(fc.json()),
        }
        _CACHE.update(ts=time.time(), data=data)
        return data
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.warning("OpenWeatherMap indisponível (%s) — usando mock.", exc)
        data = _mock(scenario)
        data["source"] = "mock_fallback"
        return data
