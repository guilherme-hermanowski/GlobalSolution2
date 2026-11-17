// [NOVO] Chat de teste no painel: simula a conversa de um cidadão (dúvidas + triagem de ocorrências).
import { useRef, useState } from "react";
import { api } from "../api";

const SUGGESTIONS = [
  "Socorro, a água entrou na minha casa e tenho dois idosos aqui",
  "Estamos ilhados no telhado no Jardim Ribeirinho, 4 pessoas",
  "Tem um fio caído na Rua Nova, Parque das Águas",
  "Qual a rota de fuga da Vila Baixada?",
  "Vai ter risco de enchente nos próximos dias?",
];

export default function CitizenChatPanel({ areas, onNewOccurrence }) {
  const [msgs, setMsgs] = useState([{ from: "bot", text: "Simulador do App do Cidadão. Faça uma pergunta ou relate uma emergência." }]);
  const [input, setInput] = useState("");
  const [session, setSession] = useState(null);
  const [area, setArea] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  async function send(text) {
    const q = (text ?? input).trim();
    if (q.length < 2 || busy) return;
    setInput("");
    setMsgs((m) => [...m, { from: "user", text: q }]);
    setBusy(true);
    const r = await api.chat(q, session, area || null);
    setBusy(false);
    if (!r.ok) { setMsgs((m) => [...m, { from: "bot", text: `Erro: ${r.error}. Em emergência ligue 193.` }]); return; }
    setSession(r.data.session_id);
    setMsgs((m) => [...m, { from: "bot", ...r.data, text: r.data.answer }]);
    if (r.data.triage?.status === "registrada") onNewOccurrence();
    setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }

  return (
    <section className="card wide2">
      <h3>💬 Chat do cidadão (agente RAG + triagem)
        <button type="button" className="link-btn" onClick={() => { setSession(null); setMsgs(msgs.slice(0, 1)); }}>nova conversa</button>
      </h3>
      <label className="muted">Área do perfil (opcional):{" "}
        <select value={area} onChange={(e) => setArea(e.target.value)}>
          <option value="">não informada</option>
          {(areas?.areas || []).map((a) => <option key={a.id} value={a.id}>{a.nome}</option>)}
        </select>
      </label>
      <div className="chat" aria-live="polite">
        {msgs.map((m, i) => (
          <div key={i} className={`bubble ${m.from}`}>
            <div className="pre">{m.text}</div>
            {m.intent && <small className="meta">intenção: {m.intent} · modo: {m.mode}{m.sources?.length ? ` · fontes: ${m.sources.join(", ")}` : ""}</small>}
            {m.triage && (
              <div className={`triage ${m.triage.status}`}>
                {m.triage.status === "registrada" ? `✅ ${m.triage.occurrence_id} · ${m.triage.priority}` : `📝 Coletando — falta: ${m.triage.missing.join(", ")}`}
                <small> · extraído: {Object.entries(m.triage.extracted).map(([k, v]) => `${k}=${Array.isArray(v) ? v.join("/") : v}`).join("; ") || "—"}</small>
              </div>
            )}
          </div>
        ))}
        {busy && <div className="bubble bot">…</div>}
        <div ref={endRef} />
      </div>
      <div className="chips">
        {SUGGESTIONS.map((s) => <button type="button" key={s} className="chip" onClick={() => send(s)}>{s}</button>)}
      </div>
      <form className="chat-input" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <input value={input} onChange={(e) => setInput(e.target.value)} maxLength={500} placeholder="Digite como se fosse o cidadão…" aria-label="Mensagem" />
        <button type="submit" className="btn blue" disabled={busy}>Enviar</button>
      </form>
    </section>
  );
}
