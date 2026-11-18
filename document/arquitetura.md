# Arquitetura — AquaGuard / AlertaCidadão (v2)

```mermaid
flowchart LR
  subgraph Borda[IoT & Borda]
    ESP[ESP32 (Wokwi) + HC-SR04 + chuva] -- MQTT/TLS --> BROKER[(HiveMQ Cloud)]
  end
  subgraph Backend[FastAPI]
    BROKER --> LISTENER[mqtt_listener.py]
    API[/api/telemetry/ HTTP, opcional]
    LISTENER --> VAL[Pydantic + token]
    API --> VAL
    VAL --> STORE[(TelemetryStore\nfallback inteligente)]
    OWM[OpenWeatherMap\nclima + 5 dias] -. sem chave / erro .-> CACHE[Cache real] -. sem cache .-> MOCK[Clima mock]
    STORE --> RISK[Motor de risco\ndeterminístico]
    OWM --> RISK
    MOCK --> RISK
    RISK --> AGENT[Agente IA]
    KB[(protocolos_defesa_civil.json\n+ areas_risco.json)] --> RAG[BM25 Retriever] --> AGENT
    AGENT -- relato --> TRI[Agente de Triagem\nextração de slots] --> OCC[(Ocorrências P1-P3)]
    AGENT -- VERMELHO --> NOTIF[Disparo de alertas\nwa.me / mailto]
    CONT[(Contatos c/ consentimento)] --> NOTIF
    AGENT --> AUDIT[(audit_ia.jsonl\ndispatch_log.jsonl)]
  end
  AGENT --> WEB[Painel Defesa Civil - React]
  AGENT --> APP[App Cidadão - Expo]
```

## Decisões de arquitetura
| Decisão | Motivo |
|---|---|
| Risco calculado por regras explicáveis, não pelo LLM | Decisão crítica de segurança não pode alucinar; auditável |
| RAG com BM25 local sobre os 2 JSON oficiais | Roda offline na banca; respostas sempre citam a fonte (PROT/ROTA/AREA/ABRIGO) |
| Triagem por extração determinística + perguntas de esclarecimento | Previsível, testável e auditável; LLM pode ser plugado em `extract()` |
| Disparo via links wa.me / mailto | Zero atrito (sem conta Meta/Twilio/SMTP); troca por API oficial em produção |
| Fallback de clima em 3 camadas (real → cache → mock) | Apresentação nunca quebra por falta de chave ou rede |
| Telefones mascarados em UI e logs; dados pessoais fora do Git | LGPD: minimização, consentimento e direito de exclusão |

## Score de risco
score = 45% × nível do rio/cota de transbordamento + 20% × chuva no sensor + 25% × previsão 48h (saturação 100 mm) + 10% × histórico da área.
VERMELHO: rio ≥ 350 cm ou score ≥ 75 · AMARELO: rio ≥ 250 cm, score ≥ 40 ou previsão do dia ≥ 30 mm · senão VERDE.

## Prioridade da triagem
| Prioridade | Situações |
|---|---|
| P1 | pessoa ilhada/arrastada, ferido, desabamento/deslizamento, ou água no imóvel com vulneráveis (crianças, idosos, gestantes, PcD) |
| P2 | água entrando no imóvel, risco elétrico |
| P3 | rua alagada, animal em risco, relato não classificado |
