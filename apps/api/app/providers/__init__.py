from typing import Any

from ..config import settings
from ..domain import Provider
from .base import AccountRef, AdsGateway, Credentials, DiscoveredAccount, ExecutionResult, ProviderError, TokenBundle
from .google_ads import GoogleAdsGateway
from .tiktok_ads import TikTokAdsGateway

__all__ = [
    "AccountRef",
    "AdsGateway",
    "Credentials",
    "DiscoveredAccount",
    "ExecutionResult",
    "ProviderError",
    "TokenBundle",
    "gateway",
    "override_gateway",
    "provider_catalog",
]

_gateways: dict[str, Any] = {}


def gateway(provider: str) -> Any:
    if provider not in _gateways:
        _gateways[provider] = GoogleAdsGateway() if provider == Provider.GOOGLE_ADS else TikTokAdsGateway()
    return _gateways[provider]


def override_gateway(provider: str, instance: Any | None) -> None:
    """Tests swap the real gateways for fakes."""
    if instance is None:
        _gateways.pop(provider, None)
    else:
        _gateways[provider] = instance


CATALOG = {
    Provider.GOOGLE_ADS: {
        "name": "Google Ads",
        "readable": [
            "Contas e hierarquia MCC",
            "Campanhas, grupos e anúncios",
            "Palavras-chave e negativas",
            "Termos de pesquisa",
            "Extensões (assets)",
            "Conversões",
            "Métricas por dia",
            "Ideias de palavras-chave com volume",
        ],
        "editable": [
            "Criar campanha de Pesquisa (pausada)",
            "Redes (Parceiros/Display)",
            "Negativas",
            "Palavras-chave",
            "Títulos e descrições do RSA",
            "Estratégia de lance",
            "Data de término",
            "Segmentação por presença",
            "Pausar/ativar*",
            "Orçamento*",
            "Ações de conversão",
            "Conversões offline (GCLID)",
        ],
    },
    Provider.TIKTOK_ADS: {
        "name": "TikTok Ads",
        "readable": ["Anunciantes autorizados", "Campanhas e grupos de anúncios", "Anúncios", "Métricas por dia"],
        "editable": ["Criar campanha + grupo (desativados)", "Pausar/ativar*", "Orçamento*"],
    },
}


def provider_catalog() -> list[dict[str, Any]]:
    configured = {Provider.GOOGLE_ADS: settings.google_configured, Provider.TIKTOK_ADS: settings.tiktok_configured}
    return [
        {
            "provider": provider.value,
            **info,
            "configured": configured[provider],
            "mutations_enabled": settings.mutations_enabled(provider.value),
            "excluded": ["Pagamentos", "Meios de cobrança", "Adicionar saldo"],
        }
        for provider, info in CATALOG.items()
    ]
