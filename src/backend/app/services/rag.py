"""Retriever do RAG — BM25 implementado em Python puro (zero dependências pesadas,
roda offline na banca). Pode ser trocado por embeddings (ex.: sentence-transformers + FAISS)
mantendo a mesma interface `search()`."""
import json
import math
import re
import unicodedata
from collections import Counter
from typing import Dict, List

from ..config import DATA_DIR

STOPWORDS = set("a o e de da do das dos em no na nos nas um uma para por com que se ao as os eu meu minha "
                "como qual quais o que é ser vai tem ter isso esta este está há".split())


def normalize(text: str) -> List[str]:
    text = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    return [t for t in re.findall(r"[a-z0-9]+", text) if t not in STOPWORDS and len(t) > 1]


class BM25Retriever:
    def __init__(self, docs: List[Dict], k1: float = 1.5, b: float = 0.75):
        self.docs = docs
        self.k1, self.b = k1, b
        # título e tags recebem peso extra (repetição) para melhorar a precisão
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

    def get(self, doc_id: str) -> Dict:
        return next((d for d in self.docs if d["id"] == doc_id), None)


_KB = json.loads((DATA_DIR / "protocolos_defesa_civil.json").read_text(encoding="utf-8"))
retriever = BM25Retriever(_KB["documentos"])
