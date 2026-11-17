// [NOVO] Cadastro do cidadão para receber alertas por WhatsApp/e-mail (com consentimento LGPD).
import { useEffect, useState } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { ScrollView, StyleSheet, Switch, Text, TextInput, TouchableOpacity, View } from "react-native";
import { api } from "../api";

const AREAS = [["A1", "Jardim Ribeirinho"], ["B2", "Vila Baixada"], ["C3", "Parque das Águas"]];

function maskPhone(v) {
  const d = v.replace(/\D/g, "").slice(0, 11);
  if (d.length <= 2) return d;
  if (d.length <= 7) return `(${d.slice(0, 2)}) ${d.slice(2)}`;
  return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
}

export default function ContactScreen({ areaId, setAreaId }) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [whats, setWhats] = useState(true);
  const [mail, setMail] = useState(false);
  const [consent, setConsent] = useState(false);
  const [saved, setSaved] = useState(null);
  const [msg, setMsg] = useState(null);

  useEffect(() => { AsyncStorage.getItem("my_contact").then((v) => v && setSaved(JSON.parse(v))); }, []);

  async function save() {
    const channels = [whats && "whatsapp", mail && "email"].filter(Boolean);
    const r = await api.addContact({ name, phone: phone || null, email: email || null, area_id: areaId, channels, consent });
    if (r.data) {
      await AsyncStorage.setItem("my_contact", JSON.stringify(r.data));
      setSaved(r.data); setMsg({ ok: true, text: "Cadastro concluído! Você receberá alertas da sua área." });
    } else setMsg({ ok: false, text: r.error });
  }

  async function remove() {
    if (saved) await api.deleteContact(saved.id);
    await AsyncStorage.removeItem("my_contact");
    setSaved(null); setMsg({ ok: true, text: "Seus dados foram excluídos." });
  }

  if (saved) {
    return (
      <View style={s.c}>
        <Text style={s.h1}>📲 Alertas ativos</Text>
        <View style={s.box}>
          <Text style={s.h3}>{saved.name}</Text>
          <Text>{[saved.phone_masked, saved.email_masked].filter(Boolean).join(" · ")}</Text>
          <Text>Área: {AREAS.find(([id]) => id === saved.area_id)?.[1]} · canais: {saved.channels.join(", ")}</Text>
        </View>
        <TouchableOpacity style={[s.btn, { backgroundColor: "#64748b" }]} onPress={remove}>
          <Text style={s.btnTxt}>Excluir meus dados (LGPD)</Text>
        </TouchableOpacity>
        {msg && <Text style={msg.ok ? s.ok : s.err}>{msg.text}</Text>}
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={s.c}>
      <Text style={s.h1}>📲 Receber alertas</Text>
      <Text style={s.small}>Cadastre seu WhatsApp para receber avisos da Defesa Civil sobre a sua área.</Text>
      <TextInput style={s.input} placeholder="Seu nome" value={name} onChangeText={setName} maxLength={60} />
      <TextInput style={s.input} placeholder="(11) 98765-4321" keyboardType="phone-pad" value={phone} onChangeText={(v) => setPhone(maskPhone(v))} />
      <TextInput style={s.input} placeholder="E-mail (opcional)" keyboardType="email-address" autoCapitalize="none" value={email} onChangeText={setEmail} />
      <Text style={s.sub}>Minha área:</Text>
      <View style={s.row}>
        {AREAS.map(([id, nome]) => (
          <TouchableOpacity key={id} onPress={() => setAreaId(id)} style={[s.chip, areaId === id && s.chipOn]}>
            <Text style={areaId === id ? { color: "#fff", fontWeight: "700" } : null}>{nome}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <View style={s.switchRow}><Text>WhatsApp</Text><Switch value={whats} onValueChange={setWhats} /></View>
      <View style={s.switchRow}><Text>E-mail</Text><Switch value={mail} onValueChange={setMail} /></View>
      <View style={s.switchRow}>
        <Text style={{ flex: 1, fontSize: 12 }}>Autorizo o uso do meu contato apenas para alertas da Defesa Civil. Posso excluir meus dados a qualquer momento (LGPD).</Text>
        <Switch value={consent} onValueChange={setConsent} />
      </View>
      <TouchableOpacity style={[s.btn, { backgroundColor: consent ? "#0369a1" : "#94a3b8" }]} onPress={save} disabled={!consent}>
        <Text style={s.btnTxt}>Cadastrar</Text>
      </TouchableOpacity>
      {msg && <Text style={msg.ok ? s.ok : s.err}>{msg.text}</Text>}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  c: { padding: 16, gap: 12 },
  h1: { fontSize: 22, fontWeight: "800" }, h3: { fontWeight: "700", fontSize: 16 },
  sub: { color: "#475569" }, small: { fontSize: 12, color: "#64748b" },
  input: { backgroundColor: "#fff", borderWidth: 1, borderColor: "#cbd5e1", borderRadius: 12, padding: 12 },
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999, backgroundColor: "#e2e8f0" }, chipOn: { backgroundColor: "#0369a1" },
  switchRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 },
  box: { backgroundColor: "#fff", borderRadius: 12, padding: 12, borderWidth: 1, borderColor: "#e2e8f0", gap: 4 },
  btn: { padding: 14, borderRadius: 12, alignItems: "center" }, btnTxt: { color: "#fff", fontWeight: "700" },
  ok: { color: "#15803d" }, err: { color: "#b91c1c" },
});
