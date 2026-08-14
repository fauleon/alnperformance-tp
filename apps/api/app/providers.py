from enum import StrEnum
from urllib.parse import urlencode

from pydantic import BaseModel

from .config import settings


class ProviderName(StrEnum):
    GOOGLE_ADS = "GOOGLE_ADS"
    META_ADS = "META_ADS"


class ProviderCapability(BaseModel):
    provider: ProviderName
    configured: bool
    connected: bool = False
    mutation_enabled: bool
    oauth_url: str | None
    readable: tuple[str, ...]
    editable: tuple[str, ...]
    excluded: tuple[str, ...] = ("PAYMENTS", "BILLING_METHODS", "ADD_FUNDS")


GOOGLE_READ = ("accounts", "campaigns", "ad_groups", "ads", "assets", "keywords", "audiences", "conversions", "metrics", "search_terms")
GOOGLE_EDIT = ("campaigns", "ad_groups", "ads", "assets", "keywords", "negative_keywords", "audiences", "geo_targets", "schedules", "bids", "budgets", "conversion_actions")
META_READ = ("ad_accounts", "campaigns", "ad_sets", "ads", "creatives", "audiences", "pixels", "events", "insights")
META_EDIT = ("campaigns", "ad_sets", "ads", "creatives", "audiences", "placements", "optimization", "budgets", "pixels", "conversion_events")


def google_oauth_url(state: str) -> str | None:
    if not settings.google_client_id:
        return None
    query = urlencode({
        "client_id": settings.google_client_id,
        "redirect_uri": f"{settings.public_api_url}/v1/connections/google/callback",
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/adwords",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    })
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"


def meta_oauth_url(state: str) -> str | None:
    if not settings.meta_app_id:
        return None
    query = urlencode({
        "client_id": settings.meta_app_id,
        "redirect_uri": f"{settings.public_api_url}/v1/connections/meta/callback",
        "response_type": "code",
        "scope": "ads_management,ads_read,business_management,read_insights",
        "state": state,
    })
    return f"https://www.facebook.com/v23.0/dialog/oauth?{query}"


def capabilities(provider: ProviderName, state: str) -> ProviderCapability:
    if provider == ProviderName.GOOGLE_ADS:
        configured = bool(settings.google_client_id and settings.google_client_secret and settings.google_ads_developer_token)
        return ProviderCapability(provider=provider, configured=configured, mutation_enabled=settings.google_ads_mutations_enabled and not settings.global_kill_switch, oauth_url=google_oauth_url(state), readable=GOOGLE_READ, editable=GOOGLE_EDIT)
    configured = bool(settings.meta_app_id and settings.meta_app_secret)
    return ProviderCapability(provider=provider, configured=configured, mutation_enabled=settings.meta_ads_mutations_enabled and not settings.global_kill_switch, oauth_url=meta_oauth_url(state), readable=META_READ, editable=META_EDIT)
