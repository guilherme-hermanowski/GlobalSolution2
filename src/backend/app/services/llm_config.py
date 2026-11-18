"""Configuração do modelo Gemini usado pelo SDK de agentes — mesma implementação do
projeto CardioIA (shared/agentes/llm_config.py): fala com o Gemini através do endpoint
dele compatível com a API da OpenAI, com rotação entre chaves em caso de 429/503.

Diferente do CardioIA, NÃO cacheia o cliente (sem @lru_cache): cada chamada daqui roda
dentro do próprio event loop que o Runner.run_sync() cria pra ela (FastAPI é sync aqui,
cada requisição pode cair numa thread/loop diferente do threadpool). Um client async
cacheado entre chamadas trava com "Event ... is bound to a different event loop", porque
os locks internos do httpx2 nascem amarrados ao loop da primeira chamada."""
import itertools

import httpx2
from agents import OpenAIChatCompletionsModel, set_tracing_disabled
from openai import AsyncOpenAI

from ..config import settings
from .chaves_llm import ler_chaves_gemini

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

set_tracing_disabled(True)


class _TransporteComRotacaoDeChave(httpx2.AsyncHTTPTransport):
    """Distribui as chamadas entre várias chaves do Gemini (round-robin) e, se uma delas
    devolver 429/503 (cota esgotada ou sobrecarga), tenta de novo com a próxima antes de desistir."""

    def __init__(self, chaves: list[str]):
        super().__init__()
        self._chaves = chaves
        self._contador = itertools.count()

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        resposta = await super().handle_async_request(self._com_proxima_chave(request))
        for _ in range(len(self._chaves) - 1):
            if resposta.status_code not in (429, 503):
                return resposta
            await resposta.aread()
            resposta = await super().handle_async_request(self._com_proxima_chave(request))
        return resposta

    def _com_proxima_chave(self, request: httpx2.Request) -> httpx2.Request:
        chave = self._chaves[next(self._contador) % len(self._chaves)]
        request.headers["authorization"] = f"Bearer {chave}"
        return request


def obter_modelo_gemini() -> OpenAIChatCompletionsModel:
    """Cria o cliente do modelo Gemini usado pelos agentes — uma instância nova por
    chamada (ver docstring do módulo pra entender por quê não cacheia)."""
    chaves = ler_chaves_gemini()
    cliente_http = httpx2.AsyncClient(transport=_TransporteComRotacaoDeChave(chaves))
    cliente = AsyncOpenAI(base_url=GEMINI_BASE_URL, api_key=chaves[0], http_client=cliente_http)
    return OpenAIChatCompletionsModel(model=settings.llm_model, openai_client=cliente)
