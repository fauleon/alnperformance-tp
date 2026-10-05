"""Builds the inverse proposal of an executed plan. The inverse goes through approval like anything else."""

from typing import Any

from ..domain import (
    AddKeywords,
    AddNegatives,
    GoogleChangePlan,
    GoogleSearchCampaignPlan,
    PlanKind,
    RemoveNegatives,
    SetBidding,
    SetBudget,
    SetCampaignStatus,
    SetEndDate,
    SetGeoTargetType,
    SetKeywordStatus,
    SetNetworks,
    TikTokChangePlan,
    TikTokSetCampaignBudget,
    TikTokSetCampaignStatus,
    UpdateResponsiveSearchAd,
    parse_plan,
)
from ..providers.google_ads import operations_per_change

BIDDING_BACK = {
    "TARGET_SPEND": "MAXIMIZE_CLICKS",
    "MAXIMIZE_CONVERSIONS": "MAXIMIZE_CONVERSIONS",
    "MANUAL_CPC": "MANUAL_CPC",
}
MATCH = {"EXACT", "PHRASE", "BROAD"}


def _tail(resource_name: str) -> list[str]:
    return resource_name.rsplit("/", 1)[-1].split("~")


def inverse(
    kind: PlanKind, content: dict[str, Any], before: dict[str, Any] | None, result: dict[str, Any] | None
) -> tuple[PlanKind, dict[str, Any]] | None:
    plan = parse_plan(kind, content)
    before_changes = (before or {}).get("changes", [])
    names: list[str] = list((result or {}).get("resource_names", []))

    if isinstance(plan, GoogleSearchCampaignPlan):
        campaign = (result or {}).get("campaign")
        if not campaign:
            return None
        return PlanKind.GOOGLE_CHANGE, {
            "customer_id": plan.customer_id,
            "rationale": f'Reverter a criação de "{plan.name}" (remover campanha).',
            "changes": [{"action": "REMOVE_CAMPAIGN", "campaign_id": _tail(campaign)[0]}],
        }

    if isinstance(plan, GoogleChangePlan):
        inverse_changes: list[dict[str, Any]] = []
        cursor = 0
        for index, change in enumerate(plan.changes):
            state = before_changes[index] if index < len(before_changes) else {}
            created = names[cursor : cursor + operations_per_change(change)]
            cursor += operations_per_change(change)
            if isinstance(change, SetNetworks) and "search_partners" in state:
                inverse_changes.append(
                    {
                        "action": "SET_NETWORKS",
                        "campaign_id": change.campaign_id,
                        "search_partners": state["search_partners"],
                        "display_network": state["display_network"],
                    }
                )
            elif isinstance(change, AddNegatives) and created:
                inverse_changes.append(
                    {
                        "action": "REMOVE_NEGATIVES",
                        "campaign_id": change.campaign_id,
                        "criterion_ids": [_tail(n)[-1] for n in created],
                    }
                )
            elif isinstance(change, RemoveNegatives) and state.get("keywords"):
                inverse_changes.append(
                    {
                        "action": "ADD_NEGATIVES",
                        "campaign_id": change.campaign_id,
                        "keywords": [
                            {"text": k["text"], "match_type": k["match_type"]}
                            for k in state["keywords"]
                            if k["match_type"] in MATCH
                        ],
                    }
                )
            elif isinstance(change, AddKeywords) and created:
                inverse_changes += [
                    {
                        "action": "SET_KEYWORD_STATUS",
                        "ad_group_id": change.ad_group_id,
                        "criterion_id": _tail(n)[-1],
                        "status": "REMOVED",
                    }
                    for n in created
                ]
            elif isinstance(change, SetKeywordStatus) and state.get("status"):
                if change.status == "REMOVED" and state.get("match_type") in MATCH:
                    inverse_changes.append(
                        {
                            "action": "ADD_KEYWORDS",
                            "ad_group_id": change.ad_group_id,
                            "keywords": [{"text": state["text"], "match_type": state["match_type"]}],
                        }
                    )
                elif state["status"] in {"ENABLED", "PAUSED"}:
                    inverse_changes.append(
                        {
                            "action": "SET_KEYWORD_STATUS",
                            "ad_group_id": change.ad_group_id,
                            "criterion_id": change.criterion_id,
                            "status": state["status"],
                        }
                    )
            elif isinstance(change, UpdateResponsiveSearchAd) and len(state.get("headlines", [])) >= 3:
                inverse_changes.append(
                    {
                        "action": "UPDATE_RSA",
                        "ad_id": change.ad_id,
                        "headlines": state["headlines"],
                        "descriptions": state["descriptions"],
                    }
                )
            elif isinstance(change, SetBidding) and state.get("bidding_strategy") in BIDDING_BACK:
                bidding: dict[str, Any] = {"type": BIDDING_BACK[state["bidding_strategy"]]}
                if bidding["type"] == "MAXIMIZE_CLICKS" and state.get("cpc_ceiling"):
                    bidding["cpc_ceiling"] = {"amount": state["cpc_ceiling"]}
                if bidding["type"] == "MAXIMIZE_CONVERSIONS" and state.get("target_cpa"):
                    bidding["target_cpa"] = {"amount": state["target_cpa"]}
                inverse_changes.append({"action": "SET_BIDDING", "campaign_id": change.campaign_id, "bidding": bidding})
            elif isinstance(change, SetEndDate) and "end_date" in state:
                inverse_changes.append(
                    {"action": "SET_END_DATE", "campaign_id": change.campaign_id, "end_date": state["end_date"]}
                )
            elif isinstance(change, SetGeoTargetType) and state.get("geo_target_type") in {
                "PRESENCE",
                "PRESENCE_OR_INTEREST",
            }:
                inverse_changes.append(
                    {
                        "action": "SET_GEO_TARGET_TYPE",
                        "campaign_id": change.campaign_id,
                        "positive": state["geo_target_type"],
                    }
                )
            elif isinstance(change, SetCampaignStatus) and state.get("status") in {"ENABLED", "PAUSED"}:
                inverse_changes.append(
                    {"action": "SET_CAMPAIGN_STATUS", "campaign_id": change.campaign_id, "status": state["status"]}
                )
            elif isinstance(change, SetBudget) and state.get("daily_budget"):
                inverse_changes.append(
                    {
                        "action": "SET_BUDGET",
                        "campaign_id": change.campaign_id,
                        "daily_budget": {"amount": state["daily_budget"], "currency": change.daily_budget.currency},
                    }
                )
        if not inverse_changes:
            return None
        return PlanKind.GOOGLE_CHANGE, {
            "customer_id": plan.customer_id,
            "rationale": "Reverter alterações aplicadas.",
            "changes": inverse_changes[:25],
        }

    if isinstance(plan, TikTokChangePlan):
        tiktok_changes: list[dict[str, Any]] = []
        for index, tchange in enumerate(plan.changes):
            state = before_changes[index] if index < len(before_changes) else {}
            if isinstance(tchange, TikTokSetCampaignStatus) and state.get("status") in {"ENABLE", "DISABLE"}:
                tiktok_changes.append(
                    {"action": "SET_CAMPAIGN_STATUS", "campaign_id": tchange.campaign_id, "status": state["status"]}
                )
            elif isinstance(tchange, TikTokSetCampaignBudget) and state.get("daily_budget"):
                tiktok_changes.append(
                    {
                        "action": "SET_CAMPAIGN_BUDGET",
                        "campaign_id": tchange.campaign_id,
                        "daily_budget": {"amount": state["daily_budget"], "currency": tchange.daily_budget.currency},
                    }
                )
        if not tiktok_changes:
            return None
        return PlanKind.TIKTOK_CHANGE, {
            "advertiser_id": plan.advertiser_id,
            "rationale": "Reverter alterações.",
            "changes": tiktok_changes,
        }
    return None
