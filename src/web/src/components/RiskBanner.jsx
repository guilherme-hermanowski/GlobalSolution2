const COLORS = { VERDE: "green", AMARELO: "yellow", VERMELHO: "red" };

export default function RiskBanner({ risk }) {
  if (!risk) return <section className="banner muted">Calculando risco…</section>;
  return (
    <section className={`banner ${COLORS[risk.level]}`}>
      <div className="banner-level">
        <strong>{risk.level}</strong>
        <span>Índice {risk.score.toFixed(0)}/100</span>
      </div>
      <div className="banner-body">
        <h2>{risk.title}</h2>
        <ul>{risk.factors.map((f) => <li key={f}>{f}</li>)}</ul>
        <p className="refs">Protocolos: {risk.protocol_refs.join(", ")} · Fonte dos dados: <b>{risk.data_source}</b></p>
      </div>
    </section>
  );
}
