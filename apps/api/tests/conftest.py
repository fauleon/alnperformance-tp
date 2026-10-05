import os
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from cryptography.fernet import Fernet

# Environment must be set before the app is imported.
_db = Path(tempfile.mkdtemp(prefix="alnia-tests-")) / "test.db"
os.environ.update({
    "APP_ENV": "test",
    # CI sets TEST_DATABASE_URL to a real Postgres (migrated with alembic before the run).
    "DATABASE_URL": os.environ.get("TEST_DATABASE_URL") or f"sqlite+aiosqlite:///{_db.as_posix()}",
    "TOKEN_ENCRYPTION_KEYS": Fernet.generate_key().decode(),
    "GOOGLE_CLIENT_ID": "test-client.apps.googleusercontent.com",
    "GOOGLE_CLIENT_SECRET": "test-secret",
    "GOOGLE_ADS_DEVELOPER_TOKEN": "test-dev-token",
    "TIKTOK_APP_ID": "7000000000",
    "TIKTOK_APP_SECRET": "tiktok-secret",
    "APP_URL": "http://localhost:3000",
    "PUBLIC_API_URL": "http://localhost:3000/api",
    "CORS_ORIGINS": "http://localhost:3000",
    "GLOBAL_KILL_SWITCH": "true",
    "GOOGLE_ADS_MUTATIONS_ENABLED": "false",
    "TIKTOK_ADS_MUTATIONS_ENABLED": "false",
    "OPENAI_API_KEY": "",
    "SCRYPT_LOG_N": "10",
})

import pytest  # noqa: E402

from app.providers import DiscoveredAccount, ExecutionResult, ProviderError, TokenBundle  # noqa: E402
from app.snapshot import (  # noqa: E402
    AccountSnapshot,
    AdGroupInfo,
    AdInfo,
    CampaignInfo,
    ConversionActionInfo,
    DailyPoint,
    KeywordInfo,
    Metrics,
    SearchTermInfo,
)


def sample_snapshot(account_id: str = "1234567890", provider: str = "GOOGLE_ADS") -> AccountSnapshot:
    wasted = Metrics(impressions=300, clicks=12, cost=Decimal("60.00"), conversions=Decimal(0))
    return AccountSnapshot(
        provider=provider, account_id=account_id, account_name="Porto Imóveis", currency="BRL",
        period_start=date(2026, 9, 5), period_end=date(2026, 10, 4), enhanced_conversions_for_leads=False,
        conversion_actions=[ConversionActionInfo(conversion_action_id="77", name="Lead", status="ENABLED",
                                                 primary=True, conversions=Decimal(0))],
        campaigns=[CampaignInfo(
            campaign_id="111", name="Itahyê | Pesquisa", status="ENABLED", channel="SEARCH",
            bidding_strategy="MAXIMIZE_CONVERSIONS", daily_budget=Decimal("80.00"), search_network=True,
            search_partners=True, display_network=True, geo_target_type="PRESENCE_OR_INTEREST",
            end_date=date(2026, 10, 1),
            metrics=Metrics(impressions=4000, clicks=200, cost=Decimal("500.00"), conversions=Decimal(0)),
            ad_groups=[AdGroupInfo(
                ad_group_id="222", name="Casa Itahyê", status="ENABLED",
                keywords=[KeywordInfo(criterion_id="333", text="casa itahye", match_type="BROAD", status="ENABLED",
                                      quality_score=3, metrics=Metrics(clicks=20, cost=Decimal("40.00")))],
                ads=[AdInfo(ad_id="444", type="RESPONSIVE_SEARCH_AD", status="ENABLED", ad_strength="POOR",
                            headlines=["Casa com 4 vagas", "Casa Itahyê", "Agende visita"],
                            descriptions=["Casa com 5 vagas e 4 suítes.", "Fale conosco."])])],
        )],
        search_terms=[SearchTermInfo(term="casa itahye aluguel", campaign_id="111", metrics=wasted)],
        daily=[DailyPoint(day=date(2026, 10, 3), campaign_id="111",
                          metrics=Metrics(impressions=100, clicks=5, cost=Decimal("12.50")))],
    )


class FakeGoogle:
    provider = "GOOGLE_ADS"
    supports_pkce = True

    def __init__(self) -> None:
        self.executed: list = []
        self.validate_errors: list[str] = []
        self.execute_error: ProviderError | None = None
        self.refresh_error: ProviderError | None = None
        self.revoked: list[str] = []

    def authorization_url(self, *, state, redirect_uri, code_challenge):
        return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}&code_challenge={code_challenge}"

    async def exchange_code(self, *, code, redirect_uri, code_verifier):
        assert code_verifier, "PKCE verifier must be sent"
        if code == "no-refresh":
            return TokenBundle(access_token="ya29.access", expires_in=3600)
        return TokenBundle(access_token="ya29.access", refresh_token="1//refresh", expires_in=3600)

    async def refresh(self, refresh_token):
        if self.refresh_error:
            raise self.refresh_error
        return TokenBundle(access_token="ya29.renewed", expires_in=3600)

    async def revoke(self, token):
        self.revoked.append(token)

    async def discover_accounts(self, creds, token=None):
        return [DiscoveredAccount(external_id="9990001111", name="MCC ALN", is_manager=True, selectable=False),
                DiscoveredAccount(external_id="1234567890", name="Porto Imóveis", currency="BRL",
                                  login_customer_id="9990001111", is_test_account=True)]

    async def snapshot(self, creds, account, start, end):
        return sample_snapshot(account.external_id)

    async def validate(self, creds, account, kind, plan):
        return list(self.validate_errors)

    async def execute(self, creds, account, kind, plan):
        if self.execute_error:
            raise self.execute_error
        self.executed.append((kind, plan))
        if kind == "GOOGLE_SEARCH_CAMPAIGN":
            return ExecutionResult(status="CREATED_PAUSED", operations=10,
                                   resources={"campaign": f"customers/{account.external_id}/campaigns/555"})
        return ExecutionResult(status="APPLIED", operations=1, before={"changes": [{
            "action": "SET_NETWORKS", "campaign_id": "111", "search_partners": True, "display_network": True}]},
            resources={"resource_names": [f"customers/{account.external_id}/campaigns/111"]})

    async def reconcile(self, creds, account, campaign_ids):
        return {cid: "MISSING" for cid in campaign_ids}

    async def keyword_ideas(self, creds, account, **kwargs):
        return [{"text": "casa alto padrão", "avg_monthly_searches": 880, "competition": "HIGH"}]

    async def geo_suggest(self, creds, query, country="BR"):
        return [{"id": "1001773", "name": "São Paulo"}]


@pytest.fixture
def fake_google():
    from app.providers import override_gateway

    fake = FakeGoogle()
    override_gateway("GOOGLE_ADS", fake)
    yield fake
    override_gateway("GOOGLE_ADS", None)


@pytest.fixture(autouse=True)
def safe_defaults():
    """Every test starts with the production-safe switches."""
    from app import ratelimit
    from app.config import settings

    ratelimit.reset()
    settings.global_kill_switch = True
    settings.google_ads_mutations_enabled = False
    settings.tiktok_ads_mutations_enabled = False
    yield
    settings.global_kill_switch = True
    settings.google_ads_mutations_enabled = False
    settings.tiktok_ads_mutations_enabled = False


@pytest.fixture(scope="session", autouse=True)
async def database():
    from app.db import create_all

    await create_all()
    yield
