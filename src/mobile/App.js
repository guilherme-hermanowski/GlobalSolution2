import { useState } from "react";
import { SafeAreaView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import HomeScreen from "./src/screens/HomeScreen";
import ChatScreen from "./src/screens/ChatScreen";
import AlertsScreen from "./src/screens/AlertsScreen";

// Navegação por abas simples (sem dependências extras) — suficiente para a POC.
const TABS = [
  { id: "home", label: "Início", icon: "🏠", Screen: HomeScreen },
  { id: "chat", label: "Assistente", icon: "💬", Screen: ChatScreen },
  { id: "alerts", label: "Alertas & Abrigos", icon: "🚨", Screen: AlertsScreen },
];

export default function App() {
  const [tab, setTab] = useState("home");
  const [areaId, setAreaId] = useState("A1"); // área escolhida pelo cidadão (sem GPS = privacidade)
  const Current = TABS.find((t) => t.id === tab).Screen;
  return (
    <SafeAreaView style={s.root}>
      <StatusBar style="dark" />
      <View style={s.content}><Current areaId={areaId} setAreaId={setAreaId} goTo={setTab} /></View>
      <View style={s.tabbar}>
        {TABS.map((t) => (
          <TouchableOpacity key={t.id} style={s.tab} onPress={() => setTab(t.id)} accessibilityRole="tab">
            <Text style={s.icon}>{t.icon}</Text>
            <Text style={[s.label, tab === t.id && s.active]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#f8fafc" },
  content: { flex: 1 },
  tabbar: { flexDirection: "row", borderTopWidth: 1, borderColor: "#e2e8f0", backgroundColor: "#fff", paddingVertical: 6 },
  tab: { flex: 1, alignItems: "center" },
  icon: { fontSize: 20 },
  label: { fontSize: 11, color: "#64748b" },
  active: { color: "#0369a1", fontWeight: "700" },
});
