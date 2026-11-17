"""Testes de qualidade/resiliência:  pytest -q"""
from fastapi.testclient import TestClient

from app.config import LOG_DIR
from app.main import app
from app.services import weather as weather_mod

c = TestClient(app)
H = {"X-Device-Token": "fiap-gs-2026"}


# ------------------------------------------------------------- base (v1)
def test_health_sem_hardware():
    assert c.get("/api/health").status_code == 200


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


# ------------------------------------------------------------- [1] clima
def test_clima_sem_chave_usa_mock():
    w = c.get("/api/weather").json()
    assert w["source"] in ("mock", "openweathermap", "openweathermap_cache", "mock_fallback")
    assert len(w["forecast"]) == 5


def test_clima_falha_de_rede_cai_no_fallback(monkeypatch):
    import httpx
    monkeypatch.setattr(weather_mod.settings, "openweather_api_key", "chave-fake")
    monkeypatch.setitem(weather_mod._CACHE, "data", None)
    monkeypatch.setitem(weather_mod._CACHE, "ts", 0.0)

    def boom():
        raise httpx.ConnectError("sem rede")
    monkeypatch.setattr(weather_mod, "_fetch_real", boom)
    w = weather_mod.get_weather("normal")
    assert w["source"] == "mock_fallback" and "rede" in w["fallback_reason"]


# ------------------------------------------------------------- [2] contatos e disparos
def test_contato_valida_telefone_e_consentimento():
    bad = c.post("/api/contacts", json={"name": "Ana", "phone": "123", "area_id": "A1", "consent": True})
    assert bad.status_code == 422
    no_consent = c.post("/api/contacts", json={"name": "Ana", "phone": "(11) 98765-4321", "area_id": "A1", "consent": False})
    assert no_consent.status_code == 422


def test_disparo_gera_link_whatsapp_e_mascara_telefone():
    r = c.post("/api/contacts", json={"name": "Maria Teste", "phone": "(11) 98765-4321", "area_id": "A1",
                                      "channels": ["whatsapp"], "consent": True})
    assert r.status_code == 201 and r.json()["phone_masked"] == "+55 (11) 9****-4321"
    cid = r.json()["id"]
    d = c.post("/api/alerts/dispatch/test").json()
    msg = next(m for m in d["messages"] if m["contact_id"] == cid)
    assert msg["link"].startswith("https://wa.me/5511987654321?text=")
    assert "SIMULA" in d["text"] and d["level"] == "VERMELHO"
    assert c.delete(f"/api/contacts/{cid}").json()["deleted"]
    log = (LOG_DIR / "dispatch_log.jsonl").read_text(encoding="utf-8")
    assert "98765-4321" not in log and "5511987654321" not in log


# ------------------------------------------------------------- [3] triagem
def test_triagem_multi_turno_registra_ocorrencia():
    r1 = c.post("/api/chat", json={"message": "Socorro, a água entrou na minha casa e tenho dois idosos aqui"}).json()
    assert r1["intent"] == "ocorrencia" and r1["triage"]["status"] == "coletando"
    assert "localizacao" in r1["triage"]["missing"]
    r2 = c.post("/api/chat", json={"message": "Fica na Vila Baixada, rua da esperança perto da praça",
                                   "session_id": r1["session_id"]}).json()
    assert r2["triage"]["status"] == "registrada"
    assert r2["triage"]["priority"] == "P1"            # água em casa + idosos
    assert "ROTA-B2" in r2["sources"] or "ROTA-B2" in str(r2["answer"])
    occ = c.get("/api/occurrences").json()
    assert any(o["id"] == r2["triage"]["occurrence_id"] and o["area_id"] == "B2" for o in occ)


def test_duvida_nao_vira_ocorrencia():
    r = c.post("/api/chat", json={"message": "O que devo fazer se a água entrar em casa?"}).json()
    assert r["intent"] == "duvida" and "PROT-03" in r["sources"]


def test_pessoa_ilhada_e_p1_com_193():
    r = c.post("/api/chat", json={"message": "Estamos ilhados no telhado no Jardim Ribeirinho, 4 pessoas"}).json()
    assert r["triage"]["priority"] == "P1" and "193" in r["answer"] and "PROT-09" in r["sources"]
