import { useState } from "react";

const SCENARIOS = [
  { id: "normal", label: "☀️ Normal", cls: "green" },
  { id: "chuva_moderada", label: "🌧️ Chuva Moderada", cls: "yellow" },
  { id: "transbordamento_critico", label: "🌊 Transbordamento Crítico", cls: "red" },
];

export default function SimulationPanel({ current, onChanged, setScenario }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function trigger(id) {
    setBusy(true);
    const res = await setScenario(id);
    setMsg(res ? `Cenário "${id}" ativado → risco ${res.alert.level}` : "Falha ao contatar o backend");
    setBusy(false);
    onChanged();
  }

  return (
    <section className="card">
      <h3>🎛️ Controle de Simulação (demo)</h3>
      <p className="muted">Dispara leituras virtuais do ESP32. Dados gerados aqui são rotulados como <b>SIMULADO</b>.</p>
      <div className="sim-buttons">
        {SCENARIOS.map((s) => (
          <button type="button" key={s.id} disabled={busy} className={`btn ${s.cls} ${current === s.id ? "active" : ""}`} onClick={() => trigger(s.id)}>
            {s.label}
          </button>
        ))}
      </div>
      {msg && <p className="sim-msg">{msg}</p>}
    </section>
  );
}
