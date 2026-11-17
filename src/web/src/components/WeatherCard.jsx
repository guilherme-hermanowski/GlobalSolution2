// [ATUALIZADO] mostra a origem do dado (API real, cache ou mock) e o motivo do fallback.
const dayName = (iso) => new Date(iso + "T12:00:00").toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit" });
const SOURCE = {
  openweathermap: { text: "OpenWeatherMap (real)", cls: "ok" },
  openweathermap_cache: { text: "Cache do último dado real", cls: "warn" },
  mock: { text: "Mock (sem chave de API)", cls: "warn" },
  mock_fallback: { text: "Mock (falha na API)", cls: "bad" },
};

export default function WeatherCard({ weather, status }) {
  if (!weather) return <section className="card">Carregando clima…</section>;
  const { current, forecast } = weather;
  const src = SOURCE[weather.source] || SOURCE.mock;
  return (
    <section className="card">
      <h3>🌦️ Meteorologia · {weather.city} <span className={`pill ${src.cls}`}>{src.text}</span></h3>
      <p className="big">
        {current.icon && <img alt="" width="36" height="36" style={{ verticalAlign: "middle" }} src={`https://openweathermap.org/img/wn/${current.icon}.png`} />}
        {Math.round(current.temp_c)}°C · {current.description}
      </p>
      <p>Sensação {Math.round(current.feels_like_c ?? current.temp_c)}°C · Umidade {current.humidity}% · Vento {current.wind_kmh ?? "-"} km/h · Chuva 1h {current.rain_1h_mm} mm</p>
      {weather.fallback_reason && <p className="muted">⚠️ Fallback: {weather.fallback_reason}</p>}
      <div className="forecast">
        {forecast.map((d) => (
          <div key={d.date} className={`fday ${d.rain_mm >= 50 ? "red" : d.rain_mm >= 30 ? "yellow" : "green"}`} title={d.description}>
            <b>{dayName(d.date)}</b>
            <span>{d.rain_mm} mm</span>
            <small>{Math.round(d.pop * 100)}% prob.</small>
            <small>{Math.round(d.temp_min)}°/{Math.round(d.temp_max)}°</small>
          </div>
        ))}
      </div>
      {status && <small className="legend">Chamadas API: {status.calls} · falhas: {status.failures}{status.cache_age_s != null && ` · cache ${Math.round(status.cache_age_s)}s`}</small>}
    </section>
  );
}
