import { useRef, useState } from "react";
import { ActivityIndicator, FlatList, KeyboardAvoidingView, Platform, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { api } from "../api";

const SUGGESTIONS = ["Vai ter risco de enchente nos próximos dias?", "O que levar no kit de emergência?", "Qual a rota de fuga da minha área?", "O que fazer se a água entrar em casa?"];

export default function ChatScreen({ areaId }) {
  const [messages, setMessages] = useState([
    { id: "0", from: "bot", text: "Olá! Sou o assistente da Defesa Civil. Respondo com base nos protocolos oficiais. Não compartilhe dados pessoais (CPF, telefone)." },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const listRef = useRef(null);

  async function send(text) {
    const q = (text ?? input).trim();
    if (q.length < 2 || busy) return;
    setInput("");
    setMessages((m) => [...m, { id: String(Date.now()), from: "user", text: q }]);
    setBusy(true);
    const { data } = await api.chat(q, areaId);
    const reply = data
      ? { text: data.answer, sources: data.sources, grounded: data.grounded, mode: data.mode }
      : { text: "Sem conexão com o servidor. Em emergência ligue 199 (Defesa Civil) ou 193 (Bombeiros).", sources: [] };
    setMessages((m) => [...m, { id: String(Date.now() + 1), from: "bot", ...reply }]);
    setBusy(false);
    setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 100);
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={(m) => m.id}
        contentContainerStyle={s.list}
        renderItem={({ item }) => (
          <View style={[s.msg, item.from === "user" ? s.user : s.bot]}>
            <Text style={item.from === "user" ? s.userTxt : null}>{item.text}</Text>
            {item.sources?.length > 0 && <Text style={s.src}>📘 Fontes: {item.sources.join(", ")} · {item.mode}</Text>}
            {item.grounded === false && <Text style={s.src}>⚠️ Fora da base oficial — resposta de segurança</Text>}
          </View>
        )}
        ListFooterComponent={busy ? <ActivityIndicator style={{ margin: 10 }} /> : null}
      />
      <View style={s.sugg}>
        {SUGGESTIONS.map((q) => (
          <TouchableOpacity key={q} onPress={() => send(q)} style={s.chip}><Text style={s.chipTxt}>{q}</Text></TouchableOpacity>
        ))}
      </View>
      <View style={s.inputRow}>
        <TextInput style={s.input} value={input} onChangeText={setInput} placeholder="Digite sua dúvida…" maxLength={500} onSubmitEditing={() => send()} />
        <TouchableOpacity style={s.send} onPress={() => send()} disabled={busy}><Text style={{ color: "#fff", fontWeight: "700" }}>Enviar</Text></TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  list: { padding: 12, gap: 8 },
  msg: { padding: 12, borderRadius: 14, maxWidth: "88%" },
  bot: { backgroundColor: "#fff", alignSelf: "flex-start", borderWidth: 1, borderColor: "#e2e8f0" },
  user: { backgroundColor: "#0369a1", alignSelf: "flex-end" }, userTxt: { color: "#fff" },
  src: { fontSize: 11, color: "#64748b", marginTop: 6 },
  sugg: { flexDirection: "row", flexWrap: "wrap", gap: 6, paddingHorizontal: 10 },
  chip: { backgroundColor: "#e0f2fe", paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999 }, chipTxt: { fontSize: 12, color: "#075985" },
  inputRow: { flexDirection: "row", padding: 10, gap: 8 },
  input: { flex: 1, backgroundColor: "#fff", borderWidth: 1, borderColor: "#cbd5e1", borderRadius: 12, paddingHorizontal: 12 },
  send: { backgroundColor: "#0369a1", paddingHorizontal: 16, justifyContent: "center", borderRadius: 12 },
});
