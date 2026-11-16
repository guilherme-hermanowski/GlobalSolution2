// Mapa esquemático (SVG) das áreas de risco e abrigos — coordenadas normalizadas 0..1,
// evitando expor localização real de moradores. Pode ser trocado por Leaflet/OSM.
const LVL_COLOR = { VERDE: "#16a34a", AMARELO: "#f59e0b", VERMELHO: "#dc2626" };

export default function RiskMap({ areas, risk }) {
  if (!areas) return <section className="card wide">Carregando áreas…</section>;
  const affected = new Set(risk?.affected_areas || []);
  const color = (a) => (affected.has(a.nome) ? LVL_COLOR[risk.level] : LVL_COLOR.VERDE);
  return (
    <section className="card wide">
      <h3>🗺️ Áreas de risco e abrigos</h3>
      <div className="map-wrap">
        <svg viewBox="0 0 100 100" className="map">
          <path d="M0,70 C20,60 35,85 55,78 S85,55 100,60" className="river" />
          {areas.areas.map((a) => (
            <g key={a.id}>
              <circle cx={a.x * 100} cy={a.y * 100} r={6 + a.vulnerabilidade * 6} fill={color(a)} opacity="0.35" />
              <circle cx={a.x * 100} cy={a.y * 100} r="2" fill={color(a)} />
              <text x={a.x * 100 + 3} y={a.y * 100 - 3}>{a.id}</text>
            </g>
          ))}
          {areas.abrigos.map((s) => (
            <text key={s.nome} x={s.x * 100} y={s.y * 100} className="shelter">🏠</text>
          ))}
        </svg>
        <table>
          <thead><tr><th>Área</th><th>População</th><th>Vulnerab.</th><th>Status</th><th>Abrigo</th></tr></thead>
          <tbody>
            {areas.areas.map((a) => (
              <tr key={a.id}>
                <td>{a.id} · {a.nome}</td>
                <td>{a.populacao_estimada.toLocaleString("pt-BR")}</td>
                <td>{Math.round(a.vulnerabilidade * 100)}%</td>
                <td><span className="dot" style={{ background: color(a) }} /> {affected.has(a.nome) ? risk.level : "VERDE"}</td>
                <td>{a.abrigo}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
