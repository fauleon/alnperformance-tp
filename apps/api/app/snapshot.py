"""Provider-neutral view of an ad account. Gateways fill it; audit, copilot and the panel read it."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class Metrics(BaseModel):
    impressions: int = 0
    clicks: int = 0
    cost: Decimal = Decimal("0")
    conversions: Decimal = Decimal("0")
    conversion_value: Decimal = Decimal("0")

    @property
    def ctr(self) -> Decimal | None:
        return (Decimal(self.clicks) / self.impressions * 100).quantize(Decimal("0.01")) if self.impressions else None

    @property
    def cpc(self) -> Decimal | None:
        return (self.cost / self.clicks).quantize(Decimal("0.01")) if self.clicks else None

    @property
    def cost_per_conversion(self) -> Decimal | None:
        return (self.cost / self.conversions).quantize(Decimal("0.01")) if self.conversions else None

    def add(self, other: "Metrics") -> "Metrics":
        return Metrics(
            impressions=self.impressions + other.impressions,
            clicks=self.clicks + other.clicks,
            cost=self.cost + other.cost,
            conversions=self.conversions + other.conversions,
            conversion_value=self.conversion_value + other.conversion_value,
        )

    def public(self) -> dict[str, object]:
        return {
            **self.model_dump(mode="json"),
            "ctr": _s(self.ctr),
            "cpc": _s(self.cpc),
            "cost_per_conversion": _s(self.cost_per_conversion),
        }


def _s(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


class KeywordInfo(BaseModel):
    criterion_id: str
    text: str
    match_type: str
    status: str
    quality_score: int | None = None
    metrics: Metrics = Field(default_factory=Metrics)


class AdInfo(BaseModel):
    ad_id: str
    type: str
    status: str
    headlines: list[str] = Field(default_factory=list)
    descriptions: list[str] = Field(default_factory=list)
    ad_strength: str | None = None
    final_urls: list[str] = Field(default_factory=list)
    metrics: Metrics = Field(default_factory=Metrics)


class AdGroupInfo(BaseModel):
    ad_group_id: str
    name: str
    status: str
    keywords: list[KeywordInfo] = Field(default_factory=list)
    ads: list[AdInfo] = Field(default_factory=list)
    metrics: Metrics = Field(default_factory=Metrics)


class NegativeInfo(BaseModel):
    criterion_id: str | None = None
    text: str
    match_type: str
    source: str = "campaign"  # campaign | shared_list


class AssetInfo(BaseModel):
    type: str  # SITELINK | CALLOUT | STRUCTURED_SNIPPET | ...
    text: str
    level: str = "campaign"


class CampaignInfo(BaseModel):
    campaign_id: str
    name: str
    status: str
    channel: str
    bidding_strategy: str | None = None
    daily_budget: Decimal | None = None
    budget_id: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    search_network: bool | None = None
    search_partners: bool | None = None
    display_network: bool | None = None
    geo_target_type: str | None = None
    geo_targets: list[str] = Field(default_factory=list)
    negatives: list[NegativeInfo] = Field(default_factory=list)
    assets: list[AssetInfo] = Field(default_factory=list)
    ad_groups: list[AdGroupInfo] = Field(default_factory=list)
    metrics: Metrics = Field(default_factory=Metrics)
    objective: str | None = None  # TikTok
    has_pixel: bool | None = None  # TikTok


class ConversionActionInfo(BaseModel):
    conversion_action_id: str
    name: str
    status: str
    category: str | None = None
    primary: bool = True
    conversions: Decimal = Decimal("0")


class SearchTermInfo(BaseModel):
    term: str
    campaign_id: str
    ad_group_id: str | None = None
    status: str | None = None
    metrics: Metrics = Field(default_factory=Metrics)


class DailyPoint(BaseModel):
    day: date
    campaign_id: str | None = None
    metrics: Metrics = Field(default_factory=Metrics)


class AccountSnapshot(BaseModel):
    provider: str
    account_id: str
    account_name: str | None = None
    currency: str | None = None
    period_start: date
    period_end: date
    campaigns: list[CampaignInfo] = Field(default_factory=list)
    conversion_actions: list[ConversionActionInfo] = Field(default_factory=list)
    enhanced_conversions_for_leads: bool | None = None
    search_terms: list[SearchTermInfo] = Field(default_factory=list)
    daily: list[DailyPoint] = Field(default_factory=list)

    def totals(self) -> Metrics:
        total = Metrics()
        for campaign in self.campaigns:
            total = total.add(campaign.metrics)
        return total

    def by_day(self) -> list[dict[str, object]]:
        days: dict[date, Metrics] = {}
        for point in self.daily:
            days[point.day] = days.get(point.day, Metrics()).add(point.metrics)
        return [{"day": day.isoformat(), **metrics.public()} for day, metrics in sorted(days.items())]
