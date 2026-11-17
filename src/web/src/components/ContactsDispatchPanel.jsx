// [NOVO] Cadastro de contatos (WhatsApp/e-mail) + disparo simulado de alertas com links wa.me/mailto.
import { useState } from "react";
import { api } from "../api";

const EMPTY = { name: "", phone: "", email: "", area_id: "A1", whatsapp: true, emailCh: false, consent: false };
const TRIGGER = { manual: "Manual", teste_rapido: "Teste rápido", automatico: "Automático (VERMELHO)" };

// Máscara visual (XX) 9XXXX-XXXX enquanto digita
function maskInput(v) {
  const d = v.replace(/\D/g, "").slice(0, 11);
  if (d.length <= 2) return d;
  if (d.length <= 7) return `(${d.slice(0, 2)}) ${d.slice(2)}`;
  return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
}

export default function ContactsDispatchPanel({ contacts, dispatches, areas, onChanged }) {
  const [form, setForm] = useState(EMPTY);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [level, setLevel] = useState("VERMELHO");
  const [target, setTarget] = useState("");
  const [last, setLast] = useState(null);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  async function submit(e) {
    e.preventDefault();
    const channels = [form.whatsapp && "whatsapp", form.emailCh && "email"].filter(Boolean);
    const r = await api.addContact({ name: form.name, phone: form.phone || null, email: form.email || null,
                                     area_id: form.area_id, channels, consent: form.consent });
    setMsg(r.ok ? { ok: true, text: `Contato salvo: ${r.data.phone_masked || r.data.email_masked}` } : { ok: false, text: r.error });
    if (r.ok) { setForm(EMPTY); onChanged(); }
  }

  async function run(fn) {
    setBusy(true);
    const r = await fn();
    setBusy(false);
    if (r.ok) { setLast(r.data); onChanged(); } else setMsg({ ok: false, text: r.error });
  }

  return (
    <>
      <section className="card">
        <h3>📇 Cadastro de cidadão</h3>
        <form onSubmit={submit} className="form">
          <label>Nome<input required value={form.name} onChange={set("name")} maxLength={60} /></label>
          <label>Celular / WhatsApp<input value={form.phone} placeholder="(11) 98765-4321" inputMode="tel"
            onChange={(e) => setForm({ ...form, phone: maskInput(e.target.value) })} /></label>
          <label>E-mail (opcional)<input type="email" value={form.email} onChange={set("email")} /></label>
          <label>Área
            <select value={form.area_id} onChange={set("area_id")}>
              {(areas?.areas || []).map((a) => <option key={a.id} value={a.id}>{a.id} · {a.nome}</option>)}
            </select>
          </label>
          <div className="checks">
            <label><input type="checkbox" checked={form.whatsapp} onChange={set("whatsapp")} /> WhatsApp</label>
            <label><input type="checkbox" checked={form.emailCh} onChange={set("emailCh")} /> E-mail</label>
          </div>
          <label className="consent"><input type="checkbox" checked={form.consent} onChange={set("consent")} />
            Autorizo o uso do meu contato exclusivamente para alertas da Defesa Civil (LGPD). Posso solicitar a exclusão a qualquer momento.</label>
          <button type="submit" className="btn blue">Salvar contato</button>
          {msg && <p className={msg.ok ? "ok-msg" : "err-msg"} role="status">{msg.text}</p>}
        </form>
      </section>

      <section className="card">
        <h3>👥 Contatos cadastrados ({contacts?.length || 0})</h3>
        {(!contacts || contacts.length === 0) && <p className="muted">Nenhum contato. Cadastre um número para testar o disparo.</p>}
        <ul className="list">
          {(contacts || []).map((c) => (
            <li key={c.id} className="row-between">
              <span><b>{c.name}</b> · {c.area_id}<br /><small>{[c.phone_masked, c.email_masked].filter(Boolean).join(" · ")} · {c.channels.join("+")}</small></span>
              <button type="button" className="link-btn" onClick={async () => { await api.deleteContact(c.id); onChanged(); }}>remover</button>
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h3>📣 Disparo de alerta</h3>
        <button type="button" className="btn red big-btn" disabled={busy} onClick={() => run(api.dispatchQuickTest)}>
          ⚡ TESTE RÁPIDO — simular enchente e disparar
        </button>
        <p className="muted">Coloca o sensor em “Transbordamento Crítico” e gera alerta VERMELHO para as áreas afetadas.</p>
        <hr />
        <div className="form">
          <label>Nível
            <select value={level} onChange={(e) => setLevel(e.target.value)}>
              <option>VERMELHO</option><option>AMARELO</option><option>VERDE</option>
            </select>
          </label>
          <label>Área
            <select value={target} onChange={(e) => setTarget(e.target.value)}>
              <option value="">Áreas afetadas pelo nível</option>
              {(areas?.areas || []).map((a) => <option key={a.id} value={a.id}>{a.id} · {a.nome}</option>)}
            </select>
          </label>
          <button type="button" className="btn blue" disabled={busy}
            onClick={() => run(() => api.dispatch({ level, area_ids: target ? [target] : null, test: true }))}>Disparar alerta manual</button>
        </div>
      </section>

      {last && (
        <section className="card wide">
          <h3>✉️ Último disparo {last.id} — {last.total} mensagem(ns)</h3>
          <div className="two-col">
            <pre className="preview">{last.text}</pre>
            <div>
              <a className="btn green link" href={last.share_link} target="_blank" rel="noreferrer">📲 Compartilhar no WhatsApp (grupos)</a>
              <ul className="list">
                {last.messages.map((m, i) => (
                  <li key={i} className="row-between">
                    <span>{m.channel === "whatsapp" ? "🟢" : "📧"} {m.contact_name} · {m.recipient_masked}</span>
                    <a href={m.link} target="_blank" rel="noreferrer">enviar →</a>
                  </li>
                ))}
                {last.messages.length === 0 && <li className="muted">Nenhum contato nas áreas — use o link de compartilhamento.</li>}
              </ul>
            </div>
          </div>
        </section>
      )}

      <section className="card wide">
        <h3>🧾 Auditoria de disparos</h3>
        <table>
          <thead><tr><th>Horário</th><th>ID</th><th>Origem</th><th>Nível</th><th>Áreas</th><th>Destinatários</th><th>Protocolos</th></tr></thead>
          <tbody>
            {(dispatches || []).slice(0, 15).map((d) => (
              <tr key={d.id} className="clickable" onClick={() => setLast(d)}>
                <td>{new Date(d.created_at).toLocaleTimeString("pt-BR")}</td><td>{d.id}</td><td>{TRIGGER[d.trigger]}</td>
                <td className={`lvl-${d.level}`}><b>{d.level}</b></td><td>{d.area_ids.join(", ")}</td><td>{d.total}</td>
                <td>{d.protocol_refs.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {(!dispatches || dispatches.length === 0) && <p className="muted">Nenhum disparo ainda.</p>}
      </section>
    </>
  );
}
