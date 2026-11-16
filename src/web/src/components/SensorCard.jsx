const SOURCE_LABEL = {
  real: { text: "REAL (ESP32)", cls: "ok" },
  simulated: { text: "SIMULADO", cls: "warn" },
  simulated_fallback: { text: "FALLBACK (ESP32 offline)", cls: "bad" },
};

// Mini-gráfico SVG do nível do rio (sem dependências externas)
function Sparkline({ points }) {
  if (!points || points.length < 2) return null;
  const w = 280, h = 60, max = 420;
  const d = points.map((v, i) => `${(i / (points.length - 1)) * w},${h - (v / max) * h}`).join(" ");
  const y = (cm) => h - (cm / max) * h;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="spark" aria-label="Histórico do nível do rio">
      <line x1="0" x2={w} y1={y(250)} y2={y(250)} className="th-alert" />
      <line x1="0" x2={w} y1={y(350)} y2={y(350)} className="th-overflow" />
      <polyline points={d} fill="none" strokeWidth="2" className="spark-line" />
    </svg>
  );
}

export default function SensorCard({ telemetry, history }) {
  if (!telemetry) return <section className="card">Carregando sensores…</section>;
  const src = SOURCE_LABEL[telemetry.source] || SOURCE_LABEL.simulated;
  const pct = Math.min(100, telemetry.river_level_pct);
  return (
    <section className="card">
      <h3>📡 Sensores IoT <span className={`pill ${src.cls}`}>{src.text}</span></h3>
      <div className="gauge">
        <div className="gauge-fill" style={{ height: `${pct}%`, background: pct >= 100 ? "#dc2626" : pct >= 71 ? "#f59e0b" : "#0ea5e9" }} />
        <span>{telemetry.river_level_cm.toFixed(0)} cm<br /><small>{pct.toFixed(0)}% da cota</small></span>
      </div>
      <dl>
        <dt>Chuva (sensor)</dt><dd>{telemetry.rain_detected ? "🌧️ detectada" : "☀️ sem chuva"} · {telemetry.rain_intensity}%</dd>
        <dt>Dispositivo</dt><dd>{telemetry.device_ref} <small>(pseudonimizado)</small></dd>
        <dt>Zona</dt><dd>{telemetry.zone} <small>(~1 km)</small></dd>
        <dt>Status</dt><dd>{telemetry.online ? `online · ${telemetry.stale_seconds}s atrás` : "offline — usando fallback"}</dd>
      </dl>
      <Sparkline points={(history || []).map((h) => h.river_level_cm)} />
      <small className="legend">— cota de alerta 250 cm · — transbordamento 350 cm</small>
    </section>
  );
}
