from datetime import date
from decimal import Decimal

from app.domain import AdGroupPlan, DateRange, GoogleSearchCampaignPlan, Money
from app.policy import evaluate_plan, validate_public_url


def plan(amount: str = "25.00") -> GoogleSearchCampaignPlan:
    return GoogleSearchCampaignPlan(
        customer_id="demo",
        name="KubeGame Pro | Search | Agosto",
        final_url="https://example.com/oferta",
        daily_budget=Money(amount=amount, currency="BRL"),
        period=DateRange(start=date(2026, 8, 14), end=date(2026, 8, 31)),
        geo_targets=["Brasil"],
        language_targets=["pt-BR"],
        conversion_goal_ids=["purchase"],
        ad_groups=[AdGroupPlan(name="CKA", keywords=["curso cka"], headlines=["Curso CKA", "Prepare-se para CKA", "Pacote Completo"], descriptions=["Treinamento prático.", "Conheça o pacote."])],
    )


def test_allows_safe_paused_plan():
    decision = evaluate_plan(plan(), daily_budget_limit=Decimal(100), kill_switch=False)
    assert decision.allowed


def test_blocks_budget_over_limit_and_kill_switch():
    decision = evaluate_plan(plan("500"), daily_budget_limit=Decimal(100), kill_switch=True)
    assert not decision.allowed
    assert len(decision.violations) == 2


def test_blocks_private_destinations():
    assert validate_public_url("http://127.0.0.1/admin")
    assert validate_public_url("http://localhost/admin")

