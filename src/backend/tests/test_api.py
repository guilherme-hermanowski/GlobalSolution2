"""Testes de qualidade/resiliência:  pytest -q"""
from fastapi.testclient import TestClient

from app.main import app

c = TestClient(app)
H = {"X-Device-Token": "fiap-gs-2026"}


def test_health_sem_hardware():
    r = c.get("/api/health")
    assert r.status_code == 200


def test_fallback_quando_esp32_offline():
    r = c.get("/api/telemetry/latest").json()
    assert r["source"] in ("simulated_fallback", "simulated", "real")


def test_payload_invalido_rejeitado():
    r = c.post("/api/telemetry", headers=H, json={"device_id": "esp32-01", "river_level_cm": -5,
                                                    "rain_intensity": 10, "rain_detected": True})
    assert r.status_code == 422


def test_token_obrigatorio():
    r = c.post("/api/telemetry", json={"device_id": "esp32-01", "river_level_cm": 100,
                                       "rain_intensity": 0, "rain_detected": False})
    assert r.status_code == 401


def test_cenario_critico_gera_vermelho():
    r = c.post("/api/simulation/scenario", json={"scenario": "transbordamento_critico"}).json()
    assert r["alert"]["level"] == "VERMELHO"
    assert r["telemetry"]["source"] == "simulated"


def test_chat_fundamentado_e_recusa_fora_do_escopo():
    ok = c.post("/api/chat", json={"message": "Qual a rota de fuga do Jardim Ribeirinho?"}).json()
    assert ok["grounded"] and "ROTA-A1" in ok["sources"]
    fora = c.post("/api/chat", json={"message": "Qual o resultado do jogo de futebol ontem?"}).json()
    assert fora["grounded"] is False


def test_pii_removida_do_audit():
    c.post("/api/chat", json={"message": "Meu CPF é 123.456.789-00, o que levar no kit?"})
    last = c.get("/api/audit?n=1").json()[0]
    assert "123.456.789-00" not in str(last)
