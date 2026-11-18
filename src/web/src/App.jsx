import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import RiskBanner from "./components/RiskBanner.jsx";
import SensorCard from "./components/SensorCard.jsx";
import WeatherCard from "./components/WeatherCard.jsx";
import RiskMap from "./components/RiskMap.jsx";
import SimulationPanel from "./components/SimulationPanel.jsx";
import AlertsAuditPanel from "./components/AlertsAuditPanel.jsx";
import ContactsDispatchPanel from "./components/ContactsDispatchPanel.jsx"; // [NOVO]
import OccurrencesPanel from "./components/OccurrencesPanel.jsx";           // [NOVO]
import CitizenChatPanel from "./components/CitizenChatPanel.jsx";           // [NOVO]
import AdvicePanel from "./components/AdvicePanel.jsx";                     // [NOVO]

const POLL_MS = 4000;
const TABS = [
  { id: "monitor", label: "📊 Monitoramento" },
  { id: "alerts", label: "📣 Contatos & Disparos" },
  { id: "triage", label: "🆘 Ocorrências & Chat" },
];

export default function App() {
  const [data, setData] = useState({});
  const [apiOnline, setApiOnline] = useState(true);
  const [updatedAt, setUpdatedAt] = useState(null);
  const [tab, setTab] = useState("monitor");

  const refresh = useCallback(async () => {
    const keys = ["health", "telemetry", "history", "weather", "weatherStatus", "risk", "areas", "alerts", "audit",
                  "contacts", "dispatches", "occurrences"];
    const values = await Promise.all(keys.map((k) => api[k]()));
    setApiOnline(Boolean(values[0]));
    // Mantém os últimos dados válidos caso alguma chamada falhe (degradação graciosa)
    setData((prev) => Object.fromEntries(keys.map((k, i) => [k, values[i] ?? prev[k]])));
    setUpdatedAt(new Date());
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  const openOcc = (data.occurrences || []).filter((o) => o.status !== "encerrada").length;

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>💧 AquaGuard <span>| Painel da Defesa Civil</span></h1>
          <small>ODS 11 · ODS 13 — Monitoramento preventivo de enchentes</small>
        </div>
        <div className="header-status">
          <span className={`pill ${apiOnline ? "ok" : "bad"}`}>API {apiOnline ? "online" : "offline"}</span>
          {data.health && <span className={`pill ${data.health.weather_mode === "real" ? "ok" : "warn"}`}>Clima: {data.health.weather_mode}</span>}
          {data.health && <span className="pill">IA: {data.health.llm_mode}</span>}
          {updatedAt && <small>Atualizado {updatedAt.toLocaleTimeString("pt-BR")}</small>}
        </div>
      </header>

      {!apiOnline && <div className="offline">Backend indisponível — exibindo os últimos dados recebidos.</div>}

      <RiskBanner risk={data.risk} />

      <nav className="tabs">
        {TABS.map((t) => (
          <button type="button" key={t.id} className={`tab ${tab === t.id ? "on" : ""}`} onClick={() => setTab(t.id)}>
            {t.label}{t.id === "triage" && openOcc > 0 && <span className="badge">{openOcc}</span>}
          </button>
        ))}
      </nav>

      {tab === "monitor" && (
        <main className="grid">
          <SensorCard telemetry={data.telemetry} history={data.history} />
          <WeatherCard weather={data.weather} status={data.weatherStatus} />
          <SimulationPanel current={data.health?.scenario} onChanged={refresh} setScenario={api.setScenario} />
          <RiskMap areas={data.areas} risk={data.risk} />
          <AlertsAuditPanel alerts={data.alerts} audit={data.audit} />
          <AdvicePanel riskLevel={data.risk?.level} />
        </main>
      )}
      {tab === "alerts" && (
        <main className="grid">
          <ContactsDispatchPanel contacts={data.contacts} dispatches={data.dispatches} areas={data.areas} onChanged={refresh} />
        </main>
      )}
      {tab === "triage" && (
        <main className="grid">
          <CitizenChatPanel areas={data.areas} onNewOccurrence={refresh} />
          <OccurrencesPanel occurrences={data.occurrences} onChanged={refresh} />
        </main>
      )}
    </div>
  );
}
