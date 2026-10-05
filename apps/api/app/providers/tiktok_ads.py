"""TikTok for Business Marketing API v1.3 gateway (plain HTTPS + JSON)."""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import httpx

from ..config import settings
from ..domain import (
    AnyPlan,
    PlanKind,
    TikTokCampaignPlan,
    TikTokChangePlan,
    TikTokSetAdGroupStatus,
    TikTokSetCampaignBudget,
    TikTokSetCampaignStatus,
)
from ..snapshot import AccountSnapshot, AdGroupInfo, AdInfo, CampaignInfo, DailyPoint, Metrics
from .base import AccountRef, Credentials, DiscoveredAccount, ExecutionResult, ProviderError, TokenBundle

log = logging.getLogger("aln.tiktok_ads")

API = "https://business-api.tiktok.com/open_api/v1.3"
AUTH_URL = "https://business-api.tiktok.com/portal/auth"
RECONNECT_CODES = {40102, 40104, 40105, 40106}
RETRYABLE_CODES = {40100, 40133, 50000, 50002, 51000, 51004}
CONVERSION_OBJECTIVES = {"WEB_CONVERSIONS", "LEAD_GENERATION", "CONVERSIONS"}
BILLING = {"CLICK": "CPC", "CONVERT": "OCPM", "REACH": "CPM", "LEAD_GENERATION": "OCPM", "SHOW": "CPM"}


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"))
    except ArithmeticError:
        return Decimal("0")


def _status(value: str | None) -> str:
    return "ENABLED" if (value or "").upper() == "ENABLE" else (value or "UNKNOWN").upper()


class TikTokAdsGateway:
    provider = "TIKTOK_ADS"
    supports_pkce = False

    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        self._http = http

    def authorization_url(self, *, state: str, redirect_uri: str, code_challenge: str | None) -> str:
        return (
            f"{AUTH_URL}?{urlencode({'app_id': settings.tiktok_app_id, 'state': state, 'redirect_uri': redirect_uri})}"
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Access-Token"] = token
        encoded = {k: json.dumps(v) if isinstance(v, list | dict) else v for k, v in (params or {}).items()}
        try:
            if self._http:
                response = await self._http.request(method, f"{API}{path}", headers=headers, params=encoded, json=body)
            else:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.request(method, f"{API}{path}", headers=headers, params=encoded, json=body)
        except httpx.TransportError as error:
            raise ProviderError("Falha de comunicação com o TikTok.", retryable=True) from error
        if response.status_code >= 500 or response.status_code == 429:
            raise ProviderError(f"TikTok indisponível ({response.status_code}).", retryable=True)
        try:
            payload = response.json()
        except ValueError as error:
            raise ProviderError("Resposta inválida do TikTok.", retryable=True) from error
        code = int(payload.get("code", -1))
        if code != 0:
            message = str(payload.get("message", ""))[:300]
            raise ProviderError(
                "O TikTok recusou a operação.",
                retryable=code in RETRYABLE_CODES,
                needs_reconnect=code in RECONNECT_CODES,
                details=[f"{message} [código {code}]"],
            )
        return payload.get("data") or {}

    async def _pages(self, path: str, token: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            data = await self._request("GET", path, token=token, params={**params, "page": page, "page_size": 1000})
            items += data.get("list", [])
            total_pages = int((data.get("page_info") or {}).get("total_page", 1) or 1)
            if page >= total_pages or page >= 20:
                return items
            page += 1

    # ------------------------------------------------------------------ OAuth

    async def exchange_code(self, *, code: str, redirect_uri: str, code_verifier: str | None) -> TokenBundle:
        data = await self._request(
            "POST",
            "/oauth2/access_token/",
            body={"app_id": settings.tiktok_app_id, "secret": settings.tiktok_app_secret, "auth_code": code},
        )
        if not data.get("access_token"):
            raise ProviderError("O TikTok não devolveu o token de acesso.")
        return TokenBundle(
            access_token=data["access_token"],
            scopes=json.dumps(data.get("scope", [])),
            extra={"advertiser_ids": [str(a) for a in data.get("advertiser_ids", [])]},
        )

    async def refresh(self, refresh_token: str) -> TokenBundle:  # pragma: no cover - long-term tokens
        raise ProviderError("Tokens do TikTok não expiram; reconecte se o acesso foi revogado.", needs_reconnect=True)

    async def revoke(self, token: str) -> None:
        await self._request(
            "POST",
            "/oauth2/revoke_token/",
            body={"app_id": settings.tiktok_app_id, "secret": settings.tiktok_app_secret, "access_token": token},
        )

    async def discover_accounts(self, creds: Credentials, token: TokenBundle | None = None) -> list[DiscoveredAccount]:
        data = await self._request(
            "GET",
            "/oauth2/advertiser/get/",
            token=creds.access_token,
            params={"app_id": settings.tiktok_app_id, "secret": settings.tiktok_app_secret},
        )
        advertisers = {str(a["advertiser_id"]): a.get("advertiser_name") or "" for a in data.get("list", [])}
        if not advertisers:
            return []
        info = await self._request(
            "GET",
            "/advertiser/info/",
            token=creds.access_token,
            params={
                "advertiser_ids": list(advertisers)[:100],
                "fields": ["advertiser_id", "name", "currency", "timezone"],
            },
        )
        details = {str(item.get("advertiser_id")): item for item in info.get("list", [])}
        return sorted(
            (
                DiscoveredAccount(
                    external_id=aid,
                    name=details.get(aid, {}).get("name") or name or f"Anunciante {aid}",
                    currency=details.get(aid, {}).get("currency"),
                    time_zone=details.get(aid, {}).get("timezone"),
                )
                for aid, name in advertisers.items()
            ),
            key=lambda a: a.name.lower(),
        )

    # ------------------------------------------------------------------ reads

    async def snapshot(self, creds: Credentials, account: AccountRef, start: date, end: date) -> AccountSnapshot:
        token, aid = creds.access_token or "", account.external_id
        start = max(start, end - timedelta(days=29))  # daily breakdown is limited to 30 days
        campaigns = await self._pages("/campaign/get/", token, {"advertiser_id": aid})
        groups = await self._pages("/adgroup/get/", token, {"advertiser_id": aid})
        ads = await self._pages("/ad/get/", token, {"advertiser_id": aid})
        report = await self._pages(
            "/report/integrated/get/",
            token,
            {
                "advertiser_id": aid,
                "report_type": "BASIC",
                "data_level": "AUCTION_CAMPAIGN",
                "dimensions": ["campaign_id", "stat_time_day"],
                "metrics": ["spend", "impressions", "clicks", "conversion"],
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            },
        )

        snapshot = AccountSnapshot(
            provider=self.provider, account_id=aid, currency=account.currency, period_start=start, period_end=end
        )
        by_id: dict[str, CampaignInfo] = {}
        for c in campaigns:
            if (c.get("operation_status") or "").upper() == "DELETE" or c.get(
                "secondary_status"
            ) == "CAMPAIGN_STATUS_DELETE":
                continue
            cid = str(c["campaign_id"])
            budget_mode = c.get("budget_mode")
            by_id[cid] = CampaignInfo(
                campaign_id=cid,
                name=c.get("campaign_name", cid),
                status=_status(c.get("operation_status")),
                channel="TIKTOK",
                objective=c.get("objective_type"),
                daily_budget=_decimal(c.get("budget")) if budget_mode == "BUDGET_MODE_DAY" else None,
            )
        group_by_id: dict[str, AdGroupInfo] = {}
        for g in groups:
            cid, gid = str(g.get("campaign_id")), str(g["adgroup_id"])
            if cid not in by_id or (g.get("operation_status") or "").upper() == "DELETE":
                continue
            group = AdGroupInfo(
                ad_group_id=gid, name=g.get("adgroup_name", gid), status=_status(g.get("operation_status"))
            )
            group_by_id[gid] = group
            by_id[cid].ad_groups.append(group)
            if by_id[cid].objective in CONVERSION_OBJECTIVES:
                by_id[cid].has_pixel = bool(by_id[cid].has_pixel) or bool(g.get("pixel_id"))
        for ad in ads:
            owner = group_by_id.get(str(ad.get("adgroup_id")))
            if owner and (ad.get("operation_status") or "").upper() != "DELETE":
                owner.ads.append(
                    AdInfo(
                        ad_id=str(ad["ad_id"]),
                        type="TIKTOK_AD",
                        status=_status(ad.get("operation_status")),
                        headlines=[ad.get("ad_name") or ""],
                        descriptions=[ad.get("ad_text") or ""],
                    )
                )
        for row in report:
            dims, metrics = row.get("dimensions", {}), row.get("metrics", {})
            cid = str(dims.get("campaign_id"))
            point = Metrics(
                impressions=int(float(metrics.get("impressions") or 0)),
                clicks=int(float(metrics.get("clicks") or 0)),
                cost=_decimal(metrics.get("spend")),
                conversions=_decimal(metrics.get("conversion")),
            )
            day = date.fromisoformat(str(dims.get("stat_time_day", start.isoformat()))[:10])
            snapshot.daily.append(DailyPoint(day=day, campaign_id=cid, metrics=point))
            if cid in by_id:
                by_id[cid].metrics = by_id[cid].metrics.add(point)
        snapshot.campaigns = sorted(by_id.values(), key=lambda c: (c.status != "ENABLED", -c.metrics.cost))
        return snapshot

    async def reconcile(self, creds: Credentials, account: AccountRef, campaign_ids: list[str]) -> dict[str, str]:
        if not campaign_ids:
            return {}
        items = await self._pages(
            "/campaign/get/",
            creds.access_token or "",
            {"advertiser_id": account.external_id, "filtering": {"campaign_ids": campaign_ids[:100]}},
        )
        found = {str(c["campaign_id"]): _status(c.get("operation_status")) for c in items}
        return {cid: found.get(cid, "MISSING") for cid in campaign_ids}

    # ------------------------------------------------------------------ writes

    async def validate(self, creds: Credentials, account: AccountRef, kind: PlanKind, plan: AnyPlan) -> list[str]:
        # The Marketing API has no validate-only mode; local contracts and policy are the validation.
        return []

    async def _campaign(self, token: str, aid: str, campaign_id: str) -> dict[str, Any]:
        items = await self._pages(
            "/campaign/get/", token, {"advertiser_id": aid, "filtering": {"campaign_ids": [campaign_id]}}
        )
        if not items:
            raise ProviderError(f"Campanha {campaign_id} não encontrada no TikTok.")
        return items[0]

    async def execute(self, creds: Credentials, account: AccountRef, kind: PlanKind, plan: AnyPlan) -> ExecutionResult:
        token, aid = creds.access_token or "", account.external_id
        if isinstance(plan, TikTokCampaignPlan):
            existing = await self._pages("/campaign/get/", token, {"advertiser_id": aid})
            if match := next(
                (
                    c
                    for c in existing
                    if c.get("campaign_name") == plan.name and (c.get("operation_status") or "").upper() != "DELETE"
                ),
                None,
            ):
                return ExecutionResult(status="ALREADY_EXISTS", resources={"campaign_id": str(match["campaign_id"])})
            created = await self._request(
                "POST",
                "/campaign/create/",
                token=token,
                body={
                    "advertiser_id": aid,
                    "campaign_name": plan.name,
                    "objective_type": plan.objective,
                    "budget_mode": "BUDGET_MODE_INFINITE",
                    "operation_status": "DISABLE",
                },
            )
            campaign_id = str(created["campaign_id"])
            group = plan.ad_group
            body: dict[str, Any] = {
                "advertiser_id": aid,
                "campaign_id": campaign_id,
                "adgroup_name": group.name,
                "promotion_type": "WEBSITE",
                "placement_type": "PLACEMENT_TYPE_AUTOMATIC",
                "location_ids": group.location_ids,
                "gender": group.gender,
                "budget_mode": "BUDGET_MODE_DAY",
                "budget": float(plan.daily_budget.amount),
                "schedule_type": "SCHEDULE_START_END" if group.end_date else "SCHEDULE_FROM_NOW",
                "schedule_start_time": f"{max(group.start_date, date.today()).isoformat()} 00:00:00",
                "optimization_goal": group.optimization_goal,
                "billing_event": BILLING[group.optimization_goal],
                "bid_type": "BID_TYPE_NO_BID",
                "pacing": "PACING_MODE_SMOOTH",
                "operation_status": "DISABLE",
            }
            if group.end_date:
                body["schedule_end_time"] = f"{group.end_date.isoformat()} 23:59:59"
            if group.age_groups:
                body["age_groups"] = group.age_groups
            if group.language_codes:
                body["languages"] = group.language_codes
            if group.pixel_id:
                body["pixel_id"] = group.pixel_id
                body["optimization_event"] = group.optimization_event
            try:
                adgroup = await self._request("POST", "/adgroup/create/", token=token, body=body)
            except ProviderError:
                # Saga compensation: never leave a half-built campaign behind.
                await self._request(
                    "POST",
                    "/campaign/status/update/",
                    token=token,
                    body={"advertiser_id": aid, "campaign_ids": [campaign_id], "operation_status": "DELETE"},
                )
                raise
            return ExecutionResult(
                status="CREATED_PAUSED",
                operations=2,
                resources={"campaign_id": campaign_id, "adgroup_id": str(adgroup.get("adgroup_id", ""))},
            )

        if not isinstance(plan, TikTokChangePlan):
            raise ProviderError("Plano não pertence ao TikTok Ads.")
        before: list[dict[str, Any]] = []
        for change in plan.changes:
            if isinstance(change, TikTokSetCampaignStatus | TikTokSetCampaignBudget):
                campaign = await self._campaign(token, aid, change.campaign_id)
                before.append(
                    {
                        "action": change.action,
                        "campaign_id": change.campaign_id,
                        "status": (campaign.get("operation_status") or "").upper(),
                        "budget_mode": campaign.get("budget_mode"),
                        "daily_budget": str(_decimal(campaign.get("budget"))),
                    }
                )
            else:
                before.append({"action": change.action})
        for change, state in zip(plan.changes, before, strict=True):
            if isinstance(change, TikTokSetCampaignStatus):
                await self._request(
                    "POST",
                    "/campaign/status/update/",
                    token=token,
                    body={
                        "advertiser_id": aid,
                        "campaign_ids": [change.campaign_id],
                        "operation_status": change.status,
                    },
                )
            elif isinstance(change, TikTokSetAdGroupStatus):
                await self._request(
                    "POST",
                    "/adgroup/status/update/",
                    token=token,
                    body={"advertiser_id": aid, "adgroup_ids": [change.adgroup_id], "operation_status": change.status},
                )
            elif isinstance(change, TikTokSetCampaignBudget):
                if state.get("budget_mode") != "BUDGET_MODE_DAY":
                    raise ProviderError("O orçamento desta campanha fica no grupo de anúncios; altere por lá.")
                await self._request(
                    "POST",
                    "/campaign/update/",
                    token=token,
                    body={
                        "advertiser_id": aid,
                        "campaign_id": change.campaign_id,
                        "budget": float(change.daily_budget.amount),
                    },
                )
        return ExecutionResult(
            status="APPLIED",
            operations=len(plan.changes),
            before={"changes": before},
            after={"changes": [c.model_dump(mode="json") for c in plan.changes]},
        )
