"""Privacidade por design (LGPD):
- device_id / sessão pseudonimizados com HMAC-SHA256 + sal (não reversível sem o sal);
- geolocalização generalizada para grade de ~1 km (2 casas decimais);
- PII (CPF, telefone, e-mail, CEP) removida de textos antes de irem para logs;
- telefone/e-mail exibidos apenas mascarados nas interfaces."""
import hashlib
import hmac
import re
from typing import Optional

from ..config import settings

_PII_PATTERNS = [
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[CPF]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"),
    (re.compile(r"\b\d{5}-?\d{3}\b"), "[CEP]"),
    (re.compile(r"(\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}-?\d{4}\b"), "[TELEFONE]"),
]


def pseudonymize(value: str, prefix: str = "dev") -> str:
    digest = hmac.new(settings.privacy_salt.encode(), value.encode(), hashlib.sha256).hexdigest()
    return f"{prefix}_{digest[:10]}"


def generalize_location(lat: Optional[float], lon: Optional[float]) -> str:
    if lat is None or lon is None:
        return "zona_nao_informada"
    return f"grid_{round(lat, 2):.2f}_{round(lon, 2):.2f}"  # ~1,1 km de precisão


def scrub_pii(text: str) -> str:
    for pattern, token in _PII_PATTERNS:
        text = pattern.sub(token, text)
    return text


def mask_phone(e164: Optional[str]) -> Optional[str]:
    """5511987654321 -> +55 (11) 9****-4321"""
    if not e164:
        return None
    return f"+55 ({e164[2:4]}) {e164[4]}****-{e164[-4:]}"


def mask_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    user, _, domain = email.partition("@")
    return f"{user[0]}***@{domain}"
