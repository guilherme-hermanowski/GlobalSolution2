# FIAP - Faculdade de Informática e Administração Paulista

## Global Solution — CitizenTech

# 💧 AquaGuard / AlertaCidadão — v2

## 👨‍🎓 Integrantes
- <a href="https://www.linkedin.com/company/inova-fusca">Guilherme Campos Hermanowski </a>
- <a href="https://www.linkedin.com/company/inova-fusca">Fatima Candal</a>
- <a href="https://www.linkedin.com/company/inova-fusca"> Matheus Alboredo Soares</a> 
- <a href="https://www.linkedin.com/company/inova-fusca">Jonathan Willian Luft </a>
- <a href="https://www.linkedin.com/company/inova-fusca">Ana Belchior </a>

## 👩‍🏫 Professores
- Tutor(a): Nome · Coordenador(a): Nome

## 📜 Descrição
Sistema de **prevenção de enchentes em áreas urbanas vulneráveis** (ODS 11 — Cidades Sustentáveis; ODS 13 — Ação Climática).
Um ESP32 mede o nível do rio e a chuva; o backend cruza a telemetria com a **previsão real do OpenWeatherMap** e o histórico;
um **Agente de IA com RAG** gera alertas, **dispara avisos por WhatsApp/e-mail** e faz a **triagem de ocorrências** relatadas pelos cidadãos.

> **Modo Simulação / Fallback Inteligente:** funciona 100% **sem hardware**, sem chave de clima e sem chave de LLM.
> Todo dado exibido é rotulado (`real`, `simulated`, `simulated_fallback`, `openweathermap`, `mock`...).

### Novidades da v2
| Pilar | O que entrou |
|---|---|
| 🌦️ Clima real | OpenWeatherMap (atual + 5 dias) com fallback automático real → cache → mock |
| 📣 Contatos e disparos | Cadastro de WhatsApp/e-mail com consentimento, links `wa.me`/`mailto`, botão de teste rápido, auditoria de disparos |
| 🆘 Triagem | Chat identifica relatos de emergência, extrai local e tipo, registra ocorrência P1–P3 e orienta com base nos protocolos |

Detalhes em [`document/INTEGRACAO_v2.md`](document/INTEGRACAO_v2.md) e [`document/arquitetura.md`](document/arquitetura.md).

## 📁 Estrutura de pastas
```
aquaguard-alertacidadao/
├── assets/  config/  scripts/
├── document/                   # arquitetura.md · INTEGRACAO_v2.md
├── src/
│   ├── iot/
│   │   └── firmware/aquaguard_esp32/        # aquaguard_esp32.ino · diagram.json (Wokwi) · secrets.h
│   ├── backend/
│   │   ├── app/
│   │   │   ├── main.py · config.py · schemas.py
│   │   │   └── services/
│   │   │       ├── telemetry.py      # store + fallback inteligente
│   │   │       ├── weather.py        # [v2] OpenWeatherMap + cache + mock
│   │   │       ├── risk_engine.py    # score explicável
│   │   │       ├── rag.py            # [v2] BM25 sobre protocolos + áreas
│   │   │       ├── agent.py          # [v2] análise proativa + roteamento do chat
│   │   │       ├── triage.py         # [v2] agente de triagem de ocorrências
│   │   │       ├── notifications.py  # [v2] contatos + disparos wa.me/mailto
│   │   │       ├── mqtt_listener.py  # assina o tópico MQTT do ESP32 (HiveMQ Cloud)
│   │   │       ├── audit.py · privacy.py
│   │   ├── data/                     # protocolos, áreas/rotas/abrigos, histórico
│   │   ├── logs/                     # app.log · audit_ia.jsonl · dispatch_log.jsonl · ocorrencias.jsonl
│   │   └── tests/test_api.py         # 14 testes
│   ├── web/                          # Painel (abas: Monitoramento · Contatos & Disparos · Ocorrências & Chat)
│   └── mobile/                       # App (Início · Assistente · Alertas · Receber alertas)
└── README.md
```

## 🔧 Como executar
Pré-requisitos: Python 3.10+, Node 18+.
```bash
# 1) Backend
cd src/backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # opcional: OPENWEATHER_API_KEY / GEMINI_API_KEYS / MQTT_*
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000      # Swagger: http://localhost:8000/docs
pytest -q

# 2) Painel web
cd src/web && npm install && npm run dev                       # http://localhost:5173

# 3) IoT — ESP32 via Wokwi (substitui o antigo simulador local)
# cp src/iot/firmware/aquaguard_esp32/secrets.example.h  ->  secrets.h  (preencha e NÃO commite)
# preencha também MQTT_SERVER/MQTT_USER/MQTT_PASSWORD no .env do backend (mesmo broker)
# abra https://wokwi.com, crie um projeto ESP32 (Arduino), cole aquaguard_esp32.ino e diagram.json
# (libraries.txt já lista PubSubClient/ArduinoJson — o Wokwi instala sozinho) e clique em ▶ play.
# Arraste o slider do HC-SR04 (nível do rio) e o potenciômetro (chuva, 0-100%).

# 4) App do Cidadão
cd src/mobile && npm install && npx expo install --fix && npx expo start
```
No app, ajuste `src/mobile/src/config.js` com o IP do backend. Windows: `scripts\start_demo.bat`.

## 🎬 Roteiro de apresentação (≈5 min)
1. **Monitoramento**: semáforo verde; mostre a etiqueta do clima (real ou mock) e do sensor (SIMULADO/FALLBACK).
2. **Contatos & Disparos**: cadastre seu próprio WhatsApp (área A1) com consentimento.
3. Clique **⚡ TESTE RÁPIDO** → painel fica VERMELHO, mensagem aparece na prévia → clique "enviar →" e o WhatsApp abre com o alerta pronto.
4. **Ocorrências & Chat**: clique "Socorro, a água entrou na minha casa e tenho dois idosos aqui" → agente pergunta a localização → responda "Vila Baixada, rua da esperança" → ocorrência **P1** com rota ROTA-B2.
5. Pergunte "Qual a rota de fuga da Vila Baixada?" (dúvida → RAG) e algo fora do escopo (recusa segura). Mostre a auditoria.

## 🛡️ Governança
| Pilar | Implementação |
|---|---|
| Qualidade de dados | Pydantic: faixas físicas, coerência entre sensores, celular BR validado e normalizado (E.164), consentimento obrigatório |
| Resiliência | Clima real → cache → mock; ESP32 offline → leitura sintética rotulada; buffer no firmware; cache offline no app; falha no disparo não derruba a análise |
| Auditoria | `audit_ia.jsonl` (risco, chat, triagem, disparos), `dispatch_log.jsonl`, `ocorrencias.jsonl` |
| Anti-alucinação | Risco e prioridade determinísticos; RAG com limiar de relevância; respostas e mensagens montadas com trechos da base; LLM opcional com temperatura 0 |
| Privacidade (LGPD) | Consentimento, exclusão de dados, telefone/e-mail mascarados, PII removida do chat/logs, sessão pseudonimizada, app sem GPS, contatos fora do Git |

> Protocolos, áreas, rotas e histórico em `src/backend/data` são **ilustrativos** — substitua pelos dados oficiais do município.

## Vídeo: <a href="https://youtu.be/82j4XrzOwnA"Youtube</a>

## 📋 Licença
Projeto acadêmico — FIAP Global Solution.
