// [ATUALIZADO] Chat com roteamento: dúvidas (RAG) e relatos de emergência (triagem -> ocorrência).
import { useRef, useState } from "react";
import { ActivityIndicator, FlatList, KeyboardAvoidingView, Linking, Platform, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { api } from "../api";

const SUGGESTIONS = [
  "A água entrou na minha casa",
  "Vai ter risco de enchente nos próximos dias?",
  "Qual a rota de fuga da minha área?",
  "O que levar no kit de emergência?",
];

export default function ChatScreen({ areaId }) {
  const [messages, setMessages] = useState([
    { id: "0", from: "bot", text: "Olá! Sou o assistente da Defesa Civil. Tire dúvidas ou relate uma emergência (diga o que está acontecendo e onde). Não compartilhe CPF ou telefone aqui." },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const listRef = useRef(null);

  async function send(text) {
    const q = (text ?? input).trim();
    if (q.length < 2 || busy) return;
    setInput("");
    setMessages((m) => [...m, { id: String(Date.now()), from: "user", text: q }]);
    setBusy(true);
    const { data } = await api.chat(q, areaId, sessionId);
    if (data?.session_id) setSessionId(data.session_id);
    const reply = data
      ? { text: data.answer, sources: data.sources, grounded: data.grounded, mode: data.mode, triage: data.triage }
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
            {item.triage?.status === "registrada" && (
              <View style={s.occCard}>
                <Text style={s.occTitle}>✅ Protocolo {item.triage.occurrence_id} · {item.triage.priority}</Text>
                {item.triage.priority === "P1" && (
                  <TouchableOpacity style={s.call} onPress={() => Linking.openURL("tel:193")}>
                    <Text style={{ color: "#fff", fontWeight: "800" }}>📞 Ligar 193 agora</Text>
                  </TouchableOpacity>
                )}
              </View>
            )}
            {item.triage?.status === "coletando" && <Text style={s.src}>📝 Registrando ocorrência…</Text>}
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
        <TextInput style={s.input} value={input} onChangeText={setInput} placeholder="Digite sua dúvida ou relato…" maxLength={500} onSubmitEditing={() => send()} />
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
  occCard: { marginTop: 8, backgroundColor: "#dcfce7", borderRadius: 10, padding: 8, gap: 6 },
  occTitle: { fontWeight: "700", color: "#14532d" },
  call: { backgroundColor: "#dc2626", padding: 10, borderRadius: 10, alignItems: "center" },
  sugg: { flexDirection: "row", flexWrap: "wrap", gap: 6, paddingHorizontal: 10 },
  chip: { backgroundColor: "#e0f2fe", paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999 }, chipTxt: { fontSize: 12, color: "#075985" },
  inputRow: { flexDirection: "row", padding: 10, gap: 8 },
  input: { flex: 1, backgroundColor: "#fff", borderWidth: 1, borderColor: "#cbd5e1", borderRadius: 12, paddingHorizontal: 12 },
  send: { backgroundColor: "#0369a1", paddingHorizontal: 16, justifyContent: "center", borderRadius: 12 },
});
