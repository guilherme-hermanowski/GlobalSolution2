"""Leitura das chaves de API do Gemini — mesmo padrão usado no projeto CardioIA
(shared/chaves_llm.py), pra permitir rotação entre várias chaves/contas Google."""
import os


def ler_chaves_gemini() -> list[str]:
    """GEMINI_API_KEYS aceita várias chaves separadas por vírgula (uma por conta Google).
    GEMINI_API_KEY/GOOGLE_API_KEY seguem funcionando como alternativa de uma chave só."""
    bruto = os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
    chaves = [chave.strip() for chave in bruto.split(",") if chave.strip()]
    if not chaves:
        raise RuntimeError(
            "Nenhuma chave de API do Gemini definida — defina GEMINI_API_KEYS (uma ou mais, "
            "separadas por vírgula) ou GEMINI_API_KEY no .env (ver .env.example)."
        )
    return chaves


def tem_chave_gemini() -> bool:
    try:
        ler_chaves_gemini()
        return True
    except RuntimeError:
        return False
