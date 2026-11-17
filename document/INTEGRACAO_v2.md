# Guia de integração — AquaGuard v2

A estrutura da v1 foi preservada (FastAPI, React, Expo, simulador IoT e JSON locais).
Legenda: **[NOVO]** arquivo criado · **[ATUALIZADO]** arquivo alterado de forma compatível.

## Pilar 1 — Clima real + fallback
| Arquivo | Mudança |
|---|---|
| `backend/app/services/weather.py` [ATUALIZADO] | OpenWeatherMap `/weather` + `/forecast` (agregado por dia no fuso da cidade), cache com TTL, fallback real → cache → mock, `weather_status()` |
| `backend/app/config.py` [ATUALIZADO] | `WEATHER_TIMEOUT_S`, `WEATHER_CACHE_TTL_S` |
| `backend/app/main.py` [ATUALIZADO] | `GET /api/weather/status` (diagnóstico) |
| `web/src/components/WeatherCard.jsx` [ATUALIZADO] | Etiqueta da origem (real/cache/mock), motivo do fallback, ícone, vento, contador de chamadas |

**Ativar o clima real**
1. Crie uma conta gratuita em openweathermap.org → *API keys* (a chave pode levar até ~2 h para ativar; até lá a API devolve 401 e o sistema cai no fallback sozinho).
2. Em `src/backend/.env`: `OPENWEATHER_API_KEY=<sua_chave>` e, se quiser, `CITY_LAT`, `CITY_LON`, `CITY_NAME`.
3. Reinicie o backend e confira `GET /api/weather/status` → `"mode": "real"`.

> Com clima real ativo, os botões de cenário mudam só o sensor (o clima é o de verdade). Para a demo com chuva "garantida", deixe a chave em branco.

## Pilar 2 — Contatos e disparo de alertas
| Arquivo | Mudança |
|---|---|
| `backend/app/services/notifications.py` [NOVO] | Cadastro (deduplicação, persistência local fora do Git), mensagem montada a partir dos protocolos, links `wa.me` / `mailto`, link de compartilhamento para grupos, log de disparos com telefone mascarado |
| `backend/app/schemas.py` [ATUALIZADO] | `ContactIn` (normaliza celular BR → E.164, exige consentimento), `ContactOut`, `DispatchIn/Out` |
| `backend/app/services/agent.py` [ATUALIZADO] | Disparo **automático** quando o risco muda para VERMELHO (`AUTO_DISPATCH_ON_RED`) |
| `web/src/components/ContactsDispatchPanel.jsx` [NOVO] | Formulário, lista, botão **⚡ TESTE RÁPIDO**, disparo manual, prévia da mensagem, links e auditoria |
| `mobile/src/screens/ContactScreen.js` [NOVO] | Aba "Receber alertas" com consentimento e exclusão de dados |

**Endpoints**
| Método | Rota | Uso |
|---|---|---|
| POST | `/api/contacts` | cadastrar `{name, phone, email?, area_id, channels, consent}` |
| GET / DELETE | `/api/contacts`, `/api/contacts/{id}` | listar (mascarado) / excluir (LGPD) |
| POST | `/api/alerts/dispatch` | disparo manual `{level, area_ids?, test}` |
| POST | `/api/alerts/dispatch/test` | **teste rápido**: força o cenário crítico e dispara VERMELHO |
| GET | `/api/alerts/dispatches` | histórico de disparos (com links) |

## Pilar 3 — Agente de triagem com RAG
| Arquivo | Mudança |
|---|---|
| `backend/app/services/rag.py` [ATUALIZADO] | Indexa **protocolos_defesa_civil.json + areas_risco.json** (áreas, rotas, abrigos) |
| `backend/app/services/triage.py` [NOVO] | Intenção (dúvida × relato), extração de área/rua/tipo/nº de pessoas/vulneráveis, perguntas de esclarecimento, prioridade P1–P3, ocorrência + orientação extraída dos protocolos |
| `backend/app/services/agent.py` [ATUALIZADO] | Roteia relato → triagem; dúvida → RAG; resto → recusa segura |
| `backend/app/schemas.py` [ATUALIZADO] | `ChatIn.session_id`, `ChatOut.intent/triage/session_id`, `Occurrence` |
| `backend/data/areas_risco.json` [ATUALIZADO] | Campos `aliases` e `rotas` (rotas saíram dos protocolos para o arquivo de áreas) |
| `backend/data/protocolos_defesa_civil.json` [ATUALIZADO] | PROT-09 (pessoa ilhada) e PROT-10 (risco elétrico/estrutural) |
| `web/src/components/CitizenChatPanel.jsx` / `OccurrencesPanel.jsx` [NOVO] | Chat de teste e fila de ocorrências (atender/encerrar) |
| `mobile/src/screens/ChatScreen.js` [ATUALIZADO] | Mantém `session_id`, mostra protocolo da ocorrência e botão "Ligar 193" em P1 |

**Endpoints**: `POST /api/chat` (agora aceita `session_id`), `GET /api/occurrences`, `PATCH /api/occurrences/{id}` `{status}`.

**Para plugar um LLM na extração**: substitua `triage.extract()` por uma chamada com saída JSON
(`area_id`, `location_text`, `types[]`, `people_at_risk`, `vulnerable[]`) e mantenha o restante igual.
A prioridade e as orientações continuam determinísticas.

## Compatibilidade
- Todos os campos novos de `ChatOut` são opcionais: os clientes da v1 continuam funcionando.
- Os 7 testes da v1 continuam passando; agora são 14 no total (`pytest -q`).
