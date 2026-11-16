import AsyncStorage from "@react-native-async-storage/async-storage";
import { API_URL } from "./config";

// Cache offline: se o backend cair, o app mostra o último risco conhecido (resiliência).
async function request(path, options = {}, cacheKey) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 7000);
  try {
    const res = await fetch(`${API_URL}${path}`, {
      ...options, signal: ctrl.signal, headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (cacheKey) await AsyncStorage.setItem(cacheKey, JSON.stringify({ data, at: Date.now() }));
    return { data, offline: false };
  } catch (e) {
    if (cacheKey) {
      const cached = await AsyncStorage.getItem(cacheKey);
      if (cached) { const c = JSON.parse(cached); return { data: c.data, offline: true, cachedAt: c.at }; }
    }
    return { data: null, offline: true };
  } finally {
    clearTimeout(t);
  }
}

export const api = {
  risk: () => request("/api/risk", {}, "cache_risk"),
  weather: () => request("/api/weather", {}, "cache_weather"),
  alerts: () => request("/api/alerts", {}, "cache_alerts"),
  areas: () => request("/api/areas", {}, "cache_areas"),
  chat: (message, area_id) => request("/api/chat", { method: "POST", body: JSON.stringify({ message, area_id }) }),
};
