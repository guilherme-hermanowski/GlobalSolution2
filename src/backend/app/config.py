"""Configuração central. Lê variáveis de ambiente (.env opcional).
Nenhuma variável é obrigatória: a ausência ativa os modos de fallback."""
import os
from pathlib import Path

try:  # python-dotenv é opcional
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)


class Settings:
    openweather_api_key: str = os.getenv("OPENWEATHER_API_KEY", "").strip()
    city_lat: float = float(os.getenv("CITY_LAT", "-23.5505"))
    city_lon: float = float(os.getenv("CITY_LON", "-46.6333"))
    city_name: str = os.getenv("CITY_NAME", "São Paulo")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    telemetry_timeout_s: int = int(os.getenv("TELEMETRY_TIMEOUT_S", "60"))
    privacy_salt: str = os.getenv("PRIVACY_SALT", "troque-este-sal")
    device_token: str = os.getenv("DEVICE_TOKEN", "fiap-gs-2026")
    # Parâmetros físicos do ponto monitorado (régua do rio)
    river_alert_cm: float = 250.0     # cota de alerta
    river_overflow_cm: float = 350.0  # cota de transbordamento


settings = Settings()
