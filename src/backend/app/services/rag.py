"""[ATUALIZADO] Retriever do RAG — BM25 em Python puro (roda offline na banca).

Base de conhecimento = SOMENTE arquivos locais da Defesa Civil:
  - data/protocolos_defesa_civil.json  -> condutas de segurança (PROT-xx)
  - data/areas_risco.json              -> áreas (AREA-xx), rotas (ROTA-xx) e abrigos (ABRIGO-n)
Interface `search()`/`get()` estável: pode ser trocada por embeddings (FAISS) sem mudar o agente."""
import json
import math
import re
import unicodedata
from collections import Counter
from typing import Dict, List, Optional

from ..config import DATA_DIR

STOPWORDS = set("a o e de da do das dos em no na nos nas um uma para por com que se ao as os eu meu minha "
                "como qual quais o que é ser vai tem ter isso esta este está há mais".split())


def normalize(text: str) -> List[str]:
    text = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    return [t for t in re.findall(r"[a-z0-9]+", text) if t not in STOPWORDS and len(t) > 1]


def strip_accents(text: str) -> str:
    return unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()


def build_corpus() -> List[Dict]:
    kb = json.loads((DATA_DIR / "protocolos_defesa_civil.json").read_text(encoding="utf-8"))
    areas = json.loads((DATA_DIR / "areas_risco.json").read_text(encoding="utf-8"))
    docs = [dict(d, origem="protocolos_defesa_civil.json") for d in kb["documentos"]]
    rotas = {r["id"]: r for r in areas.get("rotas", [])}
    for a in areas["areas"]:
        rota = rotas.get(a["rota"], {})
        alias_tags = [t for al in a.get("aliases", []) for t in normalize(al)]
        docs.append({"id": a["rota"], "titulo": f"Rota de fuga - {a['nome']} (Área {a['id']})",
                     "tags": ["rota", "fuga", "abrigo", "sair", a["id"].lower(), *normalize(a["nome"]), *alias_tags],
                     "texto": f"Área {a['id']} {a['nome']}: {rota.get('texto', '')}", "origem": "areas_risco.json"})
        docs.append({"id": f"AREA-{a['id']}", "titulo": f"Área de risco {a['nome']}",
                     "tags": ["area", "risco", "bairro", a["id"].lower(), *normalize(a["nome"]), *alias_tags],
                     "texto": (f"A área {a['id']} ({a['nome']}) tem vulnerabilidade {round(a['vulnerabilidade']*100)}% "
                               f"e cerca de {a['populacao_estimada']} moradores. Abrigo de referência: {a['abrigo']}. "
                               f"Rota de fuga: {a['rota']}."), "origem": "areas_risco.json"})
    for i, s in enumerate(areas["abrigos"], 1):
        docs.append({"id": f"ABRIGO-{i}", "titulo": f"Abrigo {s['nome']}",
                     "tags": ["abrigo", "pets" if s["aceita_pets"] else "abrigo", *normalize(s["nome"])],
                     "texto": (f"{s['nome']}: capacidade para {s['capacidade']} pessoas; "
                               f"{'aceita' if s['aceita_pets'] else 'não aceita'} animais de estimação."),
                     "origem": "areas_risco.json"})
    return docs


class BM25Retriever:
    def __init__(self, docs: List[Dict], k1: float = 1.5, b: float = 0.75):
        self.docs = docs
        self.k1, self.b = k1, b
        self.tokens = [normalize(f"{d['titulo']} {d['titulo']} {' '.join(d['tags']) * 2} {d['texto']}") for d in docs]
        self.avgdl = sum(map(len, self.tokens)) / len(self.tokens)
        df = Counter(t for doc in self.tokens for t in set(doc))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.tf = [Counter(doc) for doc in self.tokens]

    def search(self, query: str, k: int = 3) -> List[Dict]:
        q = normalize(query)
        scored = []
        for i, tf in enumerate(self.tf):
            dl = len(self.tokens[i])
            s = sum(self.idf.get(t, 0) * tf[t] * (self.k1 + 1) /
                    (tf[t] + self.k1 * (1 - self.b + self.b * dl / self.avgdl)) for t in q if t in tf)
            if s > 0:
                scored.append({**self.docs[i], "score": round(s, 3)})
        return sorted(scored, key=lambda d: d["score"], reverse=True)[:k]

    def get(self, doc_id: str) -> Optional[Dict]:
        return next((d for d in self.docs if d["id"] == doc_id), None)


retriever = BM25Retriever(build_corpus())
