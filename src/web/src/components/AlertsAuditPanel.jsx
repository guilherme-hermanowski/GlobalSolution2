export default function AlertsAuditPanel({ alerts, audit }) {
  return (
    <section className="card wide two-col">
      <div>
        <h3>🚨 Histórico de alertas</h3>
        {(!alerts || alerts.length === 0) && <p className="muted">Nenhum alerta emitido.</p>}
        <ul className="list">
          {(alerts || []).slice(0, 8).map((a) => (
            <li key={a.id} className={`lvl-${a.level}`}>
              <b>{a.level}</b> · {new Date(a.created_at).toLocaleTimeString("pt-BR")} — {a.title}
              <small> ({a.data_source})</small>
            </li>
          ))}
        </ul>
      </div>
      <div>
        <h3>🧾 Auditoria da IA</h3>
        <ul className="list mono">
          {(audit || []).map((r) => (
            <li key={r.decision_id}>
              {new Date(r.ts).toLocaleTimeString("pt-BR")} · <b>{r.kind}</b> ·{" "}
              {r.kind === "chat"
                ? `modo=${r.output.mode} grounded=${String(r.output.grounded)} docs=[${(r.inputs.retrieved || []).join(",")}]`
                : `nível=${r.output.level} score=${r.output.score} refs=[${r.output.protocol_refs.join(",")}]`}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
