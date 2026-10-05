"""Deterministic, explainable rules. Runs on every validation, approval and execution."""

import re
from dataclasses import dataclass, field
from decimal import Decimal
from ipaddress import ip_address
from urllib.parse import urlparse

from .domain import (
    AnyPlan,
    BiddingType,
    GoogleChangePlan,
    GoogleSearchCampaignPlan,
    MatchType,
    TikTokCampaignPlan,
    TikTokChangePlan,
    is_activation,
    is_budget_change,
    plan_daily_budget,
)

BLOCKED_HOSTS = {"localhost", "metadata.google.internal", "metadata", "169.254.169.254"}


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    violations: tuple[str, ...]
    warnings: tuple[str, ...]
    snapshot: dict[str, object] = field(default_factory=dict)


def validate_public_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return "A URL de destino deve usar HTTP ou HTTPS."
    if parsed.username or parsed.password:
        return "A URL de destino não pode conter usuário ou senha."
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host or "." not in host and not host.startswith("["):
        return "A URL de destino precisa de um domínio público."
    if host in BLOCKED_HOSTS or host.endswith((".local", ".internal", ".localhost", ".lan")):
        return "A URL de destino não pode apontar para rede local ou metadata."
    try:
        address = ip_address(host.strip("[]"))
    except ValueError:
        return None
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    ):
        return "A URL de destino não pode apontar para um IP privado ou reservado."
    return None


NUMBER_FACT = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(vagas?|su[ií]tes?|quartos?|banheiros?|dormit[óo]rios?|m²|m2|metros?|andares?|lotes?)",
    re.IGNORECASE,
)


def _unit(word: str) -> str:
    word = word.lower().replace("í", "i").replace("ó", "o")
    for key, unit in (
        ("vaga", "vagas"),
        ("suite", "suítes"),
        ("quarto", "quartos"),
        ("banheiro", "banheiros"),
        ("dormitorio", "quartos"),
        ("m", "m²"),
        ("andar", "andares"),
        ("lote", "lotes"),
    ):
        if word.startswith(key):
            return unit
    return word


def consistency_issues(texts: list[str]) -> list[str]:
    """Finds the same attribute written with different numbers (e.g. "4 vagas" and "5 vagas")."""
    seen: dict[str, set[str]] = {}
    for text in texts:
        for number, word in NUMBER_FACT.findall(text):
            seen.setdefault(_unit(word), set()).add(number.replace(",", "."))
    return [
        f"Textos com valores diferentes para {unit}: {', '.join(sorted(values))}."
        for unit, values in sorted(seen.items())
        if len(values) > 1
    ]


def plan_texts(plan: AnyPlan) -> list[str]:
    if isinstance(plan, GoogleSearchCampaignPlan):
        texts = [*plan.callouts]
        for group in plan.ad_groups:
            for ad in group.ads:
                texts += ad.headlines + ad.descriptions
        for link in plan.sitelinks:
            texts += [link.text, link.description1 or "", link.description2 or ""]
        if plan.structured_snippet:
            texts += plan.structured_snippet.values
        return texts
    if isinstance(plan, GoogleChangePlan):
        return [t for c in plan.changes if c.action == "UPDATE_RSA" for t in (*c.headlines, *c.descriptions)]
    return []


def plan_urls(plan: AnyPlan) -> list[str]:
    if isinstance(plan, GoogleSearchCampaignPlan):
        urls = [str(plan.final_url), *(str(s.final_url) for s in plan.sitelinks)]
        urls += [str(ad.final_url) for group in plan.ad_groups for ad in group.ads if ad.final_url]
        return urls
    if isinstance(plan, TikTokCampaignPlan):
        return [str(plan.landing_page)]
    return []


def evaluate_plan(
    plan: AnyPlan,
    *,
    daily_budget_limit: Decimal,
    kill_switch: bool,
    account_currency: str | None = None,
) -> PolicyDecision:
    violations: list[str] = []
    warnings: list[str] = []

    budget = plan_daily_budget(plan)
    if budget and budget.amount > daily_budget_limit:
        violations.append(f"Orçamento diário de {budget.amount} excede o limite do cliente ({daily_budget_limit}).")
    if budget and account_currency and budget.currency != account_currency:
        violations.append(f"Moeda do orçamento ({budget.currency}) diferente da moeda da conta ({account_currency}).")

    for url in plan_urls(plan):
        if error := validate_public_url(url):
            violations.append(f"{error} ({url})")
        elif url.startswith("http://"):
            warnings.append(f"Prefira HTTPS na URL de destino ({url}).")

    if isinstance(plan, GoogleChangePlan | TikTokChangePlan):
        budget_changes = [c for c in plan.changes if is_budget_change(c)]
        activations = [c for c in plan.changes if is_activation(c)]
        if budget_changes and len(plan.changes) > len(budget_changes):
            violations.append("Mudança de orçamento precisa ser uma proposta separada, sem outras alterações.")
        if activations and len(plan.changes) > len(activations):
            violations.append("Ativação precisa ser uma proposta separada, sem outras alterações.")

    if isinstance(plan, GoogleSearchCampaignPlan):
        broad = any(k.match_type == MatchType.BROAD for g in plan.ad_groups for k in g.keywords)
        if broad and plan.bidding.type != BiddingType.MAXIMIZE_CONVERSIONS:
            warnings.append("Correspondência ampla sem Smart Bidding tende a gastar com buscas irrelevantes.")
        if plan.bidding.type == BiddingType.MAXIMIZE_CLICKS and not plan.bidding.cpc_ceiling:
            warnings.append("Maximizar Cliques sem teto de CPC pode encarecer os cliques.")
        if not plan.campaign_negatives and not any(g.negative_keywords for g in plan.ad_groups):
            warnings.append("Campanha sem palavras-chave negativas.")
        if any(len(ad.headlines) < 15 for g in plan.ad_groups for ad in g.ads):
            warnings.append("Anúncios com menos de 15 títulos costumam ter força menor.")
        if plan.bidding.type == BiddingType.MANUAL_CPC and not all(g.cpc_bid for g in plan.ad_groups):
            violations.append("CPC manual exige lance em todos os grupos de anúncios.")

    warnings += consistency_issues(plan_texts(plan))

    if kill_switch:
        violations.append("Mutações externas estão desativadas pelo kill switch global.")

    return PolicyDecision(
        allowed=not violations,
        violations=tuple(violations),
        warnings=tuple(warnings),
        snapshot={
            "daily_budget_limit": str(daily_budget_limit),
            "required_initial_status": "PAUSED",
            "kill_switch": kill_switch,
            "account_currency": account_currency,
        },
    )
