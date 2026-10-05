"""Google Ads API v25 gateway. The client library is synchronous, so every call runs in a worker thread."""

from __future__ import annotations

import logging
from contextvars import ContextVar
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import anyio
import httpx

from ..config import GOOGLE_ADS_API_VERSION, settings
from ..domain import (
    AddKeywords,
    AddNegatives,
    AnyPlan,
    Bidding,
    BiddingType,
    CreateConversionAction,
    GoogleChangePlan,
    GoogleSearchCampaignPlan,
    Money,
    PlanKind,
    RemoveCampaign,
    RemoveNegatives,
    SetBidding,
    SetBudget,
    SetCampaignStatus,
    SetEndDate,
    SetGeoTargetType,
    SetKeywordStatus,
    SetNetworks,
    UpdateResponsiveSearchAd,
)
from ..snapshot import (
    AccountSnapshot,
    AdGroupInfo,
    AdInfo,
    AssetInfo,
    CampaignInfo,
    ConversionActionInfo,
    DailyPoint,
    KeywordInfo,
    Metrics,
    NegativeInfo,
    SearchTermInfo,
)
from .base import AccountRef, Credentials, DiscoveredAccount, ExecutionResult, ProviderError, TokenBundle

log = logging.getLogger("aln.google_ads")

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
SCOPE = "https://www.googleapis.com/auth/adwords"
NO_END_DATE = "2037-12-30 23:59:59"
RETRYABLE_ERRORS = {"quota_error", "internal_error"}
RECONNECT_ERRORS = {"authentication_error"}

# Requests made in the current task; the service layer persists them for quota tracking.
request_counter: ContextVar[list[int] | None] = ContextVar("google_request_counter", default=None)


def _count(n: int = 1) -> None:
    counter = request_counter.get()
    if counter is not None:
        counter[0] += n


def to_micros(value: Money | Decimal) -> int:
    amount = value.amount if isinstance(value, Money) else value
    return int((amount * 1_000_000).to_integral_value())


def from_micros(value: int | float | None) -> Decimal:
    return (Decimal(int(value or 0)) / 1_000_000).quantize(Decimal("0.01"))


def gaql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        parsed = datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    return None if parsed.year >= 2037 else parsed


def _metrics(row: Any) -> Metrics:
    m = row.metrics
    return Metrics(
        impressions=int(m.impressions),
        clicks=int(m.clicks),
        cost=from_micros(m.cost_micros),
        conversions=Decimal(str(round(m.conversions, 2))),
        conversion_value=Decimal(str(round(m.conversions_value, 2))),
    )


def translate_error(error: BaseException) -> ProviderError:
    from google.ads.googleads.errors import GoogleAdsException
    from google.auth.exceptions import RefreshError

    if isinstance(error, ProviderError):
        return error
    if isinstance(error, GoogleAdsException):
        details: list[str] = []
        retryable = reconnect = False
        for item in error.failure.errors:
            which = type(item.error_code).pb(item.error_code).WhichOneof("error_code") or "unknown"
            code = getattr(item.error_code, which, None)
            code_name = getattr(code, "name", str(code))
            path = ".".join(e.field_name for e in item.location.field_path_elements) if item.location else ""
            details.append(f"{item.message} [{which}.{code_name}{' em ' + path if path else ''}]")
            retryable |= which in RETRYABLE_ERRORS
            reconnect |= which in RECONNECT_ERRORS
            if code_name == "DEVELOPER_TOKEN_NOT_APPROVED":
                details.append("O Developer Token ainda está em modo teste: só funciona com contas de teste.")
        return ProviderError(
            "O Google Ads recusou a operação.", retryable=retryable, needs_reconnect=reconnect, details=details[:25]
        )
    if isinstance(error, RefreshError):
        return ProviderError(
            "A autorização do Google expirou ou foi revogada. Reconecte a conta.", needs_reconnect=True
        )
    try:
        import grpc

        if isinstance(error, grpc.RpcError):
            status = error.code()  # type: ignore[attr-defined]
            transient = {
                grpc.StatusCode.UNAVAILABLE,
                grpc.StatusCode.DEADLINE_EXCEEDED,
                grpc.StatusCode.RESOURCE_EXHAUSTED,
                grpc.StatusCode.INTERNAL,
            }
            return ProviderError(
                f"Falha de comunicação com o Google Ads ({status.name}).", retryable=status in transient
            )
    except ImportError:  # pragma: no cover
        pass
    log.exception("google_ads.unexpected_error")
    return ProviderError("Erro inesperado ao falar com o Google Ads.", retryable=True)


class GoogleAdsGateway:
    provider = "GOOGLE_ADS"
    supports_pkce = True

    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        self._http = http

    # ------------------------------------------------------------------ OAuth

    def authorization_url(self, *, state: str, redirect_uri: str, code_challenge: str | None) -> str:
        query = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
        if code_challenge:
            query |= {"code_challenge": code_challenge, "code_challenge_method": "S256"}
        return f"{AUTH_URL}?{urlencode(query)}"

    async def _post(self, url: str, data: dict[str, Any]) -> httpx.Response:
        if self._http:
            return await self._http.post(url, data=data)
        async with httpx.AsyncClient(timeout=20) as client:
            return await client.post(url, data=data)

    async def exchange_code(self, *, code: str, redirect_uri: str, code_verifier: str | None) -> TokenBundle:
        data = {
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        if code_verifier:
            data["code_verifier"] = code_verifier
        response = await self._post(TOKEN_URL, data)
        if response.is_error:
            raise ProviderError("O Google recusou a troca do código de autorização.")
        body = response.json()
        return TokenBundle(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_in=int(body.get("expires_in", 3600)),
            scopes=body.get("scope"),
        )

    async def refresh(self, refresh_token: str) -> TokenBundle:
        response = await self._post(
            TOKEN_URL,
            {
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
            },
        )
        if response.status_code in {400, 401}:
            body = response.json() if response.content else {}
            if body.get("error") in {"invalid_grant", "unauthorized_client", "invalid_client"}:
                raise ProviderError(
                    "A autorização do Google foi revogada ou expirou. Reconecte a conta.", needs_reconnect=True
                )
        if response.is_error:
            raise ProviderError("Não foi possível renovar o acesso ao Google agora.", retryable=True)
        body = response.json()
        return TokenBundle(
            access_token=body["access_token"], expires_in=int(body.get("expires_in", 3600)), scopes=body.get("scope")
        )

    async def revoke(self, token: str) -> None:
        response = await self._post(REVOKE_URL, {"token": token})
        if response.is_error and response.status_code != 400:  # 400 = already invalid
            raise ProviderError("O Google não confirmou a revogação. Tente novamente.", retryable=True)

    # ------------------------------------------------------------------ client

    def client(self, creds: Credentials, login_customer_id: str | None):  # pragma: no cover - needs credentials
        from google.ads.googleads.client import GoogleAdsClient
        from google.oauth2.credentials import Credentials as OAuthCredentials

        if not settings.google_ads_developer_token:
            raise ProviderError("GOOGLE_ADS_DEVELOPER_TOKEN não configurado.")
        oauth = OAuthCredentials(
            token=creds.access_token,
            refresh_token=creds.refresh_token,
            token_uri=TOKEN_URL,
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            scopes=[SCOPE],
        )
        return GoogleAdsClient(
            credentials=oauth,
            developer_token=settings.google_ads_developer_token,
            login_customer_id=login_customer_id,
            version=GOOGLE_ADS_API_VERSION,
            use_proto_plus=True,
        )

    async def _run(self, fn, *args):
        try:
            return await anyio.to_thread.run_sync(fn, *args)
        except Exception as error:  # noqa: BLE001 - translated for the caller
            raise translate_error(error) from error

    @staticmethod
    def search(client, customer_id: str, query: str) -> list[Any]:
        _count()
        service = client.get_service("GoogleAdsService")
        rows: list[Any] = []
        for batch in service.search_stream(customer_id=customer_id, query=" ".join(query.split())):
            rows.extend(batch.results)
        return rows

    # ------------------------------------------------------------------ accounts

    async def discover_accounts(self, creds: Credentials, token: TokenBundle | None = None) -> list[DiscoveredAccount]:
        return await self._run(self._discover_sync, creds)

    def _discover_sync(self, creds: Credentials) -> list[DiscoveredAccount]:
        client = self.client(creds, None)
        _count()
        roots = [
            name.split("/")[-1]
            for name in client.get_service("CustomerService").list_accessible_customers().resource_names
        ][:50]
        found: dict[str, DiscoveredAccount] = {}
        for root in roots:
            try:
                rows = self.search(
                    self.client(creds, root),
                    root,
                    """
                    SELECT customer_client.id, customer_client.descriptive_name, customer_client.currency_code,
                           customer_client.time_zone, customer_client.manager, customer_client.test_account,
                           customer_client.level, customer_client.status
                    FROM customer_client WHERE customer_client.level <= 1""",
                )
            except Exception as error:  # noqa: BLE001 - a cancelled root must not hide the others
                log.warning("google_ads.discover_root_failed", extra={"root": root, "error": str(error)[:200]})
                continue
            root_name = next((r.customer_client.descriptive_name for r in rows if r.customer_client.level == 0), None)
            for row in rows:
                cc = row.customer_client
                external_id = str(cc.id)
                if cc.status.name not in {"ENABLED", "UNSPECIFIED"} or external_id in found:
                    continue
                found[external_id] = DiscoveredAccount(
                    external_id=external_id,
                    name=cc.descriptive_name or f"Conta {external_id}",
                    currency=cc.currency_code or None,
                    time_zone=cc.time_zone or None,
                    login_customer_id=root if root != external_id else None,
                    is_manager=bool(cc.manager),
                    is_test_account=bool(cc.test_account),
                    selectable=not cc.manager,
                    parent_name=root_name if root != external_id else None,
                )
        return sorted(found.values(), key=lambda a: (not a.selectable, a.name.lower()))

    # ------------------------------------------------------------------ reads

    async def snapshot(self, creds: Credentials, account: AccountRef, start: date, end: date) -> AccountSnapshot:
        return await self._run(self._snapshot_sync, creds, account, start, end)

    def _snapshot_sync(self, creds: Credentials, account: AccountRef, start: date, end: date) -> AccountSnapshot:
        client = self.client(creds, account.login_customer_id)
        cid = account.external_id
        between = f"segments.date BETWEEN '{start.isoformat()}' AND '{end.isoformat()}'"
        q = lambda query: self.search(client, cid, query)  # noqa: E731

        customer = q("""SELECT customer.descriptive_name, customer.currency_code,
                        customer.conversion_tracking_setting.enhanced_conversions_for_leads_enabled FROM customer""")
        snapshot = AccountSnapshot(provider=self.provider, account_id=cid, period_start=start, period_end=end)
        if customer:
            c = customer[0].customer
            snapshot.account_name = c.descriptive_name
            snapshot.currency = c.currency_code
            snapshot.enhanced_conversions_for_leads = bool(
                c.conversion_tracking_setting.enhanced_conversions_for_leads_enabled
            )

        campaigns: dict[str, CampaignInfo] = {}
        for row in q("""
            SELECT campaign.id, campaign.name, campaign.status, campaign.advertising_channel_type,
                   campaign.bidding_strategy_type, campaign.start_date_time, campaign.end_date_time,
                   campaign.network_settings.target_google_search, campaign.network_settings.target_search_network,
                   campaign.network_settings.target_content_network,
                   campaign.geo_target_type_setting.positive_geo_target_type,
                   campaign_budget.id, campaign_budget.amount_micros
            FROM campaign WHERE campaign.status != 'REMOVED'"""):
            c, ns = row.campaign, row.campaign.network_settings
            campaigns[str(c.id)] = CampaignInfo(
                campaign_id=str(c.id),
                name=c.name,
                status=c.status.name,
                channel=c.advertising_channel_type.name,
                bidding_strategy=c.bidding_strategy_type.name,
                daily_budget=from_micros(row.campaign_budget.amount_micros),
                budget_id=str(row.campaign_budget.id) if row.campaign_budget.id else None,
                start_date=_date(c.start_date_time),
                end_date=_date(c.end_date_time),
                search_network=bool(ns.target_google_search),
                search_partners=bool(ns.target_search_network),
                display_network=bool(ns.target_content_network),
                geo_target_type=c.geo_target_type_setting.positive_geo_target_type.name,
            )

        for row in q(f"""SELECT campaign.id, metrics.impressions, metrics.clicks, metrics.cost_micros,
                         metrics.conversions, metrics.conversions_value FROM campaign
                         WHERE campaign.status != 'REMOVED' AND {between}"""):
            if (campaign := campaigns.get(str(row.campaign.id))) is not None:
                campaign.metrics = _metrics(row)

        for row in q(f"""SELECT campaign.id, segments.date, metrics.impressions, metrics.clicks, metrics.cost_micros,
                         metrics.conversions, metrics.conversions_value FROM campaign WHERE {between}"""):
            snapshot.daily.append(
                DailyPoint(
                    day=_date(row.segments.date) or start, campaign_id=str(row.campaign.id), metrics=_metrics(row)
                )
            )

        groups: dict[str, AdGroupInfo] = {}
        group_campaign: dict[str, str] = {}
        for row in q("""SELECT campaign.id, ad_group.id, ad_group.name, ad_group.status FROM ad_group
                        WHERE ad_group.status != 'REMOVED' AND campaign.status != 'REMOVED'"""):
            gid = str(row.ad_group.id)
            groups[gid] = AdGroupInfo(ad_group_id=gid, name=row.ad_group.name, status=row.ad_group.status.name)
            group_campaign[gid] = str(row.campaign.id)
        for row in q(f"""SELECT ad_group.id, metrics.impressions, metrics.clicks, metrics.cost_micros,
                         metrics.conversions, metrics.conversions_value FROM ad_group
                         WHERE ad_group.status != 'REMOVED' AND {between}"""):
            if (group := groups.get(str(row.ad_group.id))) is not None:
                group.metrics = _metrics(row)

        keyword_metrics: dict[tuple[str, str], Metrics] = {}
        for row in q(f"""SELECT ad_group.id, ad_group_criterion.criterion_id, metrics.impressions, metrics.clicks,
                         metrics.cost_micros, metrics.conversions, metrics.conversions_value FROM keyword_view
                         WHERE {between}"""):
            keyword_metrics[(str(row.ad_group.id), str(row.ad_group_criterion.criterion_id))] = _metrics(row)
        for row in q("""SELECT campaign.id, ad_group.id, ad_group_criterion.criterion_id, ad_group_criterion.negative,
                        ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type,
                        ad_group_criterion.status, ad_group_criterion.quality_info.quality_score
                        FROM ad_group_criterion WHERE ad_group_criterion.type = 'KEYWORD'
                        AND ad_group_criterion.status != 'REMOVED' AND campaign.status != 'REMOVED'"""):
            crit, gid = row.ad_group_criterion, str(row.ad_group.id)
            if crit.negative:
                if (campaign := campaigns.get(str(row.campaign.id))) is not None:
                    campaign.negatives.append(
                        NegativeInfo(
                            criterion_id=str(crit.criterion_id),
                            text=crit.keyword.text,
                            match_type=crit.keyword.match_type.name,
                            source="ad_group",
                        )
                    )
                continue
            if (group := groups.get(gid)) is not None:
                group.keywords.append(
                    KeywordInfo(
                        criterion_id=str(crit.criterion_id),
                        text=crit.keyword.text,
                        match_type=crit.keyword.match_type.name,
                        status=crit.status.name,
                        quality_score=crit.quality_info.quality_score or None,
                        metrics=keyword_metrics.get((gid, str(crit.criterion_id)), Metrics()),
                    )
                )

        ad_metrics: dict[str, Metrics] = {}
        for row in q(f"""SELECT ad_group_ad.ad.id, metrics.impressions, metrics.clicks, metrics.cost_micros,
                         metrics.conversions, metrics.conversions_value FROM ad_group_ad WHERE {between}"""):
            ad_metrics[str(row.ad_group_ad.ad.id)] = _metrics(row)
        for row in q("""SELECT ad_group.id, ad_group_ad.ad.id, ad_group_ad.ad.type, ad_group_ad.status,
                        ad_group_ad.ad_strength, ad_group_ad.ad.final_urls,
                        ad_group_ad.ad.responsive_search_ad.headlines,
                        ad_group_ad.ad.responsive_search_ad.descriptions
                        FROM ad_group_ad WHERE ad_group_ad.status != 'REMOVED' AND campaign.status != 'REMOVED'"""):
            aga, ad = row.ad_group_ad, row.ad_group_ad.ad
            if (group := groups.get(str(row.ad_group.id))) is not None:
                group.ads.append(
                    AdInfo(
                        ad_id=str(ad.id),
                        type=ad.type_.name,
                        status=aga.status.name,
                        ad_strength=aga.ad_strength.name,
                        headlines=[h.text for h in ad.responsive_search_ad.headlines],
                        descriptions=[d.text for d in ad.responsive_search_ad.descriptions],
                        final_urls=list(ad.final_urls),
                        metrics=ad_metrics.get(str(ad.id), Metrics()),
                    )
                )
        for gid, group in groups.items():
            if (campaign := campaigns.get(group_campaign[gid])) is not None:
                campaign.ad_groups.append(group)

        for row in q("""SELECT campaign.id, campaign_criterion.criterion_id, campaign_criterion.keyword.text,
                        campaign_criterion.keyword.match_type FROM campaign_criterion
                        WHERE campaign_criterion.negative = TRUE AND campaign_criterion.type = 'KEYWORD'
                        AND campaign.status != 'REMOVED'"""):
            if (campaign := campaigns.get(str(row.campaign.id))) is not None:
                cc = row.campaign_criterion
                campaign.negatives.append(
                    NegativeInfo(
                        criterion_id=str(cc.criterion_id), text=cc.keyword.text, match_type=cc.keyword.match_type.name
                    )
                )
        for row in q("""SELECT campaign.id, shared_set.name FROM campaign_shared_set
                        WHERE shared_set.type = 'NEGATIVE_KEYWORDS' AND campaign_shared_set.status = 'ENABLED'"""):
            if (campaign := campaigns.get(str(row.campaign.id))) is not None:
                campaign.negatives.append(
                    NegativeInfo(text=f"Lista: {row.shared_set.name}", match_type="LIST", source="shared_list")
                )
        for row in q("""SELECT campaign.id, campaign_criterion.location.geo_target_constant FROM campaign_criterion
                        WHERE campaign_criterion.type = 'LOCATION' AND campaign_criterion.negative = FALSE
                        AND campaign.status != 'REMOVED'"""):
            if (campaign := campaigns.get(str(row.campaign.id))) is not None:
                campaign.geo_targets.append(row.campaign_criterion.location.geo_target_constant.split("/")[-1])
        for row in q("""SELECT campaign.id, campaign_asset.field_type, asset.sitelink_asset.link_text,
                        asset.callout_asset.callout_text, asset.structured_snippet_asset.values
                        FROM campaign_asset WHERE campaign_asset.status != 'REMOVED'
                        AND campaign.status != 'REMOVED'"""):
            if (campaign := campaigns.get(str(row.campaign.id))) is None:
                continue
            kind = row.campaign_asset.field_type.name
            asset = row.asset
            text = (
                asset.sitelink_asset.link_text
                or asset.callout_asset.callout_text
                or ", ".join(asset.structured_snippet_asset.values)
            )
            campaign.assets.append(AssetInfo(type=kind, text=text))

        conversions_by_action: dict[str, Decimal] = {}
        for row in q(f"""SELECT segments.conversion_action, metrics.all_conversions FROM customer WHERE {between}"""):
            key = row.segments.conversion_action.split("/")[-1]
            conversions_by_action[key] = conversions_by_action.get(key, Decimal(0)) + Decimal(
                str(round(row.metrics.all_conversions, 2))
            )
        for row in q("""SELECT conversion_action.id, conversion_action.name, conversion_action.status,
                        conversion_action.category, conversion_action.primary_for_goal FROM conversion_action
                        WHERE conversion_action.status != 'REMOVED'"""):
            ca = row.conversion_action
            snapshot.conversion_actions.append(
                ConversionActionInfo(
                    conversion_action_id=str(ca.id),
                    name=ca.name,
                    status=ca.status.name,
                    category=ca.category.name,
                    primary=bool(ca.primary_for_goal),
                    conversions=conversions_by_action.get(str(ca.id), Decimal(0)),
                )
            )

        for row in q(f"""SELECT search_term_view.search_term, search_term_view.status, campaign.id, ad_group.id,
                         metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions,
                         metrics.conversions_value FROM search_term_view WHERE {between} AND metrics.clicks > 0
                         ORDER BY metrics.cost_micros DESC LIMIT 500"""):
            snapshot.search_terms.append(
                SearchTermInfo(
                    term=row.search_term_view.search_term,
                    status=row.search_term_view.status.name,
                    campaign_id=str(row.campaign.id),
                    ad_group_id=str(row.ad_group.id),
                    metrics=_metrics(row),
                )
            )

        snapshot.campaigns = sorted(campaigns.values(), key=lambda c: (c.status != "ENABLED", -c.metrics.cost))
        return snapshot

    async def keyword_ideas(
        self,
        creds: Credentials,
        account: AccountRef,
        *,
        seeds: list[str],
        url: str | None,
        geo_ids: list[str],
        language_id: str = "1014",
    ) -> list[dict[str, Any]]:
        return await self._run(self._keyword_ideas_sync, creds, account, seeds, url, geo_ids, language_id)

    def _keyword_ideas_sync(self, creds, account, seeds, url, geo_ids, language_id) -> list[dict[str, Any]]:
        client = self.client(creds, account.login_customer_id)
        request = client.get_type("GenerateKeywordIdeasRequest")
        request.customer_id = account.external_id
        request.language = f"languageConstants/{language_id}"
        request.geo_target_constants.extend([f"geoTargetConstants/{g}" for g in geo_ids])
        request.include_adult_keywords = False
        request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
        request.page_size = 100
        if seeds and url:
            request.keyword_and_url_seed.url = url
            request.keyword_and_url_seed.keywords.extend(seeds[:20])
        elif seeds:
            request.keyword_seed.keywords.extend(seeds[:20])
        elif url:
            request.url_seed.url = url
        else:
            raise ProviderError("Informe palavras-semente ou uma URL.")
        _count()
        ideas = []
        for idea in client.get_service("KeywordPlanIdeaService").generate_keyword_ideas(request=request):
            metrics = idea.keyword_idea_metrics
            ideas.append(
                {
                    "text": idea.text,
                    "avg_monthly_searches": int(metrics.avg_monthly_searches or 0),
                    "competition": metrics.competition.name,
                    "low_top_of_page_bid": str(from_micros(metrics.low_top_of_page_bid_micros)),
                    "high_top_of_page_bid": str(from_micros(metrics.high_top_of_page_bid_micros)),
                }
            )
            if len(ideas) >= 100:
                break
        return sorted(ideas, key=lambda i: -i["avg_monthly_searches"])

    async def geo_suggest(self, creds: Credentials, query: str, country: str = "BR") -> list[dict[str, Any]]:
        return await self._run(self._geo_suggest_sync, creds, query, country)

    def _geo_suggest_sync(self, creds, query, country) -> list[dict[str, Any]]:
        client = self.client(creds, None)
        request = client.get_type("SuggestGeoTargetConstantsRequest")
        request.locale = "pt"
        request.country_code = country
        request.location_names.names.append(query)
        _count()
        response = client.get_service("GeoTargetConstantService").suggest_geo_target_constants(request=request)
        return [
            {
                "id": str(s.geo_target_constant.id),
                "name": s.geo_target_constant.name,
                "canonical_name": s.geo_target_constant.canonical_name,
                "type": s.geo_target_constant.target_type,
                "reach": int(s.reach or 0),
            }
            for s in response.geo_target_constant_suggestions
        ][:15]

    async def upload_click_conversion(
        self,
        creds: Credentials,
        account: AccountRef,
        *,
        conversion_action_id: str,
        gclid: str,
        occurred_at: datetime,
        value: Decimal | None,
        currency: str | None,
    ) -> dict[str, Any]:
        return await self._run(
            self._upload_sync, creds, account, conversion_action_id, gclid, occurred_at, value, currency
        )

    def _upload_sync(self, creds, account, conversion_action_id, gclid, occurred_at, value, currency):
        client = self.client(creds, account.login_customer_id)
        conversion = client.get_type("ClickConversion")
        conversion.conversion_action = f"customers/{account.external_id}/conversionActions/{conversion_action_id}"
        conversion.gclid = gclid
        conversion.conversion_date_time = occurred_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S+00:00")
        if value is not None:
            conversion.conversion_value = float(value)
            conversion.currency_code = currency or account.currency or "BRL"
        request = client.get_type("UploadClickConversionsRequest")
        request.customer_id = account.external_id
        request.conversions.append(conversion)
        request.partial_failure = True
        _count()
        response = client.get_service("ConversionUploadService").upload_click_conversions(request=request)
        if response.partial_failure_error and response.partial_failure_error.code:
            raise ProviderError(
                "O Google recusou a conversão offline.", details=[response.partial_failure_error.message[:300]]
            )
        return {"uploaded": 1}

    async def reconcile(self, creds: Credentials, account: AccountRef, campaign_ids: list[str]) -> dict[str, str]:
        if not campaign_ids:
            return {}
        return await self._run(self._reconcile_sync, creds, account, campaign_ids)

    def _reconcile_sync(self, creds, account, campaign_ids) -> dict[str, str]:
        client = self.client(creds, account.login_customer_id)
        ids = ", ".join(str(int(i)) for i in campaign_ids[:500])
        rows = self.search(
            client,
            account.external_id,
            f"SELECT campaign.id, campaign.status FROM campaign WHERE campaign.id IN ({ids})",
        )
        found = {str(r.campaign.id): r.campaign.status.name for r in rows}
        return {cid: found.get(cid, "MISSING") for cid in campaign_ids}

    # ------------------------------------------------------------------ writes

    async def validate(self, creds: Credentials, account: AccountRef, kind: PlanKind, plan: AnyPlan) -> list[str]:
        try:
            await self._run(self._mutate_sync, creds, account, kind, plan, True)
        except ProviderError as error:
            if error.retryable or error.needs_reconnect:
                raise
            return error.details or [error.message]
        return []

    async def execute(self, creds: Credentials, account: AccountRef, kind: PlanKind, plan: AnyPlan) -> ExecutionResult:
        return await self._run(self._mutate_sync, creds, account, kind, plan, False)

    def _mutate_sync(
        self, creds, account: AccountRef, kind: PlanKind, plan: AnyPlan, validate_only: bool
    ) -> ExecutionResult:
        client = self.client(creds, account.login_customer_id)
        cid = account.external_id
        before: dict[str, Any] = {}
        if isinstance(plan, GoogleSearchCampaignPlan):
            if not validate_only and (existing := self._campaign_by_name(client, cid, plan.name)):
                return ExecutionResult(status="ALREADY_EXISTS", resources={"campaign": existing})
            builder = OperationBuilder(client, cid)
            builder.create_search_campaign(plan, today=date.today())
        elif isinstance(plan, GoogleChangePlan):
            builder = OperationBuilder(client, cid)
            before = {"changes": [self._before(client, cid, change) for change in plan.changes]}
            for change in plan.changes:
                builder.apply_change(change, before)
        else:
            raise ProviderError("Plano não pertence ao Google Ads.")

        _count(len(builder.operations))
        response = client.get_service("GoogleAdsService").mutate(
            customer_id=cid, mutate_operations=builder.operations, validate_only=validate_only
        )
        if validate_only:
            return ExecutionResult(status="VALID", operations=len(builder.operations))
        names = [_response_resource_name(r) for r in response.mutate_operation_responses]
        resources: dict[str, Any] = {"resource_names": names}
        campaign = next((n for n in names if "/campaigns/" in n), None)
        if campaign:
            resources["campaign"] = campaign
        conversion = next((n for n in names if "/conversionActions/" in n), None)
        if conversion:
            resources["conversion_action"] = conversion
            resources["tag_snippets"] = self._tag_snippets(client, cid, conversion)
        status = "CREATED_PAUSED" if isinstance(plan, GoogleSearchCampaignPlan) else "APPLIED"
        return ExecutionResult(
            status=status,
            resources=resources,
            before=before,
            after={"resource_names": names},
            operations=len(builder.operations),
        )

    def _campaign_by_name(self, client, cid: str, name: str) -> str | None:
        rows = self.search(
            client,
            cid,
            f"SELECT campaign.resource_name FROM campaign "
            f"WHERE campaign.name = {gaql_string(name)} AND campaign.status != 'REMOVED'",
        )
        return rows[0].campaign.resource_name if rows else None

    def _tag_snippets(self, client, cid: str, resource_name: str) -> list[dict[str, str]]:
        rows = self.search(
            client,
            cid,
            f"SELECT conversion_action.tag_snippets FROM conversion_action "
            f"WHERE conversion_action.resource_name = {gaql_string(resource_name)}",
        )
        if not rows:
            return []
        return [
            {
                "type": s.type_.name,
                "page_format": s.page_format.name,
                "global_site_tag": s.global_site_tag,
                "event_snippet": s.event_snippet,
            }
            for s in rows[0].conversion_action.tag_snippets
        ]

    def _before(self, client, cid: str, change: Any) -> dict[str, Any]:
        """Reads the current state of everything a change touches, for the diff and for "Reverter"."""
        if isinstance(
            change,
            SetNetworks | SetBidding | SetEndDate | SetGeoTargetType | SetCampaignStatus | SetBudget | RemoveCampaign,
        ):
            rows = self.search(
                client,
                cid,
                f"""
                SELECT campaign.id, campaign.name, campaign.status, campaign.end_date_time,
                       campaign.network_settings.target_search_network,
                       campaign.network_settings.target_content_network,
                       campaign.geo_target_type_setting.positive_geo_target_type, campaign.bidding_strategy_type,
                       campaign.target_spend.cpc_bid_ceiling_micros, campaign.maximize_conversions.target_cpa_micros,
                       campaign_budget.resource_name, campaign_budget.amount_micros,
                       campaign_budget.explicitly_shared
                FROM campaign WHERE campaign.id = {int(change.campaign_id)}""",
            )
            if not rows:
                raise ProviderError(f"Campanha {change.campaign_id} não encontrada nesta conta.")
            c, b = rows[0].campaign, rows[0].campaign_budget
            return {
                "action": change.action,
                "campaign_id": change.campaign_id,
                "campaign_name": c.name,
                "status": c.status.name,
                "end_date": c.end_date_time[:10] if _date(c.end_date_time) else None,
                "search_partners": bool(c.network_settings.target_search_network),
                "display_network": bool(c.network_settings.target_content_network),
                "geo_target_type": c.geo_target_type_setting.positive_geo_target_type.name,
                "bidding_strategy": c.bidding_strategy_type.name,
                "cpc_ceiling": str(from_micros(c.target_spend.cpc_bid_ceiling_micros))
                if c.target_spend.cpc_bid_ceiling_micros
                else None,
                "target_cpa": str(from_micros(c.maximize_conversions.target_cpa_micros))
                if c.maximize_conversions.target_cpa_micros
                else None,
                "budget_resource": b.resource_name,
                "daily_budget": str(from_micros(b.amount_micros)),
                "budget_shared": bool(b.explicitly_shared),
            }
        if isinstance(change, RemoveNegatives):
            ids = ", ".join(str(int(i)) for i in change.criterion_ids)
            rows = self.search(
                client,
                cid,
                f"""
                SELECT campaign_criterion.criterion_id, campaign_criterion.keyword.text,
                       campaign_criterion.keyword.match_type FROM campaign_criterion
                WHERE campaign.id = {int(change.campaign_id)} AND campaign_criterion.criterion_id IN ({ids})""",
            )
            return {
                "action": change.action,
                "keywords": [
                    {
                        "criterion_id": str(r.campaign_criterion.criterion_id),
                        "text": r.campaign_criterion.keyword.text,
                        "match_type": r.campaign_criterion.keyword.match_type.name,
                    }
                    for r in rows
                ],
            }
        if isinstance(change, SetKeywordStatus):
            rows = self.search(
                client,
                cid,
                f"""
                SELECT ad_group_criterion.status, ad_group_criterion.keyword.text,
                       ad_group_criterion.keyword.match_type FROM ad_group_criterion
                WHERE ad_group.id = {int(change.ad_group_id)}
                AND ad_group_criterion.criterion_id = {int(change.criterion_id)}""",
            )
            if not rows:
                raise ProviderError(f"Palavra-chave {change.criterion_id} não encontrada.")
            crit = rows[0].ad_group_criterion
            return {
                "action": change.action,
                "status": crit.status.name,
                "text": crit.keyword.text,
                "match_type": crit.keyword.match_type.name,
            }
        if isinstance(change, UpdateResponsiveSearchAd):
            rows = self.search(
                client,
                cid,
                f"""
                SELECT ad_group_ad.ad.responsive_search_ad.headlines, ad_group_ad.ad.responsive_search_ad.descriptions
                FROM ad_group_ad WHERE ad_group_ad.ad.id = {int(change.ad_id)}""",
            )
            if not rows:
                raise ProviderError(f"Anúncio {change.ad_id} não encontrado.")
            rsa = rows[0].ad_group_ad.ad.responsive_search_ad
            return {
                "action": change.action,
                "headlines": [h.text for h in rsa.headlines],
                "descriptions": [d.text for d in rsa.descriptions],
            }
        return {"action": change.action}


def operations_per_change(change: Any) -> int:
    """How many mutate operations a change produces, in order. Used to map results back to changes."""
    if isinstance(change, AddNegatives | AddKeywords):
        return len(change.keywords)
    if isinstance(change, RemoveNegatives):
        return len(change.criterion_ids)
    return 1


def _response_resource_name(response: Any) -> str:
    which = type(response).pb(response).WhichOneof("response")
    return getattr(response, which).resource_name if which else ""


def _set_present(message: Any, field: str) -> None:
    """Marks an empty sub-message (e.g. manual_cpc) as set, which selects that oneof member."""
    getattr(type(message).pb(message), field).SetInParent()


class OperationBuilder:
    """Builds GoogleAdsService.Mutate operations. Pure: no network, so it is unit-tested directly."""

    def __init__(self, client: Any, customer_id: str) -> None:
        self.client = client
        self.cid = customer_id
        self.operations: list[Any] = []
        self._temp = 0

    def _temp_id(self) -> int:
        self._temp -= 1
        return self._temp

    def _rn(self, collection: str, identifier: int | str) -> str:
        return f"customers/{self.cid}/{collection}/{identifier}"

    def _op(self) -> Any:
        operation = self.client.get_type("MutateOperation")
        self.operations.append(operation)
        return operation

    def _mask(self, operation: Any, paths: list[str]) -> None:
        from google.protobuf import field_mask_pb2

        self.client.copy_from(operation.update_mask, field_mask_pb2.FieldMask(paths=paths))

    def _bidding(self, campaign: Any, bidding: Bidding) -> list[str]:
        if bidding.type == BiddingType.MAXIMIZE_CLICKS:
            if bidding.cpc_ceiling:
                campaign.target_spend.cpc_bid_ceiling_micros = to_micros(bidding.cpc_ceiling)
                return ["target_spend.cpc_bid_ceiling_micros"]
            _set_present(campaign, "target_spend")
            return ["target_spend"]
        if bidding.type == BiddingType.MAXIMIZE_CONVERSIONS:
            if bidding.target_cpa:
                campaign.maximize_conversions.target_cpa_micros = to_micros(bidding.target_cpa)
                return ["maximize_conversions.target_cpa_micros"]
            _set_present(campaign, "maximize_conversions")
            return ["maximize_conversions"]
        _set_present(campaign, "manual_cpc")
        return ["manual_cpc"]

    def _keyword_criterion(self, criterion: Any, text: str, match: str) -> None:
        criterion.keyword.text = text
        criterion.keyword.match_type = self.client.enums.KeywordMatchTypeEnum[match]

    def create_search_campaign(self, plan: GoogleSearchCampaignPlan, today: date) -> None:
        enums = self.client.enums
        budget_rn = self._rn("campaignBudgets", self._temp_id())
        budget = self._op().campaign_budget_operation.create
        budget.resource_name = budget_rn
        budget.name = f"{plan.name} | orçamento"
        budget.amount_micros = to_micros(plan.daily_budget)
        budget.delivery_method = enums.BudgetDeliveryMethodEnum.STANDARD
        budget.explicitly_shared = False

        campaign_rn = self._rn("campaigns", self._temp_id())
        campaign = self._op().campaign_operation.create
        campaign.resource_name = campaign_rn
        campaign.name = plan.name
        campaign.status = enums.CampaignStatusEnum.PAUSED
        campaign.advertising_channel_type = enums.AdvertisingChannelTypeEnum.SEARCH
        campaign.campaign_budget = budget_rn
        campaign.network_settings.target_google_search = True
        campaign.network_settings.target_search_network = False
        campaign.network_settings.target_content_network = False
        campaign.geo_target_type_setting.positive_geo_target_type = enums.PositiveGeoTargetTypeEnum.PRESENCE
        campaign.contains_eu_political_advertising = (
            enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
        )
        if plan.start_date > today:
            campaign.start_date_time = f"{plan.start_date.isoformat()} 00:00:00"
        if plan.end_date:
            campaign.end_date_time = f"{plan.end_date.isoformat()} 23:59:59"
        self._bidding(campaign, plan.bidding)

        for geo in plan.geo_target_ids:
            criterion = self._op().campaign_criterion_operation.create
            criterion.campaign = campaign_rn
            criterion.location.geo_target_constant = f"geoTargetConstants/{geo}"
        for language in plan.language_ids:
            criterion = self._op().campaign_criterion_operation.create
            criterion.campaign = campaign_rn
            criterion.language.language_constant = f"languageConstants/{language}"
        for negative in plan.campaign_negatives:
            criterion = self._op().campaign_criterion_operation.create
            criterion.campaign = campaign_rn
            criterion.negative = True
            self._keyword_criterion(criterion, negative.text, negative.match_type.value)

        def link_asset(field_type: Any) -> Any:
            asset_rn = self._rn("assets", self._temp_id())
            asset = self._op().asset_operation.create
            asset.resource_name = asset_rn
            link = self.client.get_type("MutateOperation")
            link.campaign_asset_operation.create.campaign = campaign_rn
            link.campaign_asset_operation.create.asset = asset_rn
            link.campaign_asset_operation.create.field_type = field_type
            return asset, link

        links: list[Any] = []
        for sitelink in plan.sitelinks:
            asset, link = link_asset(enums.AssetFieldTypeEnum.SITELINK)
            asset.sitelink_asset.link_text = sitelink.text
            if sitelink.description1 and sitelink.description2:
                asset.sitelink_asset.description1 = sitelink.description1
                asset.sitelink_asset.description2 = sitelink.description2
            asset.final_urls.append(str(sitelink.final_url))
            links.append(link)
        for callout in plan.callouts:
            asset, link = link_asset(enums.AssetFieldTypeEnum.CALLOUT)
            asset.callout_asset.callout_text = callout
            links.append(link)
        if plan.structured_snippet:
            asset, link = link_asset(enums.AssetFieldTypeEnum.STRUCTURED_SNIPPET)
            asset.structured_snippet_asset.header = plan.structured_snippet.header
            asset.structured_snippet_asset.values.extend(plan.structured_snippet.values)
            links.append(link)
        if plan.business_name:
            asset, link = link_asset(enums.AssetFieldTypeEnum.BUSINESS_NAME)
            asset.text_asset.text = plan.business_name
            links.append(link)
        self.operations.extend(links)  # links after every asset they reference

        for group in plan.ad_groups:
            group_rn = self._rn("adGroups", self._temp_id())
            ad_group = self._op().ad_group_operation.create
            ad_group.resource_name = group_rn
            ad_group.name = group.name
            ad_group.campaign = campaign_rn
            ad_group.type_ = enums.AdGroupTypeEnum.SEARCH_STANDARD
            ad_group.status = enums.AdGroupStatusEnum.ENABLED
            if group.cpc_bid:
                ad_group.cpc_bid_micros = to_micros(group.cpc_bid)
            for keyword in group.keywords:
                criterion = self._op().ad_group_criterion_operation.create
                criterion.ad_group = group_rn
                criterion.status = enums.AdGroupCriterionStatusEnum.ENABLED
                self._keyword_criterion(criterion, keyword.text, keyword.match_type.value)
            for negative in group.negative_keywords:
                criterion = self._op().ad_group_criterion_operation.create
                criterion.ad_group = group_rn
                criterion.negative = True
                self._keyword_criterion(criterion, negative.text, negative.match_type.value)
            for ad_plan in group.ads:
                group_ad = self._op().ad_group_ad_operation.create
                group_ad.ad_group = group_rn
                group_ad.status = enums.AdGroupAdStatusEnum.ENABLED
                ad = group_ad.ad
                ad.final_urls.append(str(ad_plan.final_url or plan.final_url))
                self._rsa_texts(ad.responsive_search_ad, ad_plan.headlines, ad_plan.descriptions)
                if ad_plan.path1:
                    ad.responsive_search_ad.path1 = ad_plan.path1
                if ad_plan.path2:
                    ad.responsive_search_ad.path2 = ad_plan.path2

    def _rsa_texts(self, rsa: Any, headlines: list[str], descriptions: list[str]) -> None:
        for text in headlines:
            asset = self.client.get_type("AdTextAsset")
            asset.text = text
            rsa.headlines.append(asset)
        for text in descriptions:
            asset = self.client.get_type("AdTextAsset")
            asset.text = text
            rsa.descriptions.append(asset)

    def apply_change(self, change: Any, before: dict[str, Any]) -> None:  # noqa: C901 - one branch per action
        enums = self.client.enums
        campaign_rn = self._rn("campaigns", change.campaign_id) if hasattr(change, "campaign_id") else None
        if isinstance(change, SetNetworks):
            operation = self._op().campaign_operation
            operation.update.resource_name = campaign_rn
            operation.update.network_settings.target_search_network = change.search_partners
            operation.update.network_settings.target_content_network = change.display_network
            self._mask(operation, ["network_settings.target_search_network", "network_settings.target_content_network"])
        elif isinstance(change, AddNegatives):
            for keyword in change.keywords:
                criterion = self._op().campaign_criterion_operation.create
                criterion.campaign = campaign_rn
                criterion.negative = True
                self._keyword_criterion(criterion, keyword.text, keyword.match_type.value)
        elif isinstance(change, RemoveNegatives):
            for criterion_id in change.criterion_ids:
                self._op().campaign_criterion_operation.remove = self._rn(
                    "campaignCriteria", f"{change.campaign_id}~{criterion_id}"
                )
        elif isinstance(change, SetKeywordStatus):
            name = self._rn("adGroupCriteria", f"{change.ad_group_id}~{change.criterion_id}")
            if change.status == "REMOVED":
                self._op().ad_group_criterion_operation.remove = name
            else:
                operation = self._op().ad_group_criterion_operation
                operation.update.resource_name = name
                operation.update.status = enums.AdGroupCriterionStatusEnum[change.status]
                self._mask(operation, ["status"])
        elif isinstance(change, AddKeywords):
            for keyword in change.keywords:
                criterion = self._op().ad_group_criterion_operation.create
                criterion.ad_group = self._rn("adGroups", change.ad_group_id)
                criterion.status = enums.AdGroupCriterionStatusEnum.ENABLED
                self._keyword_criterion(criterion, keyword.text, keyword.match_type.value)
        elif isinstance(change, UpdateResponsiveSearchAd):
            operation = self._op().ad_operation
            operation.update.resource_name = self._rn("ads", change.ad_id)
            self._rsa_texts(operation.update.responsive_search_ad, change.headlines, change.descriptions)
            self._mask(operation, ["responsive_search_ad.headlines", "responsive_search_ad.descriptions"])
        elif isinstance(change, SetBidding):
            operation = self._op().campaign_operation
            operation.update.resource_name = campaign_rn
            self._mask(operation, self._bidding(operation.update, change.bidding))
        elif isinstance(change, SetEndDate):
            operation = self._op().campaign_operation
            operation.update.resource_name = campaign_rn
            operation.update.end_date_time = (
                f"{change.end_date.isoformat()} 23:59:59" if change.end_date else NO_END_DATE
            )
            self._mask(operation, ["end_date_time"])
        elif isinstance(change, SetGeoTargetType):
            operation = self._op().campaign_operation
            operation.update.resource_name = campaign_rn
            operation.update.geo_target_type_setting.positive_geo_target_type = enums.PositiveGeoTargetTypeEnum[
                change.positive
            ]
            self._mask(operation, ["geo_target_type_setting.positive_geo_target_type"])
        elif isinstance(change, SetCampaignStatus):
            operation = self._op().campaign_operation
            operation.update.resource_name = campaign_rn
            operation.update.status = enums.CampaignStatusEnum[change.status]
            self._mask(operation, ["status"])
        elif isinstance(change, RemoveCampaign):
            self._op().campaign_operation.remove = campaign_rn
        elif isinstance(change, SetBudget):
            state = next(
                (
                    b
                    for b in before.get("changes", [])
                    if b.get("campaign_id") == change.campaign_id and b.get("action") == "SET_BUDGET"
                ),
                None,
            )
            if not state or not state.get("budget_resource"):
                raise ProviderError("Orçamento da campanha não encontrado.")
            if state.get("budget_shared"):
                raise ProviderError(
                    "Esta campanha usa orçamento compartilhado; altere pelo Google Ads para não "
                    "afetar outras campanhas."
                )
            operation = self._op().campaign_budget_operation
            operation.update.resource_name = state["budget_resource"]
            operation.update.amount_micros = to_micros(change.daily_budget)
            self._mask(operation, ["amount_micros"])
        elif isinstance(change, CreateConversionAction):
            action = self._op().conversion_action_operation.create
            action.name = change.name
            action.type_ = enums.ConversionActionTypeEnum.WEBPAGE
            action.category = enums.ConversionActionCategoryEnum[change.category]
            action.counting_type = enums.ConversionActionCountingTypeEnum[change.counting]
            action.status = enums.ConversionActionStatusEnum.ENABLED
            action.primary_for_goal = change.primary
            if change.default_value:
                action.value_settings.default_value = float(change.default_value.amount)
                action.value_settings.default_currency_code = change.default_value.currency
                action.value_settings.always_use_default_value = True
        else:  # pragma: no cover - the discriminated union makes this unreachable
            raise ProviderError(f"Ação não suportada: {change.action}")
