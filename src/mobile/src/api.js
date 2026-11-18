import AsyncStorage from "@react-native-async-storage/async-storage";
import { API_URL } from "./config";

// Cache offline: se o backend cair, o app mostra o último risco conhecido (resiliência).
async function request(path, options = {}, cacheKey, timeoutMs = 8000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_URL}${path}`, {
      ...options, signal: ctrl.signal, headers: { "Content-Type": "application/json" },
    });
    const body = await res.json().catch(() => null);
    if (!res.ok) {
      const msg = Array.isArray(body?.detail) ? body.detail.map((d) => d.msg).join("; ") : body?.detail || `HTTP ${res.status}`;
      return { data: null, offline: false, error: msg };
    }
    if (cacheKey) await AsyncStorage.setItem(cacheKey, JSON.stringify({ data: body, at: Date.now() }));
    return { data: body, offline: false };
  } catch (e) {
    if (cacheKey) {
      const cached = await AsyncStorage.getItem(cacheKey);
      if (cached) { const c = JSON.parse(cached); return { data: c.data, offline: true, cachedAt: c.at }; }
    }
    return { data: null, offline: true, error: "Sem conexão com o servidor" };
  } finally {
    clearTimeout(t);
  }
}

export const api = {
  risk: () => request("/api/risk", {}, "cache_risk"),
  weather: () => request("/api/weather", {}, "cache_weather"),
  alerts: () => request("/api/alerts", {}, "cache_alerts"),
  areas: () => request("/api/areas", {}, "cache_areas"),
  // [ATUALIZADO] session_id mantém o contexto da triagem entre mensagens
  chat: (message, area_id, session_id) =>
    request("/api/chat", { method: "POST", body: JSON.stringify({ message, area_id, session_id }) }),
  // [NOVO] cadastro do cidadão
  addContact: (c) => request("/api/contacts", { method: "POST", body: JSON.stringify(c) }),
  deleteContact: (id) => request(`/api/contacts/${id}`, { method: "DELETE" }),
  // [NOVO] conselho sob demanda (Gemini) — botão "O que fazer?" e alerta vermelho automático
  // Timeout maior: chamada ao Gemini pode demorar bem mais que os outros endpoints (~10-60s observado)
  advice: (trigger, location, session_id) =>
    request("/api/advice", { method: "POST", body: JSON.stringify({ trigger, location, session_id }) }, null, 60000),
};
