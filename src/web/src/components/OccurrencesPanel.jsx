// [NOVO] Fila de ocorrências registradas pelo agente de triagem (ordenada por prioridade).
import { api } from "../api";

const PRIO = { P1: "red", P2: "yellow", P3: "green" };
const NEXT = { aberta: "em_atendimento", em_atendimento: "encerrada" };

export default function OccurrencesPanel({ occurrences, onChanged }) {
  return (
    <section className="card">
      <h3>🆘 Ocorrências ({(occurrences || []).filter((o) => o.status !== "encerrada").length} abertas)</h3>
      {(!occurrences || occurrences.length === 0) && <p className="muted">Nenhuma ocorrência. Use o chat ao lado para simular um relato.</p>}
      <ul className="occ-list">
        {(occurrences || []).map((o) => (
          <li key={o.id} className={`occ ${o.status}`}>
            <div className="row-between">
              <span><span className={`prio ${PRIO[o.priority]}`}>{o.priority}</span> <b>{o.id}</b></span>
              <small>{new Date(o.created_at).toLocaleTimeString("pt-BR")}</small>
            </div>
            <div>{o.types.map((t) => t.replace(/_/g, " ")).join(", ")}</div>
            <small>📍 {[o.area_name, o.location_text].filter(Boolean).join(" · ") || "local não informado"}
              {o.people_at_risk ? ` · 👥 ${o.people_at_risk}` : ""}{o.vulnerable.length ? ` · ⚠️ ${o.vulnerable.join(", ")}` : ""}</small>
            <p className="desc">“{o.description}”</p>
            <div className="row-between">
              <small>Orientação: {o.guidance_refs.join(", ")}</small>
              {NEXT[o.status]
                ? <button type="button" className="link-btn" onClick={async () => { await api.setOccurrenceStatus(o.id, NEXT[o.status]); onChanged(); }}>
                    {o.status === "aberta" ? "▶ atender" : "✔ encerrar"}</button>
                : <small>encerrada</small>}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
