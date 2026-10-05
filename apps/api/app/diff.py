"""Human-readable before/after for the approval screen."""

from typing import Any

from .domain import (
    AddKeywords,
    AddNegatives,
    CreateConversionAction,
    GoogleChangePlan,
    GoogleSearchCampaignPlan,
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
    TikTokCampaignPlan,
    TikTokChangePlan,
    TikTokSetAdGroupStatus,
    TikTokSetCampaignBudget,
    TikTokSetCampaignStatus,
    UpdateResponsiveSearchAd,
    parse_plan,
)
from .snapshot import AccountSnapshot, CampaignInfo

YES_NO = {True: "Ligado", False: "Desligado", None: "?"}
BIDDING_LABEL = {
    "MAXIMIZE_CLICKS": "Maximizar cliques",
    "TARGET_SPEND": "Maximizar cliques",
    "MAXIMIZE_CONVERSIONS": "Maximizar conversões",
    "MANUAL_CPC": "CPC manual",
    "TARGET_CPA": "CPA desejado",
    "TARGET_ROAS": "ROAS desejado",
    "MAXIMIZE_CONVERSION_VALUE": "Maximizar valor",
}


def _row(label: str, before: Any, after: Any) -> dict[str, str]:
    return {"label": label, "before": "—" if before in (None, "") else str(before), "after": str(after)}


def describe(kind: PlanKind, content: dict[str, Any], snapshot: AccountSnapshot | None) -> list[dict[str, str]]:
    plan = parse_plan(kind, content)
    campaigns: dict[str, CampaignInfo] = {c.campaign_id: c for c in snapshot.campaigns} if snapshot else {}

    def name(campaign_id: str) -> str:
        return campaigns[campaign_id].name if campaign_id in campaigns else f"campanha {campaign_id}"

    rows: list[dict[str, str]] = []
    if isinstance(plan, GoogleSearchCampaignPlan):
        keywords = sum(len(g.keywords) for g in plan.ad_groups)
        rows += [
            _row("Nova campanha de Pesquisa", None, f"{plan.name} (PAUSADA)"),
            _row("Orçamento diário", None, f"{plan.daily_budget.amount} {plan.daily_budget.currency}"),
            _row(
                "Lance",
                None,
                BIDDING_LABEL[plan.bidding.type.value]
                + (f", teto {plan.bidding.cpc_ceiling.amount}" if plan.bidding.cpc_ceiling else ""),
            ),
            _row("Redes", None, "Só Pesquisa do Google (sem Parceiros, sem Display)"),
            _row("Localização", None, ", ".join(plan.geo_target_names or plan.geo_target_ids) + " · presença"),
            _row(
                "Estrutura",
                None,
                f"{len(plan.ad_groups)} grupo(s), {keywords} palavra(s)-chave, "
                f"{sum(len(g.ads) for g in plan.ad_groups)} anúncio(s)",
            ),
            _row("Negativas", None, str(len(plan.campaign_negatives))),
            _row("Extensões", None, f"{len(plan.sitelinks)} sitelinks, {len(plan.callouts)} frases de destaque"),
        ]
        return rows
    if isinstance(plan, TikTokCampaignPlan):
        return [
            _row("Nova campanha TikTok", None, f"{plan.name} (DESATIVADA)"),
            _row("Objetivo", None, plan.objective),
            _row("Orçamento diário do grupo", None, f"{plan.daily_budget.amount} {plan.daily_budget.currency}"),
            _row("Otimização", None, plan.ad_group.optimization_goal),
        ]
    if isinstance(plan, GoogleChangePlan):
        for change in plan.changes:
            current = campaigns.get(getattr(change, "campaign_id", ""))
            if isinstance(change, SetNetworks):
                rows.append(
                    _row(
                        f"Parceiros de Pesquisa · {name(change.campaign_id)}",
                        YES_NO[current.search_partners if current else None],
                        YES_NO[change.search_partners],
                    )
                )
                rows.append(
                    _row(
                        f"Rede de Display · {name(change.campaign_id)}",
                        YES_NO[current.display_network if current else None],
                        YES_NO[change.display_network],
                    )
                )
            elif isinstance(change, AddNegatives):
                rows.append(
                    _row(
                        f"Negativas · {name(change.campaign_id)}",
                        f"{len(current.negatives)} negativas" if current else None,
                        "+ " + ", ".join(f"{k.text} [{k.match_type.value.lower()}]" for k in change.keywords),
                    )
                )
            elif isinstance(change, RemoveNegatives):
                texts = {n.criterion_id: n.text for n in current.negatives} if current else {}
                rows.append(
                    _row(
                        f"Remover negativas · {name(change.campaign_id)}",
                        ", ".join(texts.get(i, i) for i in change.criterion_ids),
                        "removidas",
                    )
                )
            elif isinstance(change, SetKeywordStatus):
                keyword = next(
                    (
                        k
                        for c in campaigns.values()
                        for g in c.ad_groups
                        if g.ad_group_id == change.ad_group_id
                        for k in g.keywords
                        if k.criterion_id == change.criterion_id
                    ),
                    None,
                )
                rows.append(
                    _row(
                        f"Palavra-chave {keyword.text if keyword else change.criterion_id}",
                        keyword.status if keyword else None,
                        change.status,
                    )
                )
            elif isinstance(change, AddKeywords):
                rows.append(
                    _row(
                        f"Novas palavras-chave · grupo {change.ad_group_id}",
                        None,
                        ", ".join(f"{k.text} [{k.match_type.value.lower()}]" for k in change.keywords),
                    )
                )
            elif isinstance(change, UpdateResponsiveSearchAd):
                ad = next(
                    (a for c in campaigns.values() for g in c.ad_groups for a in g.ads if a.ad_id == change.ad_id), None
                )
                rows.append(
                    _row(
                        f"Títulos do anúncio {change.ad_id}",
                        " | ".join(ad.headlines) if ad else None,
                        " | ".join(change.headlines),
                    )
                )
                rows.append(
                    _row(
                        f"Descrições do anúncio {change.ad_id}",
                        " | ".join(ad.descriptions) if ad else None,
                        " | ".join(change.descriptions),
                    )
                )
            elif isinstance(change, SetBidding):
                after = BIDDING_LABEL[change.bidding.type.value]
                if change.bidding.cpc_ceiling:
                    after += f", teto de CPC {change.bidding.cpc_ceiling.amount}"
                if change.bidding.target_cpa:
                    after += f", CPA {change.bidding.target_cpa.amount}"
                rows.append(
                    _row(
                        f"Estratégia de lance · {name(change.campaign_id)}",
                        BIDDING_LABEL.get(current.bidding_strategy or "", current.bidding_strategy)
                        if current
                        else None,
                        after,
                    )
                )
            elif isinstance(change, SetEndDate):
                rows.append(
                    _row(
                        f"Data de término · {name(change.campaign_id)}",
                        current.end_date if current else None,
                        change.end_date or "sem data de término",
                    )
                )
            elif isinstance(change, SetGeoTargetType):
                rows.append(
                    _row(
                        f"Segmentação de local · {name(change.campaign_id)}",
                        current.geo_target_type if current else None,
                        change.positive,
                    )
                )
            elif isinstance(change, SetCampaignStatus):
                rows.append(
                    _row(f"Status · {name(change.campaign_id)}", current.status if current else None, change.status)
                )
            elif isinstance(change, SetBudget):
                rows.append(
                    _row(
                        f"Orçamento diário · {name(change.campaign_id)}",
                        current.daily_budget if current else None,
                        f"{change.daily_budget.amount} {change.daily_budget.currency}",
                    )
                )
            elif isinstance(change, CreateConversionAction):
                rows.append(_row("Nova ação de conversão", None, f"{change.name} ({change.category})"))
            elif isinstance(change, RemoveCampaign):
                rows.append(
                    _row(
                        f"Remover campanha · {name(change.campaign_id)}",
                        current.status if current else None,
                        "REMOVIDA",
                    )
                )
        return rows
    if isinstance(plan, TikTokChangePlan):
        for tchange in plan.changes:
            current = campaigns.get(getattr(tchange, "campaign_id", ""))
            if isinstance(tchange, TikTokSetCampaignStatus):
                rows.append(
                    _row(f"Status · {name(tchange.campaign_id)}", current.status if current else None, tchange.status)
                )
            elif isinstance(tchange, TikTokSetAdGroupStatus):
                rows.append(_row(f"Status do grupo {tchange.adgroup_id}", None, tchange.status))
            elif isinstance(tchange, TikTokSetCampaignBudget):
                rows.append(
                    _row(
                        f"Orçamento diário · {name(tchange.campaign_id)}",
                        current.daily_budget if current else None,
                        tchange.daily_budget.amount,
                    )
                )
    return rows


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            out |= flatten(item, f"{prefix}.{key}" if prefix else str(key))
        return out
    if isinstance(value, list):
        out = {}
        for index, item in enumerate(value):
            out |= flatten(item, f"{prefix}[{index}]")
        return out
    return {prefix: value}


def revision_diff(old: dict[str, Any], new: dict[str, Any]) -> list[dict[str, str]]:
    a, b = flatten(old), flatten(new)
    return [
        _row(path, a.get(path), b.get(path, "—")) for path in sorted(set(a) | set(b)) if a.get(path) != b.get(path)
    ][:80]
