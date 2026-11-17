"""[ATUALIZADO] Clima real (OpenWeatherMap) + fallback automático.

Endpoints usados (plano gratuito):
  - /data/2.5/weather   -> clima atual
  - /data/2.5/forecast  -> previsão 5 dias em blocos de 3h (agregada por dia aqui)

Cadeia de resiliência:
  1. Sem OPENWEATHER_API_KEY            -> mock local (source="mock")
  2. Cache válido (TTL)                 -> retorna cache (evita estourar o limite gratuito)
  3. Erro de rede/HTTP/JSON             -> último dado real em cache, se houver (source="openweathermap_cache")
  4. Sem cache                           -> mock local (source="mock_fallback")
A aplicação NUNCA recebe exceção deste módulo."""
import logging
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx

from ..config import settings

logger = logging.getLogger("aquaguard.weather")
OWM = "https://api.openweathermap.org/data/2.5"
_lock = threading.Lock()
_CACHE: Dict[str, Any] = {"ts": 0.0, "data": None}
STATUS: Dict[str, Any] = {"mode": "mock" if not settings.openweather_api_key else "real",
                          "last_success": None, "last_error": None, "calls": 0, "failures": 0}

# Perfis de mock alinhados aos cenários do simulador IoT
_MOCK_PROFILES = {
    "normal":                  {"temp": 26, "desc": "parcialmente nublado", "rain_1h": 0.0, "daily": [2, 0, 5, 1, 0]},
    "chuva_moderada":          {"temp": 22, "desc": "chuva moderada",       "rain_1h": 6.0, "daily": [35, 28, 12, 5, 2]},
    "transbordamento_critico": {"temp": 20, "desc": "chuva muito forte",    "rain_1h": 25.0, "daily": [78, 55, 30, 10, 4]},
}


def _mock(scenario: str, source: str = "mock", reason: Optional[str] = None) -> Dict[str, Any]:
    p = _MOCK_PROFILES.get(scenario, _MOCK_PROFILES["normal"])
    today = datetime.now().date()
    return {
        "source": source,
        "fallback_reason": reason,
        "city": settings.city_name,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "current": {"temp_c": p["temp"], "feels_like_c": p["temp"], "description": p["desc"],
                    "humidity": 85 if p["rain_1h"] else 60, "wind_kmh": 12.0, "rain_1h_mm": p["rain_1h"], "icon": None},
        "forecast": [
            {"date": (today + timedelta(days=i)).isoformat(), "rain_mm": mm, "pop": round(min(1.0, mm / 40), 2),
             "temp_min": p["temp"] - 4, "temp_max": p["temp"] + 3, "description": p["desc"] if mm else "sem chuva"}
            for i, mm in enumerate(p["daily"])
        ],
    }


def _aggregate_forecast(raw: Dict[str, Any], tz_offset_s: int) -> list:
    """Agrega blocos de 3h por dia LOCAL da cidade (usa o offset de fuso retornado pela API)."""
    days: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"rain_mm": 0.0, "pop": 0.0, "temps": [], "desc": []})
    for item in raw.get("list", []):
        local = datetime.fromtimestamp(item["dt"] + tz_offset_s, tz=timezone.utc)
        d = local.date().isoformat()
        days[d]["rain_mm"] += item.get("rain", {}).get("3h", 0.0)
        days[d]["pop"] = max(days[d]["pop"], item.get("pop", 0.0))
        days[d]["temps"].append(item["main"]["temp"])
        days[d]["desc"].append(item["weather"][0]["description"])
    out = []
    for d, v in sorted(days.items()):
        out.append({"date": d, "rain_mm": round(v["rain_mm"], 1), "pop": round(v["pop"], 2),
                    "temp_min": round(min(v["temps"]), 1), "temp_max": round(max(v["temps"]), 1),
                    "description": max(set(v["desc"]), key=v["desc"].count)})
    return out[:5]


def _fetch_real() -> Dict[str, Any]:
    params = {"lat": settings.city_lat, "lon": settings.city_lon, "appid": settings.openweather_api_key,
              "units": "metric", "lang": "pt_br"}
    with httpx.Client(timeout=settings.weather_timeout_s) as client:
        cur = client.get(f"{OWM}/weather", params=params)
        cur.raise_for_status()
        fc = client.get(f"{OWM}/forecast", params=params)
        fc.raise_for_status()
    c, f = cur.json(), fc.json()
    tz = f.get("city", {}).get("timezone", c.get("timezone", 0))
    return {
        "source": "openweathermap",
        "fallback_reason": None,
        "city": c.get("name") or settings.city_name,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "current": {"temp_c": round(c["main"]["temp"], 1), "feels_like_c": round(c["main"]["feels_like"], 1),
                    "description": c["weather"][0]["description"], "humidity": c["main"]["humidity"],
                    "wind_kmh": round(c.get("wind", {}).get("speed", 0) * 3.6, 1),
                    "rain_1h_mm": c.get("rain", {}).get("1h", 0.0), "icon": c["weather"][0]["icon"]},
        "forecast": _aggregate_forecast(f, tz),
    }


def get_weather(scenario: str = "normal") -> Dict[str, Any]:
    if not settings.openweather_api_key:
        STATUS["mode"] = "mock"
        return _mock(scenario, "mock", "OPENWEATHER_API_KEY não configurada")

    with _lock:
        if _CACHE["data"] and time.time() - _CACHE["ts"] < settings.weather_cache_ttl_s:
            return _CACHE["data"]
        STATUS["calls"] += 1
        try:
            data = _fetch_real()
            _CACHE.update(ts=time.time(), data=data)
            STATUS.update(mode="real", last_success=data["fetched_at"], last_error=None)
            return data
        except httpx.HTTPStatusError as exc:
            reason = f"HTTP {exc.response.status_code}" + (" (chave inválida/ainda não ativada)" if exc.response.status_code == 401 else "")
        except httpx.HTTPError as exc:
            reason = f"falha de rede: {exc.__class__.__name__}"
        except (KeyError, ValueError, TypeError) as exc:
            reason = f"resposta inesperada: {exc}"
        STATUS.update(mode="fallback", last_error=reason, failures=STATUS["failures"] + 1)
        logger.warning("OpenWeatherMap indisponível (%s) — aplicando fallback.", reason)
        if _CACHE["data"]:  # último dado REAL conhecido é melhor que mock
            return {**_CACHE["data"], "source": "openweathermap_cache", "fallback_reason": reason}
        return _mock(scenario, "mock_fallback", reason)


def weather_status() -> Dict[str, Any]:
    return {**STATUS, "api_key_configured": bool(settings.openweather_api_key),
            "city": settings.city_name, "lat": settings.city_lat, "lon": settings.city_lon,
            "cache_ttl_s": settings.weather_cache_ttl_s,
            "cache_age_s": round(time.time() - _CACHE["ts"], 1) if _CACHE["data"] else None}
