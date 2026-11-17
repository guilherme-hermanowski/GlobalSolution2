import { useCallback, useEffect, useState } from "react";
import { RefreshControl, ScrollView, StyleSheet, Text, TouchableOpacity, View, Linking } from "react-native";
import { api } from "../api";
import { POLL_MS } from "../config";
import { RISK } from "../theme";

const AREAS = [["A1", "Jardim Ribeirinho"], ["B2", "Vila Baixada"], ["C3", "Parque das Águas"]];

export default function HomeScreen({ areaId, setAreaId, goTo }) {
  const [risk, setRisk] = useState(null);
  const [weather, setWeather] = useState(null);
  const [offline, setOffline] = useState(false);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const [r, w] = await Promise.all([api.risk(), api.weather()]);
    setRisk(r.data); setWeather(w.data); setOffline(r.offline);
    setLoading(false);
  }, []);

  useEffect(() => { load(); const id = setInterval(load, POLL_MS); return () => clearInterval(id); }, [load]);

  const level = risk?.level || "VERDE";
  const theme = RISK[level];
  const areaName = AREAS.find(([id]) => id === areaId)?.[1];
  const myAreaAffected = risk?.affected_areas?.includes(areaName);

  return (
    <ScrollView contentContainerStyle={s.c} refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}>
      <Text style={s.h1}>AlertaCidadão 💧</Text>
      {offline && <Text style={s.offline}>Sem conexão — exibindo último dado salvo.</Text>}

      <Text style={s.sub}>Minha área:</Text>
      <View style={s.row}>
        {AREAS.map(([id, nome]) => (
          <TouchableOpacity key={id} onPress={() => setAreaId(id)} style={[s.chip, areaId === id && s.chipOn]}>
            <Text style={areaId === id ? s.chipTxtOn : null}>{nome}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <View style={[s.card, { backgroundColor: theme.bg, borderColor: theme.color }]}>
        <Text style={s.semaforo}>{theme.emoji}</Text>
        <Text style={[s.level, { color: theme.color }]}>{theme.label}</Text>
        {risk && <Text style={s.score}>Índice de risco: {Math.round(risk.score)}/100</Text>}
        <Text style={s.action}>{theme.action}</Text>
        {risk && level !== "VERDE" && (
          <Text style={s.area}>{myAreaAffected ? `⚠️ ${areaName} está entre as áreas afetadas.` : `${areaName} não está entre as áreas afetadas no momento.`}</Text>
        )}
      </View>

      {risk && (
        <View style={s.box}>
          <Text style={s.h2}>O que fazer agora</Text>
          {risk.instructions.slice(0, 4).map((i) => <Text key={i} style={s.item}>• {i}</Text>)}
          <Text style={s.src}>Fonte: protocolos {risk.protocol_refs.join(", ")} · dados {risk.data_source}</Text>
        </View>
      )}

      {weather && (
        <View style={s.box}>
          <Text style={s.h2}>Próximos dias · {weather.city}</Text>
          <View style={s.row}>
            {weather.forecast.map((d) => (
              <View key={d.date} style={[s.day, { backgroundColor: d.rain_mm >= 50 ? "#fee2e2" : d.rain_mm >= 30 ? "#fef3c7" : "#dcfce7" }]}>
                <Text style={s.dayTxt}>{d.date.slice(8)}/{d.date.slice(5, 7)}</Text>
                <Text style={s.dayTxt}>{Math.round(d.rain_mm)}mm</Text>
              </View>
            ))}
          </View>
          <Text style={s.src}>Fonte: {weather.source}</Text>
        </View>
      )}

      <View style={s.row}>
        <TouchableOpacity style={[s.btn, { backgroundColor: "#0369a1" }]} onPress={() => goTo("chat")}><Text style={s.btnTxt}>💬 Dúvidas / Relatar</Text></TouchableOpacity>
        <TouchableOpacity style={[s.btn, { backgroundColor: "#dc2626" }]} onPress={() => Linking.openURL("tel:199")}><Text style={s.btnTxt}>📞 Defesa Civil 199</Text></TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  c: { padding: 16, gap: 12 },
  h1: { fontSize: 26, fontWeight: "800", color: "#0f172a" },
  h2: { fontSize: 16, fontWeight: "700", marginBottom: 6 },
  sub: { color: "#475569" },
  offline: { backgroundColor: "#fee2e2", color: "#991b1b", padding: 8, borderRadius: 8 },
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999, backgroundColor: "#e2e8f0" },
  chipOn: { backgroundColor: "#0369a1" }, chipTxtOn: { color: "#fff", fontWeight: "700" },
  card: { borderWidth: 3, borderRadius: 20, padding: 20, alignItems: "center" },
  semaforo: { fontSize: 64 }, level: { fontSize: 28, fontWeight: "900" },
  score: { color: "#334155", marginTop: 4 }, action: { fontSize: 16, textAlign: "center", marginTop: 10, fontWeight: "600" },
  area: { marginTop: 8, textAlign: "center" },
  box: { backgroundColor: "#fff", borderRadius: 14, padding: 14, borderWidth: 1, borderColor: "#e2e8f0" },
  item: { marginBottom: 4, lineHeight: 20 }, src: { fontSize: 11, color: "#64748b", marginTop: 6 },
  day: { padding: 8, borderRadius: 10, alignItems: "center", minWidth: 56 }, dayTxt: { fontSize: 12 },
  btn: { flex: 1, padding: 14, borderRadius: 12, alignItems: "center" }, btnTxt: { color: "#fff", fontWeight: "700" },
});
