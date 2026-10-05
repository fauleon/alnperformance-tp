"""Builds real Google Ads v25 protobuf operations offline (no network, fake credentials)."""

from datetime import date

import pytest
from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

from app.config import GOOGLE_ADS_API_VERSION
from app.domain import GoogleChangePlan, PlanKind, parse_plan
from app.providers.google_ads import OperationBuilder, gaql_string, operations_per_change, to_micros
from app.templates import PropertySheet, real_estate_plan


@pytest.fixture(scope="module")
def client():
    return GoogleAdsClient(credentials=Credentials(token="offline"), developer_token="x",
                           version=GOOGLE_ADS_API_VERSION, use_proto_plus=True)


def which(op):
    return type(op).pb(op).WhichOneof("operation")


def test_create_search_campaign_operations(client):
    sheet = PropertySheet.model_validate({
        "title": "Casa Itahyê", "condominium": "Itahyê", "neighborhood": "Alphaville", "city": "Barueri",
        "suites": 4, "parking": 4, "url": "https://portoimoveis.com.br/itahye", "daily_budget": {"amount": "60.00"},
        "cpc_ceiling": {"amount": "4.50"}, "geo_target_ids": ["1001773"], "start_date": "2026-11-01",
        "end_date": "2026-12-31", "business_name": "Porto Imóveis",
        "sitelinks": [{"text": "Fotos", "final_url": "https://portoimoveis.com.br/itahye/fotos"},
                      {"text": "Localização", "final_url": "https://portoimoveis.com.br/itahye/mapa"}]})
    plan = parse_plan(PlanKind.GOOGLE_SEARCH_CAMPAIGN, real_estate_plan(sheet, "1234567890"))
    builder = OperationBuilder(client, "1234567890")
    builder.create_search_campaign(plan, today=date(2026, 10, 5))
    kinds = [which(op) for op in builder.operations]

    assert kinds[0] == "campaign_budget_operation" and kinds[1] == "campaign_operation"
    # Every asset is created before the campaign_asset that links it.
    assert kinds.index("asset_operation") < kinds.index("campaign_asset_operation")
    assert max(i for i, k in enumerate(kinds) if k == "asset_operation") < min(
        i for i, k in enumerate(kinds) if k == "campaign_asset_operation")

    budget = builder.operations[0].campaign_budget_operation.create
    assert budget.amount_micros == to_micros(plan.daily_budget) == 60_000_000
    assert budget.explicitly_shared is False

    campaign = builder.operations[1].campaign_operation.create
    enums = client.enums
    assert campaign.status == enums.CampaignStatusEnum.PAUSED
    assert campaign.advertising_channel_type == enums.AdvertisingChannelTypeEnum.SEARCH
    assert campaign.network_settings.target_google_search is True
    assert campaign.network_settings.target_search_network is False
    assert campaign.network_settings.target_content_network is False
    assert campaign.geo_target_type_setting.positive_geo_target_type == enums.PositiveGeoTargetTypeEnum.PRESENCE
    assert campaign.contains_eu_political_advertising == (
        enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING)
    assert campaign.target_spend.cpc_bid_ceiling_micros == 4_500_000
    assert campaign.start_date_time == "2026-11-01 00:00:00"
    assert campaign.end_date_time == "2026-12-31 23:59:59"
    assert campaign.campaign_budget == budget.resource_name

    keyword_ops = [op.ad_group_criterion_operation.create for op in builder.operations
                   if which(op) == "ad_group_criterion_operation"]
    assert len(keyword_ops) == len(plan.ad_groups[0].keywords)
    ad = next(op.ad_group_ad_operation.create for op in builder.operations if which(op) == "ad_group_ad_operation")
    assert len(ad.ad.responsive_search_ad.headlines) == len(plan.ad_groups[0].ads[0].headlines)
    negatives = [op for op in builder.operations if which(op) == "campaign_criterion_operation"
                 and op.campaign_criterion_operation.create.negative]
    assert len(negatives) == len(plan.campaign_negatives)


def test_past_start_date_is_omitted(client):
    plan = parse_plan(PlanKind.GOOGLE_SEARCH_CAMPAIGN, {
        "customer_id": "1234567890", "name": "Teste", "final_url": "https://example.com",
        "daily_budget": {"amount": "10.00"}, "start_date": "2026-01-01", "geo_target_ids": ["2076"],
        "bidding": {"type": "MANUAL_CPC"},
        "ad_groups": [{"name": "Grupo", "cpc_bid": {"amount": "1.20"}, "keywords": [{"text": "teste"}],
                       "ads": [{"headlines": ["a", "b", "c"], "descriptions": ["d", "e"]}]}]})
    builder = OperationBuilder(client, "1234567890")
    builder.create_search_campaign(plan, today=date(2026, 10, 5))
    campaign = builder.operations[1].campaign_operation.create
    assert campaign.start_date_time == ""
    assert type(campaign).pb(campaign).WhichOneof("campaign_bidding_strategy") == "manual_cpc"


def test_change_operations_use_update_masks(client):
    plan = GoogleChangePlan.model_validate({"customer_id": "1234567890", "changes": [
        {"action": "SET_NETWORKS", "campaign_id": "111", "search_partners": False, "display_network": False},
        {"action": "ADD_NEGATIVES", "campaign_id": "111", "keywords": [{"text": "aluguel"}, {"text": "leilão"}]},
        {"action": "SET_KEYWORD_STATUS", "ad_group_id": "222", "criterion_id": "333", "status": "PAUSED"},
        {"action": "SET_BIDDING", "campaign_id": "111", "bidding": {"type": "MAXIMIZE_CLICKS"}},
        {"action": "SET_END_DATE", "campaign_id": "111", "end_date": None},
        {"action": "SET_GEO_TARGET_TYPE", "campaign_id": "111", "positive": "PRESENCE"},
        {"action": "UPDATE_RSA", "ad_id": "444", "headlines": ["a", "b", "c"], "descriptions": ["d", "e"]},
        {"action": "CREATE_CONVERSION_ACTION", "name": "Lead - Formulário"},
    ]})
    builder = OperationBuilder(client, "1234567890")
    for change in plan.changes:
        builder.apply_change(change, {})
    assert len(builder.operations) == sum(operations_per_change(c) for c in plan.changes)
    networks = builder.operations[0].campaign_operation
    assert list(networks.update_mask.paths) == ["network_settings.target_search_network",
                                                "network_settings.target_content_network"]
    assert networks.update.network_settings.target_search_network is False
    keyword = builder.operations[3].ad_group_criterion_operation
    assert keyword.update.resource_name == "customers/1234567890/adGroupCriteria/222~333"
    assert list(builder.operations[4].campaign_operation.update_mask.paths) == ["target_spend"]
    assert builder.operations[5].campaign_operation.update.end_date_time == "2037-12-30 23:59:59"
    rsa = builder.operations[7].ad_operation
    assert rsa.update.resource_name == "customers/1234567890/ads/444"


def test_budget_change_refuses_shared_budget(client):
    from app.providers import ProviderError

    plan = GoogleChangePlan.model_validate({"customer_id": "1234567890", "changes": [
        {"action": "SET_BUDGET", "campaign_id": "111", "daily_budget": {"amount": "40.00"}}]})
    builder = OperationBuilder(client, "1234567890")
    before = {"changes": [{"action": "SET_BUDGET", "campaign_id": "111", "budget_resource": "customers/1/campaignBudgets/9",
                           "budget_shared": True}]}
    with pytest.raises(ProviderError):
        builder.apply_change(plan.changes[0], before)
    before["changes"][0]["budget_shared"] = False
    builder.apply_change(plan.changes[0], before)
    assert builder.operations[-1].campaign_budget_operation.update.amount_micros == 40_000_000


def test_gaql_string_escapes_quotes():
    assert gaql_string("Casa d'Ouro \\ x") == "'Casa d\\'Ouro \\\\ x'"
