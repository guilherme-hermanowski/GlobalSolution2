import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import RiskBanner from "./components/RiskBanner.jsx";
import SensorCard from "./components/SensorCard.jsx";
import WeatherCard from "./components/WeatherCard.jsx";
import RiskMap from "./components/RiskMap.jsx";
import SimulationPanel from "./components/SimulationPanel.jsx";
import AlertsAuditPanel from "./components/AlertsAuditPanel.jsx";

const POLL_MS = 4000;

export default function App() {
  const [data, setData] = useState({});
  const [apiOnline, setApiOnline] = useState(true);
  const [updatedAt, setUpdatedAt] = useState(null);

  const refresh = useCallback(async () => {
    const [health, telemetry, history, weather, risk, areas, alerts, audit] = await Promise.all([
      api.health(), api.telemetry(), api.history(), api.weather(), api.risk(), api.areas(), api.alerts(), api.audit(),
    ]);
    setApiOnline(Boolean(health));
    // Mantém os últimos dados válidos caso alguma chamada falhe (degradação graciosa)
    setData((prev) => ({
      health: health ?? prev.health, telemetry: telemetry ?? prev.telemetry, history: history ?? prev.history,
      weather: weather ?? prev.weather, risk: risk ?? prev.risk, areas: areas ?? prev.areas,
      alerts: alerts ?? prev.alerts, audit: audit ?? prev.audit,
    }));
    setUpdatedAt(new Date());
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>💧 AquaGuard <span>| Painel da Defesa Civil</span></h1>
          <small>ODS 11 · ODS 13 — Monitoramento preventivo de enchentes</small>
        </div>
        <div className="header-status">
          <span className={`pill ${apiOnline ? "ok" : "bad"}`}>API {apiOnline ? "online" : "offline"}</span>
          {data.health && <span className="pill">Clima: {data.health.weather_mode}</span>}
          {data.health && <span className="pill">IA: {data.health.llm_mode}</span>}
          {updatedAt && <small>Atualizado {updatedAt.toLocaleTimeString("pt-BR")}</small>}
        </div>
      </header>

      {!apiOnline && <div className="offline">Backend indisponível — exibindo os últimos dados recebidos.</div>}

      <RiskBanner risk={data.risk} />
      <main className="grid">
        <SensorCard telemetry={data.telemetry} history={data.history} />
        <WeatherCard weather={data.weather} />
        <SimulationPanel current={data.health?.scenario} onChanged={refresh} setScenario={api.setScenario} />
        <RiskMap areas={data.areas} risk={data.risk} />
        <AlertsAuditPanel alerts={data.alerts} audit={data.audit} />
      </main>
    </div>
  );
}
