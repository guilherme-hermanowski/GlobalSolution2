function describe(r) {
  const o = r.output || {};
  switch (r.kind) {
    case "chat": return `intenção=${o.intent} modo=${o.mode} grounded=${String(o.grounded)} docs=[${(r.inputs.retrieved || []).join(",")}]`;
    case "triage": return o.status === "registrada" ? `ocorrência ${o.occurrence_id} ${o.priority} refs=[${(o.refs || []).join(",")}]` : `coletando faltam=[${(o.missing || []).join(",")}]`;
    case "dispatch": return `disparo ${o.dispatch_id} → ${o.total} destinatário(s)`;
    case "risk_assessment": return `nível=${o.level} score=${o.score} refs=[${(o.protocol_refs || []).join(",")}]`;
    default: return JSON.stringify(o);
  }
}

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
              {new Date(r.ts).toLocaleTimeString("pt-BR")} · <b>{r.kind}</b> · {describe(r)}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
