// Cliente HTTP com timeout. Em caso de falha retorna null (a UI mostra estado "offline" sem quebrar).
// requestDetailed devolve também a mensagem de validação do backend (usado em formulários).
const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function requestDetailed(path, options = {}, timeoutMs = 8000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...options,
      signal: ctrl.signal,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    const body = await res.json().catch(() => null);
    if (!res.ok) {
      const msg = Array.isArray(body?.detail) ? body.detail.map((d) => d.msg).join("; ") : body?.detail || `HTTP ${res.status}`;
      return { ok: false, error: msg };
    }
    return { ok: true, data: body };
  } catch (e) {
    return { ok: false, error: "Backend indisponível" };
  } finally {
    clearTimeout(t);
  }
}

async function request(path, options) {
  const r = await requestDetailed(path, options);
  if (!r.ok) console.warn("API:", path, r.error);
  return r.ok ? r.data : null;
}

const post = (path, body) => ({ method: "POST", body: JSON.stringify(body ?? {}) });

export const api = {
  health: () => request("/api/health"),
  telemetry: () => request("/api/telemetry/latest"),
  history: () => request("/api/telemetry/history?n=40"),
  weather: () => request("/api/weather"),
  weatherStatus: () => request("/api/weather/status"),
  risk: () => request("/api/risk"),
  areas: () => request("/api/areas"),
  alerts: () => request("/api/alerts"),
  audit: () => request("/api/audit?n=12"),
  setScenario: (scenario) => request("/api/simulation/scenario", post("", { scenario })),
  // [NOVO] contatos e disparos
  contacts: () => request("/api/contacts"),
  addContact: (c) => requestDetailed("/api/contacts", post("", c)),
  deleteContact: (id) => request(`/api/contacts/${id}`, { method: "DELETE" }),
  dispatch: (body) => requestDetailed("/api/alerts/dispatch", post("", body)),
  dispatchQuickTest: () => requestDetailed("/api/alerts/dispatch/test", post("")),
  dispatches: () => request("/api/alerts/dispatches"),
  // [NOVO] chat + triagem
  chat: (message, session_id, area_id) => requestDetailed("/api/chat", post("", { message, session_id, area_id })),
  // [NOVO] conselho sob demanda (Gemini) — botão "O que fazer?" e alerta vermelho automático
  // Timeout maior: chamada ao Gemini pode demorar bem mais que os outros endpoints (~10-60s observado)
  advice: (trigger, location, session_id) => requestDetailed("/api/advice", post("", { trigger, location, session_id }), 60000),
  occurrences: () => request("/api/occurrences"),
  setOccurrenceStatus: (id, status) => request(`/api/occurrences/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }),
};
