const dayName = (iso) => new Date(iso + "T12:00:00").toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit" });

export default function WeatherCard({ weather }) {
  if (!weather) return <section className="card">Carregando clima…</section>;
  const { current, forecast } = weather;
  return (
    <section className="card">
      <h3>🌦️ Meteorologia <span className={`pill ${weather.source === "openweathermap" ? "ok" : "warn"}`}>{weather.source}</span></h3>
      <p className="big">{Math.round(current.temp_c)}°C · {current.description}</p>
      <p>Umidade {current.humidity}% · Chuva última hora {current.rain_1h_mm} mm</p>
      <div className="forecast">
        {forecast.map((d) => (
          <div key={d.date} className={`fday ${d.rain_mm >= 50 ? "red" : d.rain_mm >= 30 ? "yellow" : "green"}`}>
            <b>{dayName(d.date)}</b>
            <span>{d.rain_mm} mm</span>
            <small>{Math.round(d.pop * 100)}% prob.</small>
          </div>
        ))}
      </div>
    </section>
  );
}
