// [NOVO] Conselho sob demanda via Gemini: botão "O que fazer?" (lê a última leitura do MQTT) +
// gatilho automático quando o risco vira VERMELHO. Aparece como um chat, igual ao do cidadão.
import { useEffect, useRef, useState } from "react";
import { api } from "../api";

export default function AdvicePanel({ riskLevel }) {
  const [msgs, setMsgs] = useState([]);
  const [session, setSession] = useState(null);
  const [busy, setBusy] = useState(false);
  const wasRedRef = useRef(false);
  const endRef = useRef(null);

  async function ask(trigger) {
    if (busy) return;
    setBusy(true);
    setMsgs((m) => [...m, { from: "user", text: trigger === "auto_red" ? "⚠️ Alerta VERMELHO — o que fazer?" : "O que fazer?" }]);
    const r = await api.advice(trigger, null, session);
    setBusy(false);
    if (!r.ok) { setMsgs((m) => [...m, { from: "bot", text: `Erro: ${r.error}. Em emergência ligue 193.` }]); return; }
    setSession(r.data.session_id);
    setMsgs((m) => [...m, { from: "bot", ...r.data, text: r.data.answer }]);
    setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }

  useEffect(() => {
    const isRed = riskLevel === "VERMELHO";
    if (isRed && !wasRedRef.current) ask("auto_red");   // dispara 1x por transição pra VERMELHO
    wasRedRef.current = isRed;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [riskLevel]);

  return (
    <section className="card wide2">
      <h3>🧭 O que fazer agora?
        <button type="button" className="btn blue" onClick={() => ask("manual")} disabled={busy}>O que fazer?</button>
      </h3>
      <p className="muted">Pergunte com base na última leitura do sensor (MQTT). Em alerta vermelho, a orientação de evacuação aparece aqui automaticamente.</p>
      <div className="chat" aria-live="polite">
        {msgs.length === 0 && (
          <div className="bubble bot"><div className="pre">Clique em "O que fazer?" pra receber uma orientação com base na leitura atual do rio e da chuva.</div></div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`bubble ${m.from}`}>
            <div className="pre">{m.text}</div>
            {m.mode && <small className="meta">modo: {m.mode}</small>}
          </div>
        ))}
        {busy && <div className="bubble bot">…</div>}
        <div ref={endRef} />
      </div>
    </section>
  );
}
