// Cliente HTTP com timeout. Em caso de falha retorna null (a UI mostra estado "offline" sem quebrar).
const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 6000);
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...options,
      signal: ctrl.signal,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    console.warn("API indisponível:", path, e.message);
    return null;
  } finally {
    clearTimeout(t);
  }
}

export const api = {
  health: () => request("/api/health"),
  telemetry: () => request("/api/telemetry/latest"),
  history: () => request("/api/telemetry/history?n=40"),
  weather: () => request("/api/weather"),
  risk: () => request("/api/risk"),
  areas: () => request("/api/areas"),
  alerts: () => request("/api/alerts"),
  audit: () => request("/api/audit?n=10"),
  setScenario: (scenario) => request("/api/simulation/scenario", { method: "POST", body: JSON.stringify({ scenario }) }),
};
