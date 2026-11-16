# FIAP - Faculdade de Informática e Administração Paulista

## Global Solution — CitizenTech

# 💧 AquaGuard / AlertaCidadão

## 👨‍🎓 Integrantes
- Nome do integrante 1 — RM
- Nome do integrante 2 — RM

## 👩‍🏫 Professores
- Tutor(a): Nome · Coordenador(a): Nome

## 📜 Descrição
Sistema de **prevenção de enchentes em áreas urbanas vulneráveis** (ODS 11 — Cidades Sustentáveis; ODS 13 — Ação Climática).
Um ESP32 mede o nível do rio e a chuva; o backend cruza a telemetria com a previsão do tempo e o histórico de alagamentos;
um **Agente de IA com RAG** gera alertas fundamentados nos protocolos da Defesa Civil e conversa com o cidadão.

> **Modo Simulação / Fallback Inteligente:** a POC funciona 100% **sem hardware**, sem chave de clima e sem chave de LLM.
> Todo dado exibido é rotulado como `real`, `simulated` ou `simulated_fallback`.

## 📁 Estrutura de pastas
```
aquaguard-alertacidadao/
├── assets/                     # imagens, logos, prints da solução
├── config/                     # exemplos de configuração (.env)
├── document/                   # arquitetura e documentação acadêmica
├── scripts/                    # start_demo.sh / start_demo.bat
├── src/
│   ├── iot/
│   │   ├── firmware/aquaguard_esp32/aquaguard_esp32.ino   # C++ ESP32 (referência)
│   │   └── simulator/iot_simulator.py                    # ESP32 virtual
│   ├── backend/                # FastAPI + Agente IA + RAG
│   │   ├── app/
│   │   │   ├── main.py         # rotas e tratamento de erros
│   │   │   ├── config.py       # variáveis de ambiente (todas opcionais)
│   │   │   ├── schemas.py      # contratos Pydantic (validação)
│   │   │   └── services/
│   │   │       ├── telemetry.py    # store + fallback inteligente
│   │   │       ├── weather.py      # OpenWeatherMap + mock
│   │   │       ├── risk_engine.py  # score explicável
│   │   │       ├── rag.py          # retriever BM25
│   │   │       ├── agent.py        # análise proativa + chat
│   │   │       ├── audit.py        # log de auditoria (JSONL)
│   │   │       └── privacy.py      # pseudonimização / anonimização
│   │   ├── data/               # protocolos (RAG), áreas, histórico
│   │   ├── logs/               # app.log + audit_ia.jsonl
│   │   └── tests/test_api.py
│   ├── web/                    # Painel Defesa Civil (React + Vite)
│   └── mobile/                 # App do Cidadão (React Native / Expo)
└── README.md
```

## 🔧 Como executar (demonstração local)
Pré-requisitos: Python 3.10+, Node 18+.

**1) Backend**
```bash
cd src/backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # opcional: preencher OPENWEATHER_API_KEY / OPENAI_API_KEY
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pytest -q                       # 7 testes de validação, fallback, RAG e privacidade
```
Swagger: http://localhost:8000/docs

**2) Painel Web**
```bash
cd src/web && npm install && npm run dev      # http://localhost:5173
```

**3) Simulador IoT (opcional — o painel já tem botões de cenário)**
```bash
python src/iot/simulator/iot_simulator.py --scenario progressivo
# ao vivo: 1=normal 2=chuva moderada 3=transbordamento  q=sair
```

**4) App do Cidadão**
```bash
cd src/mobile && npm install && npx expo install --fix && npx expo start
```
Ajuste `src/mobile/src/config.js` com o IP da máquina do backend (celular e PC na mesma rede).

**5) ESP32 físico (se disponível)**: abra o `.ino` no Arduino IDE, instale *ArduinoJson*, configure Wi-Fi, `API_URL` e `DEVICE_TOKEN`.

## 🎬 Roteiro de apresentação (3 min)
1. Painel em **Normal** → semáforo verde, sensor rotulado SIMULADO/FALLBACK.
2. Clique **Chuva Moderada** → AMARELO, previsão sobe, áreas vulneráveis destacadas.
3. Clique **Transbordamento Crítico** → VERMELHO, instruções de evacuação e abrigos.
4. No app, pergunte *"Qual a rota de fuga da minha área?"* → resposta com fonte `[ROTA-A1]`.
5. Pergunte algo fora do escopo → recusa segura (199). Mostre a **Auditoria da IA** no painel.

## 🛡️ Governança
| Pilar | Implementação |
|---|---|
| Qualidade de dados | Pydantic com faixas físicas, coerência entre sensores, timestamp no futuro bloqueado, HTTP 422 padronizado |
| Resiliência | Timeout + cache no clima; fallback sintético se ESP32 offline; buffer store-and-forward no firmware; cache offline no app |
| Auditoria da IA | `logs/audit_ia.jsonl`: entradas, hash SHA-256, regras, documentos RAG, modo da resposta |
| Anti-alucinação | Risco determinístico; limiar de relevância; modo extrativo; prompt restritivo (temperatura 0) |
| Privacidade (LGPD) | HMAC do device_id; geolocalização em grade ~1 km; remoção de CPF/telefone/e-mail/CEP; app sem GPS |
| Segurança | Token por dispositivo (`X-Device-Token`); CORS aberto apenas para POC |

> Protocolos, áreas e históricos em `src/backend/data` são **ilustrativos** — substituir por dados oficiais do município.

## 📋 Licença
Projeto acadêmico — FIAP Global Solution.
