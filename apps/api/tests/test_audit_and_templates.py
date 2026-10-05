from datetime import date
from decimal import Decimal

from app.audit_rules import build_report
from app.diff import describe, revision_diff
from app.domain import GoogleChangePlan, GoogleSearchCampaignPlan, Money, PlanKind, parse_plan
from app.policy import consistency_issues, plan_texts
from app.services.revert import inverse
from app.snapshot import AccountSnapshot, CampaignInfo, Metrics
from app.templates import Briefing, PropertySheet, briefing_plan, real_estate_plan

from .conftest import sample_snapshot


def test_google_audit_finds_the_known_problems():
    report = build_report(sample_snapshot(), today=date(2026, 10, 5))
    rules = {f.rule for f in report.findings}
    assert {"G001", "G002", "G003", "G004", "G005", "G006", "G007", "G008", "G009", "G010", "G012", "G015"} <= rules
    assert report.findings[0].severity == "critical"
    assert 0 <= report.score < 50
    # Every proposal produced by the audit is a valid change plan.
    for finding in report.findings:
        if finding.proposal:
            GoogleChangePlan.model_validate(finding.proposal)


def test_healthy_account_scores_high():
    healthy = AccountSnapshot(provider="GOOGLE_ADS", account_id="1234567890", period_start=date(2026, 9, 1),
                              period_end=date(2026, 9, 30), enhanced_conversions_for_leads=True)
    report = build_report(healthy)
    assert report.score >= 80


def test_tiktok_audit():
    snapshot = AccountSnapshot(provider="TIKTOK_ADS", account_id="700", period_start=date(2026, 9, 1),
                               period_end=date(2026, 9, 30), campaigns=[CampaignInfo(
                                   campaign_id="1", name="Leads", status="ENABLED", channel="TIKTOK",
                                   objective="WEB_CONVERSIONS", has_pixel=False,
                                   metrics=Metrics(impressions=10000, clicks=20, cost=Decimal("300")))])
    rules = {f.rule for f in build_report(snapshot).findings}
    assert {"T001", "T002", "T003"} <= rules


def sheet(**extra) -> PropertySheet:
    return PropertySheet.model_validate({
        "title": "Casa Itahyê 4 suítes", "condominium": "Itahyê", "neighborhood": "Alphaville", "city": "Barueri",
        "price": "4500000", "area_m2": 450, "suites": 4, "parking": 4,
        "differentials": ["Piscina aquecida", "Vista para o verde"], "url": "https://portoimoveis.com.br/itahye",
        "daily_budget": {"amount": "60.00"}, "geo_target_ids": ["1001773"], "start_date": "2026-11-01", **extra})


def test_real_estate_template_is_valid_and_consistent():
    content = real_estate_plan(sheet(), "1234567890")
    plan = parse_plan(PlanKind.GOOGLE_SEARCH_CAMPAIGN, content)
    assert isinstance(plan, GoogleSearchCampaignPlan)
    assert plan.bidding.type == "MAXIMIZE_CLICKS"
    assert any(k.match_type == "EXACT" for k in plan.ad_groups[0].keywords)
    assert len(plan.campaign_negatives) >= 15
    assert not consistency_issues(plan_texts(plan))
    assert all(len(h) <= 30 for h in plan.ad_groups[0].ads[0].headlines)


def test_briefing_template_drops_negatives_that_collide_with_the_offer():
    briefing = Briefing.model_validate({
        "company": "KubeGame", "offer": "Curso preparatório para CKA com laboratório", "landing_page": "https://kubegame.com.br",
        "seed_keywords": ["curso cka", "certificação kubernetes"], "daily_budget": {"amount": "30.00"},
        "geo_target_ids": ["2076"], "start_date": "2026-11-01"})
    plan = parse_plan(PlanKind.GOOGLE_SEARCH_CAMPAIGN, briefing_plan(briefing, "1234567890"))
    negatives = {n.text for n in plan.campaign_negatives}
    assert "curso" not in negatives and "grátis" in negatives


def test_revert_builds_inverse_proposals():
    created = inverse(PlanKind.GOOGLE_SEARCH_CAMPAIGN, real_estate_plan(sheet(), "1234567890"), None,
                      {"campaign": "customers/1234567890/campaigns/555"})
    assert created and created[1]["changes"] == [{"action": "REMOVE_CAMPAIGN", "campaign_id": "555"}]

    change = {"customer_id": "1234567890", "changes": [
        {"action": "SET_NETWORKS", "campaign_id": "111", "search_partners": False, "display_network": False},
        {"action": "ADD_NEGATIVES", "campaign_id": "111", "keywords": [{"text": "aluguel"}, {"text": "leilão"}]}]}
    before = {"changes": [{"action": "SET_NETWORKS", "search_partners": True, "display_network": True},
                          {"action": "ADD_NEGATIVES"}]}
    result = {"resource_names": ["customers/1234567890/campaigns/111",
                                 "customers/1234567890/campaignCriteria/111~901",
                                 "customers/1234567890/campaignCriteria/111~902"]}
    kind, content = inverse(PlanKind.GOOGLE_CHANGE, change, before, result)
    plan = parse_plan(kind, content)
    assert plan.changes[0].search_partners is True
    assert plan.changes[1].criterion_ids == ["901", "902"]


def test_diff_describes_before_and_after():
    content = {"customer_id": "1234567890", "changes": [
        {"action": "SET_NETWORKS", "campaign_id": "111", "search_partners": False, "display_network": False},
        {"action": "SET_BUDGET", "campaign_id": "111", "daily_budget": {"amount": "40.00"}}]}
    rows = describe(PlanKind.GOOGLE_CHANGE, content, sample_snapshot())
    assert rows[0]["before"] == "Ligado" and rows[0]["after"] == "Desligado"
    assert rows[-1]["before"] == "80.00"
    assert revision_diff({"a": 1, "b": [1]}, {"a": 2, "b": [1, 2]}) == [
        {"label": "a", "before": "1", "after": "2"}, {"label": "b[1]", "before": "—", "after": "2"}]


def test_money_is_decimal_and_two_places():
    assert Money(amount="10.5").amount == Decimal("10.5")
