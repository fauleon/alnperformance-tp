from dataclasses import dataclass
from decimal import Decimal
from ipaddress import ip_address
from urllib.parse import urlparse

from .domain import GoogleSearchCampaignPlan


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    violations: tuple[str, ...]
    snapshot: dict[str, object]


def validate_public_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return "A URL de destino deve usar HTTP ou HTTPS."
    host = parsed.hostname or ""
    if host in {"localhost", "metadata.google.internal"} or host.endswith(".local"):
        return "A URL de destino não pode apontar para rede local ou metadata."
    try:
        if ip_address(host).is_private or ip_address(host).is_link_local:
            return "A URL de destino não pode apontar para um IP privado."
    except ValueError:
        pass
    return None


def evaluate_plan(
    plan: GoogleSearchCampaignPlan,
    *,
    daily_budget_limit: Decimal,
    kill_switch: bool,
) -> PolicyDecision:
    violations: list[str] = []
    if plan.initial_status != "PAUSED":
        violations.append("Campanhas novas devem iniciar em PAUSED.")
    if plan.daily_budget.amount > daily_budget_limit:
        violations.append(f"Orçamento diário excede o limite de {daily_budget_limit}.")
    if error := validate_public_url(str(plan.final_url)):
        violations.append(error)
    if kill_switch:
        violations.append("Mutações externas estão desativadas pelo kill switch global.")
    return PolicyDecision(
        allowed=not violations,
        violations=tuple(violations),
        snapshot={
            "daily_budget_limit": str(daily_budget_limit),
            "required_initial_status": "PAUSED",
            "kill_switch": kill_switch,
        },
    )

