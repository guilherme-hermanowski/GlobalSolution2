import { useCallback, useEffect, useState } from "react";
import { RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { api } from "../api";
import { RISK } from "../theme";

export default function AlertsScreen({ areaId }) {
  const [alerts, setAlerts] = useState([]);
  const [areas, setAreas] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const [a, ar] = await Promise.all([api.alerts(), api.areas()]);
    setAlerts(a.data || []); setAreas(ar.data);
    setLoading(false);
  }, []);
  useEffect(() => { load(); }, [load]);

  const myArea = areas?.areas.find((a) => a.id === areaId);

  return (
    <ScrollView contentContainerStyle={s.c} refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}>
      {myArea && (
        <View style={[s.box, { borderColor: "#0369a1", borderWidth: 2 }]}>
          <Text style={s.h2}>🧭 Sua rota segura — {myArea.nome}</Text>
          <Text>Abrigo de referência: <Text style={{ fontWeight: "700" }}>{myArea.abrigo}</Text></Text>
          <Text style={s.small}>Pergunte ao Assistente "qual a rota de fuga da minha área?" para o trajeto detalhado ({myArea.rota}).</Text>
        </View>
      )}

      <Text style={s.h1}>🏠 Abrigos</Text>
      {areas?.abrigos.map((ab) => (
        <View key={ab.nome} style={s.box}>
          <Text style={s.h3}>{ab.nome}</Text>
          <Text>Capacidade: {ab.capacidade} pessoas {ab.aceita_pets ? "· 🐾 aceita pets" : ""}</Text>
        </View>
      ))}

      <Text style={s.h1}>🚨 Alertas emitidos</Text>
      {alerts.length === 0 && <Text style={s.small}>Nenhum alerta no momento.</Text>}
      {alerts.map((a) => (
        <View key={a.id} style={[s.box, { borderLeftWidth: 6, borderLeftColor: RISK[a.level].color }]}>
          <Text style={s.h3}>{RISK[a.level].emoji} {a.title}</Text>
          <Text style={s.small}>{new Date(a.created_at).toLocaleString("pt-BR")} · dados {a.data_source}</Text>
          <Text style={{ marginTop: 4 }}>{a.summary}</Text>
          {a.affected_areas.length > 0 && <Text style={s.small}>Áreas: {a.affected_areas.join(", ")}</Text>}
        </View>
      ))}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  c: { padding: 16, gap: 10 },
  h1: { fontSize: 20, fontWeight: "800", marginTop: 8 }, h2: { fontSize: 16, fontWeight: "700", marginBottom: 4 }, h3: { fontWeight: "700" },
  box: { backgroundColor: "#fff", borderRadius: 12, padding: 12, borderWidth: 1, borderColor: "#e2e8f0" },
  small: { fontSize: 12, color: "#64748b", marginTop: 4 },
});
