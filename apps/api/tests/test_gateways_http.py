import json
from datetime import date

import httpx
import pytest

from app.domain import PlanKind, parse_plan
from app.providers import AccountRef, Credentials, ProviderError
from app.providers.google_ads import GoogleAdsGateway
from app.providers.tiktok_ads import TikTokAdsGateway


def tiktok(handler) -> TikTokAdsGateway:
    return TikTokAdsGateway(httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def ok(data: dict) -> httpx.Response:
    return httpx.Response(200, json={"code": 0, "message": "OK", "data": data})


async def test_tiktok_oauth_and_discovery():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth2/access_token/"):
            body = json.loads(request.content)
            assert body["auth_code"] == "code-1" and body["secret"] == "tiktok-secret"
            return ok({"access_token": "tt-token", "advertiser_ids": [700, 701], "scope": [4]})
        if request.url.path.endswith("/oauth2/advertiser/get/"):
            assert request.headers["Access-Token"] == "tt-token"
            return ok({"list": [{"advertiser_id": 700, "advertiser_name": "Loja A"}]})
        if request.url.path.endswith("/advertiser/info/"):
            assert json.loads(request.url.params["advertiser_ids"]) == ["700"]
            return ok({"list": [{"advertiser_id": "700", "name": "Loja A", "currency": "BRL",
                                 "timezone": "America/Sao_Paulo"}]})
        raise AssertionError(request.url)

    gateway = tiktok(handler)
    url = gateway.authorization_url(state="abc", redirect_uri="https://app/api/v1/connections/tiktok/callback",
                                    code_challenge=None)
    assert "app_id=7000000000" in url and "state=abc" in url
    token = await gateway.exchange_code(code="code-1", redirect_uri="x", code_verifier=None)
    assert token.extra["advertiser_ids"] == ["700", "701"]
    accounts = await gateway.discover_accounts(Credentials("tt-token"))
    assert accounts[0].external_id == "700" and accounts[0].currency == "BRL"


async def test_tiktok_snapshot_parses_report():
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/campaign/get/"):
            return ok({"list": [{"campaign_id": "1", "campaign_name": "Leads", "objective_type": "WEB_CONVERSIONS",
                                 "operation_status": "ENABLE", "budget_mode": "BUDGET_MODE_DAY", "budget": 100}],
                       "page_info": {"total_page": 1}})
        if path.endswith("/adgroup/get/"):
            return ok({"list": [{"adgroup_id": "2", "campaign_id": "1", "adgroup_name": "G",
                                 "operation_status": "ENABLE", "pixel_id": None}]})
        if path.endswith("/ad/get/"):
            return ok({"list": [{"ad_id": "3", "adgroup_id": "2", "operation_status": "ENABLE", "ad_name": "Vídeo"}]})
        if path.endswith("/report/integrated/get/"):
            return ok({"list": [{"dimensions": {"campaign_id": "1", "stat_time_day": "2026-10-01 00:00:00"},
                                 "metrics": {"spend": "120.50", "impressions": "9000", "clicks": "40",
                                             "conversion": "0"}}]})
        raise AssertionError(path)

    snapshot = await tiktok(handler).snapshot(Credentials("t"), AccountRef("700", currency="BRL"),
                                              date(2026, 9, 1), date(2026, 10, 4))
    campaign = snapshot.campaigns[0]
    assert campaign.status == "ENABLED" and str(campaign.metrics.cost) == "120.50"
    assert campaign.has_pixel is False and campaign.ad_groups[0].ads[0].ad_id == "3"
    assert snapshot.period_start == date(2026, 9, 5), "daily reports are capped at 30 days"


async def test_tiktok_create_compensates_when_adgroup_fails():
    calls: list[tuple[str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        body = json.loads(request.content) if request.content else {}
        calls.append((path, body))
        if path.endswith("/campaign/get/"):
            return ok({"list": []})
        if path.endswith("/campaign/create/"):
            assert body["operation_status"] == "DISABLE"
            return ok({"campaign_id": "900"})
        if path.endswith("/adgroup/create/"):
            return httpx.Response(200, json={"code": 40002, "message": "invalid location", "data": {}})
        if path.endswith("/campaign/status/update/"):
            return ok({})
        raise AssertionError(path)

    plan = parse_plan(PlanKind.TIKTOK_CAMPAIGN, {
        "advertiser_id": "700", "name": "Leads Outubro", "objective": "TRAFFIC", "landing_page": "https://loja.com.br",
        "daily_budget": {"amount": "80.00"}, "ad_group": {"name": "Grupo SP", "location_ids": ["3448439"],
                                                          "start_date": "2026-11-01"}})
    with pytest.raises(ProviderError) as error:
        await tiktok(handler).execute(Credentials("t"), AccountRef("700"), PlanKind.TIKTOK_CAMPAIGN, plan)
    assert "40002" in error.value.details[0]
    assert calls[-1][0].endswith("/campaign/status/update/") and calls[-1][1]["operation_status"] == "DELETE"


async def test_tiktok_error_codes_map_to_reconnect_and_retry():
    gateway = tiktok(lambda r: httpx.Response(200, json={"code": 40105, "message": "token invalid"}))
    with pytest.raises(ProviderError) as error:
        await gateway.discover_accounts(Credentials("t"))
    assert error.value.needs_reconnect
    gateway = tiktok(lambda r: httpx.Response(503))
    with pytest.raises(ProviderError) as error:
        await gateway.discover_accounts(Credentials("t"))
    assert error.value.retryable


async def test_google_oauth_http():
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        form = dict(x.split("=", 1) for x in request.content.decode().split("&"))
        seen.append(form)
        if form.get("grant_type") == "authorization_code":
            return httpx.Response(200, json={"access_token": "ya29.a", "refresh_token": "1//r", "expires_in": 3599})
        if form.get("refresh_token") == "dead":
            return httpx.Response(400, json={"error": "invalid_grant"})
        if form.get("grant_type") == "refresh_token":
            return httpx.Response(200, json={"access_token": "ya29.b", "expires_in": 3599})
        return httpx.Response(200)

    gateway = GoogleAdsGateway(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    url = gateway.authorization_url(state="s", redirect_uri="https://app/api/cb", code_challenge="c")
    for part in ("access_type=offline", "prompt=consent", "code_challenge_method=S256", "scope=https"):
        assert part in url
    bundle = await gateway.exchange_code(code="c0de", redirect_uri="https://app/api/cb", code_verifier="v" * 50)
    assert bundle.refresh_token == "1//r" and seen[0]["code_verifier"] == "v" * 50
    assert (await gateway.refresh("ok")).access_token == "ya29.b"
    with pytest.raises(ProviderError) as error:
        await gateway.refresh("dead")
    assert error.value.needs_reconnect
    await gateway.revoke("1//r")
