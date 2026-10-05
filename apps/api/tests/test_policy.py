from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain import (
    AdGroupPlan,
    ApprovalPurpose,
    GoogleChangePlan,
    GoogleSearchCampaignPlan,
    Keyword,
    Money,
    ResponsiveSearchAd,
    approval_purpose,
)
from app.policy import consistency_issues, evaluate_plan, validate_public_url


def plan(amount: str = "25.00", url: str = "https://example.com/oferta", **extra) -> GoogleSearchCampaignPlan:
    return GoogleSearchCampaignPlan(
        customer_id="1234567890", name="KubeGame Pro | Search", final_url=url,
        daily_budget=Money(amount=amount, currency="BRL"), start_date=date(2026, 11, 1), geo_target_ids=["2076"],
        ad_groups=[AdGroupPlan(name="CKA", keywords=[Keyword(text="curso cka")], ads=[ResponsiveSearchAd(
            headlines=["Curso CKA", "Prepare-se para CKA", "Pacote Completo"],
            descriptions=["Treinamento prático.", "Conheça o pacote."])])],
        campaign_negatives=[Keyword(text="grátis")], **extra)


def test_allows_safe_paused_plan():
    decision = evaluate_plan(plan(), daily_budget_limit=Decimal(100), kill_switch=False, account_currency="BRL")
    assert decision.allowed
    assert plan().initial_status == "PAUSED"


def test_kill_switch_blocks():
    decision = evaluate_plan(plan(), daily_budget_limit=Decimal(100), kill_switch=True)
    assert not decision.allowed
    assert any("kill switch" in v for v in decision.violations)


def test_blocks_budget_over_limit_and_currency_mismatch():
    decision = evaluate_plan(plan("500"), daily_budget_limit=Decimal(100), kill_switch=False, account_currency="USD")
    assert not decision.allowed
    assert len(decision.violations) == 2


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/admin", "http://localhost/admin", "http://10.0.0.5/", "http://169.254.169.254/latest",
    "http://metadata.google.internal/", "https://user:pass@example.com/", "ftp://example.com/", "http://intranet/",
    "http://[::1]/", "http://router.lan/", "http://0.0.0.0/",
])
def test_blocks_private_destinations(url):
    assert validate_public_url(url)


def test_accepts_public_destination():
    assert validate_public_url("https://www.alnperformance.com.br/contato") is None


def test_initial_status_cannot_be_active():
    with pytest.raises(ValidationError):
        plan(initial_status="ENABLED")


def test_budget_and_activation_must_be_separate_proposals():
    mixed = GoogleChangePlan.model_validate({"customer_id": "1234567890", "changes": [
        {"action": "SET_BUDGET", "campaign_id": "1", "daily_budget": {"amount": "50.00"}},
        {"action": "SET_NETWORKS", "campaign_id": "1", "search_partners": False, "display_network": False}]})
    decision = evaluate_plan(mixed, daily_budget_limit=Decimal(100), kill_switch=False)
    assert not decision.allowed
    assert approval_purpose(mixed) == ApprovalPurpose.BUDGET_CHANGE

    activation = GoogleChangePlan.model_validate({"customer_id": "1234567890", "changes": [
        {"action": "SET_CAMPAIGN_STATUS", "campaign_id": "1", "status": "ENABLED"}]})
    assert evaluate_plan(activation, daily_budget_limit=Decimal(100), kill_switch=False).allowed
    assert approval_purpose(activation) == ApprovalPurpose.ACTIVATE


def test_budget_change_respects_workspace_limit():
    change = GoogleChangePlan.model_validate({"customer_id": "1234567890", "changes": [
        {"action": "SET_BUDGET", "campaign_id": "1", "daily_budget": {"amount": "900.00"}}]})
    assert not evaluate_plan(change, daily_budget_limit=Decimal(100), kill_switch=False).allowed


def test_detects_contradictory_numbers():
    issues = consistency_issues(["Casa com 4 vagas", "5 vagas de garagem", "4 suítes", "Área de 450 m²"])
    assert len(issues) == 1 and "vagas" in issues[0]


def test_rsa_limits_and_keyword_cleaning():
    with pytest.raises(ValidationError):
        ResponsiveSearchAd(headlines=["x" * 31, "b", "c"], descriptions=["a", "b"])
    with pytest.raises(ValidationError):
        ResponsiveSearchAd(headlines=["a", "A", "c"], descriptions=["a", "b"])
    assert Keyword(text="  Casa   À Venda ").text == "casa à venda"
    with pytest.raises(ValidationError):
        Keyword(text="casa! barata")


def test_manual_cpc_requires_bids_and_warns_broad():
    manual = plan(bidding={"type": "MANUAL_CPC"})
    assert not evaluate_plan(manual, daily_budget_limit=Decimal(100), kill_switch=False).allowed
    broad = plan()
    broad.ad_groups[0].keywords.append(Keyword(text="curso kubernetes", match_type="BROAD"))
    decision = evaluate_plan(broad, daily_budget_limit=Decimal(100), kill_switch=False)
    assert decision.allowed and any("ampla" in w for w in decision.warnings)
