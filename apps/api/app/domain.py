"""Versioned, strict contracts. Everything the AI or a person proposes must parse into one of these."""

import json
from datetime import date
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, field_validator, model_validator

GOOGLE_RSA_HEADLINE_MAX = 30
GOOGLE_RSA_DESCRIPTION_MAX = 90
FUNDS_CONFIRMATION_TEXT = "O dinheiro já está disponível. Deseja aplicar?"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Provider(StrEnum):
    GOOGLE_ADS = "GOOGLE_ADS"
    TIKTOK_ADS = "TIKTOK_ADS"


class PlanKind(StrEnum):
    GOOGLE_SEARCH_CAMPAIGN = "GOOGLE_SEARCH_CAMPAIGN"
    GOOGLE_CHANGE = "GOOGLE_CHANGE"
    TIKTOK_CAMPAIGN = "TIKTOK_CAMPAIGN"
    TIKTOK_CHANGE = "TIKTOK_CHANGE"


class PlanStatus(StrEnum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    BLOCKED = "BLOCKED"
    APPROVED = "APPROVED"
    QUEUED = "QUEUED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


class ApprovalPurpose(StrEnum):
    CREATE_PAUSED = "CREATE_PAUSED"
    APPLY_CHANGE = "APPLY_CHANGE"
    ACTIVATE = "ACTIVATE"
    BUDGET_CHANGE = "BUDGET_CHANGE"


class Money(StrictModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="BRL", pattern=r"^[A-Z]{3}$")


CustomerId = Annotated[str, Field(pattern=r"^\d{10}$")]
NumericId = Annotated[str, Field(pattern=r"^\d{1,20}$")]


def canonical_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return sha256(canonical.encode()).hexdigest()


# --------------------------------------------------------------------------- Google: new campaign


class MatchType(StrEnum):
    EXACT = "EXACT"
    PHRASE = "PHRASE"
    BROAD = "BROAD"


class Keyword(StrictModel):
    text: str = Field(min_length=1, max_length=80)
    match_type: MatchType = MatchType.PHRASE

    @field_validator("text")
    @classmethod
    def clean(cls, value: str) -> str:
        value = " ".join(value.lower().split())
        if any(char in value for char in "!@%,*()=;{}<>[]|^~`"):
            raise ValueError("palavra-chave com caractere não permitido pelo Google Ads")
        if len(value.split()) > 10:
            raise ValueError("palavra-chave com mais de 10 palavras")
        return value


class ResponsiveSearchAd(StrictModel):
    headlines: list[Annotated[str, Field(min_length=1, max_length=GOOGLE_RSA_HEADLINE_MAX)]] = Field(
        min_length=3, max_length=15
    )
    descriptions: list[Annotated[str, Field(min_length=1, max_length=GOOGLE_RSA_DESCRIPTION_MAX)]] = Field(
        min_length=2, max_length=4
    )
    path1: str | None = Field(default=None, max_length=15)
    path2: str | None = Field(default=None, max_length=15)
    final_url: HttpUrl | None = None

    @model_validator(mode="after")
    def unique_texts(self) -> "ResponsiveSearchAd":
        if len({h.lower() for h in self.headlines}) != len(self.headlines):
            raise ValueError("títulos repetidos no anúncio")
        if len({d.lower() for d in self.descriptions}) != len(self.descriptions):
            raise ValueError("descrições repetidas no anúncio")
        if self.path2 and not self.path1:
            raise ValueError("path2 exige path1")
        return self


class AdGroupPlan(StrictModel):
    name: str = Field(min_length=2, max_length=120)
    keywords: list[Keyword] = Field(min_length=1, max_length=80)
    negative_keywords: list[Keyword] = Field(default_factory=list, max_length=200)
    ads: list[ResponsiveSearchAd] = Field(min_length=1, max_length=3)
    cpc_bid: Money | None = None


class BiddingType(StrEnum):
    MAXIMIZE_CLICKS = "MAXIMIZE_CLICKS"
    MAXIMIZE_CONVERSIONS = "MAXIMIZE_CONVERSIONS"
    MANUAL_CPC = "MANUAL_CPC"


class Bidding(StrictModel):
    type: BiddingType = BiddingType.MAXIMIZE_CLICKS
    cpc_ceiling: Money | None = None
    target_cpa: Money | None = None

    @model_validator(mode="after")
    def coherent(self) -> "Bidding":
        if self.target_cpa and self.type != BiddingType.MAXIMIZE_CONVERSIONS:
            raise ValueError("CPA desejado só vale para Maximizar Conversões")
        if self.cpc_ceiling and self.type != BiddingType.MAXIMIZE_CLICKS:
            raise ValueError("teto de CPC só vale para Maximizar Cliques")
        return self


class Sitelink(StrictModel):
    text: str = Field(min_length=1, max_length=25)
    description1: str | None = Field(default=None, max_length=35)
    description2: str | None = Field(default=None, max_length=35)
    final_url: HttpUrl

    @model_validator(mode="after")
    def both_descriptions(self) -> "Sitelink":
        if bool(self.description1) != bool(self.description2):
            raise ValueError("o sitelink precisa das duas descrições ou de nenhuma")
        return self


class StructuredSnippet(StrictModel):
    header: Literal[
        "Amenities",
        "Brands",
        "Courses",
        "Destinations",
        "Featured hotels",
        "Insurance coverage",
        "Models",
        "Neighborhoods",
        "Service catalog",
        "Shows",
        "Styles",
        "Types",
    ]
    values: list[Annotated[str, Field(min_length=1, max_length=25)]] = Field(min_length=3, max_length=10)


class GoogleSearchCampaignPlan(StrictModel):
    schema_version: Literal["2.0"] = "2.0"
    customer_id: CustomerId
    name: str = Field(min_length=3, max_length=128)
    final_url: HttpUrl
    daily_budget: Money
    start_date: date
    end_date: date | None = None
    geo_target_ids: list[NumericId] = Field(min_length=1, max_length=50)
    geo_target_names: list[str] = Field(default_factory=list, max_length=50)
    language_ids: list[NumericId] = Field(default_factory=lambda: ["1014"], min_length=1, max_length=10)
    bidding: Bidding = Field(default_factory=Bidding)
    ad_groups: list[AdGroupPlan] = Field(min_length=1, max_length=20)
    campaign_negatives: list[Keyword] = Field(default_factory=list, max_length=500)
    sitelinks: list[Sitelink] = Field(default_factory=list, max_length=20)
    callouts: list[Annotated[str, Field(min_length=1, max_length=25)]] = Field(default_factory=list, max_length=20)
    structured_snippet: StructuredSnippet | None = None
    business_name: str | None = Field(default=None, max_length=25)
    initial_status: Literal["PAUSED"] = "PAUSED"

    @model_validator(mode="after")
    def dates(self) -> "GoogleSearchCampaignPlan":
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("a data de término precisa ser igual ou posterior ao início")
        if len(self.sitelinks) == 1:
            raise ValueError("o Google exige pelo menos 2 sitelinks quando houver sitelinks")
        return self


# --------------------------------------------------------------------------- Google: edits


class SetNetworks(StrictModel):
    action: Literal["SET_NETWORKS"] = "SET_NETWORKS"
    campaign_id: NumericId
    search_partners: bool
    display_network: bool


class AddNegatives(StrictModel):
    action: Literal["ADD_NEGATIVES"] = "ADD_NEGATIVES"
    campaign_id: NumericId
    keywords: list[Keyword] = Field(min_length=1, max_length=200)


class RemoveNegatives(StrictModel):
    action: Literal["REMOVE_NEGATIVES"] = "REMOVE_NEGATIVES"
    campaign_id: NumericId
    criterion_ids: list[NumericId] = Field(min_length=1, max_length=200)


class SetKeywordStatus(StrictModel):
    action: Literal["SET_KEYWORD_STATUS"] = "SET_KEYWORD_STATUS"
    ad_group_id: NumericId
    criterion_id: NumericId
    status: Literal["ENABLED", "PAUSED", "REMOVED"]


class AddKeywords(StrictModel):
    action: Literal["ADD_KEYWORDS"] = "ADD_KEYWORDS"
    ad_group_id: NumericId
    keywords: list[Keyword] = Field(min_length=1, max_length=80)


class UpdateResponsiveSearchAd(StrictModel):
    action: Literal["UPDATE_RSA"] = "UPDATE_RSA"
    ad_id: NumericId
    headlines: list[Annotated[str, Field(min_length=1, max_length=GOOGLE_RSA_HEADLINE_MAX)]] = Field(
        min_length=3, max_length=15
    )
    descriptions: list[Annotated[str, Field(min_length=1, max_length=GOOGLE_RSA_DESCRIPTION_MAX)]] = Field(
        min_length=2, max_length=4
    )


class SetBidding(StrictModel):
    action: Literal["SET_BIDDING"] = "SET_BIDDING"
    campaign_id: NumericId
    bidding: Bidding


class SetEndDate(StrictModel):
    action: Literal["SET_END_DATE"] = "SET_END_DATE"
    campaign_id: NumericId
    end_date: date | None


class SetGeoTargetType(StrictModel):
    action: Literal["SET_GEO_TARGET_TYPE"] = "SET_GEO_TARGET_TYPE"
    campaign_id: NumericId
    positive: Literal["PRESENCE", "PRESENCE_OR_INTEREST"] = "PRESENCE"


class SetCampaignStatus(StrictModel):
    action: Literal["SET_CAMPAIGN_STATUS"] = "SET_CAMPAIGN_STATUS"
    campaign_id: NumericId
    status: Literal["PAUSED", "ENABLED"]


class SetBudget(StrictModel):
    action: Literal["SET_BUDGET"] = "SET_BUDGET"
    campaign_id: NumericId
    daily_budget: Money


class CreateConversionAction(StrictModel):
    action: Literal["CREATE_CONVERSION_ACTION"] = "CREATE_CONVERSION_ACTION"
    name: str = Field(min_length=3, max_length=100)
    category: Literal[
        "SUBMIT_LEAD_FORM",
        "CONTACT",
        "PHONE_CALL_LEAD",
        "BOOK_APPOINTMENT",
        "QUALIFIED_LEAD",
        "PURCHASE",
        "SIGNUP",
        "REQUEST_QUOTE",
    ] = "SUBMIT_LEAD_FORM"
    counting: Literal["ONE_PER_CLICK", "MANY_PER_CLICK"] = "ONE_PER_CLICK"
    default_value: Money | None = None
    primary: bool = True


class RemoveCampaign(StrictModel):
    """Only produced by "Reverter" on a campaign this system created."""

    action: Literal["REMOVE_CAMPAIGN"] = "REMOVE_CAMPAIGN"
    campaign_id: NumericId


GoogleChange = Annotated[
    SetNetworks
    | AddNegatives
    | RemoveNegatives
    | SetKeywordStatus
    | AddKeywords
    | UpdateResponsiveSearchAd
    | SetBidding
    | SetEndDate
    | SetGeoTargetType
    | SetCampaignStatus
    | SetBudget
    | CreateConversionAction
    | RemoveCampaign,
    Field(discriminator="action"),
]


class GoogleChangePlan(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    customer_id: CustomerId
    rationale: str = Field(default="", max_length=2000)
    changes: list[GoogleChange] = Field(min_length=1, max_length=25)


# --------------------------------------------------------------------------- TikTok


class TikTokAdGroupPlan(StrictModel):
    name: str = Field(min_length=2, max_length=100)
    location_ids: list[NumericId] = Field(min_length=1, max_length=50)
    age_groups: list[Literal["AGE_13_17", "AGE_18_24", "AGE_25_34", "AGE_35_44", "AGE_45_54", "AGE_55_100"]] = Field(
        default_factory=list
    )
    gender: Literal["GENDER_UNLIMITED", "GENDER_MALE", "GENDER_FEMALE"] = "GENDER_UNLIMITED"
    language_codes: list[str] = Field(default_factory=list, max_length=10)
    optimization_goal: Literal["CLICK", "CONVERT", "REACH", "LEAD_GENERATION", "SHOW"] = "CLICK"
    pixel_id: NumericId | None = None
    optimization_event: str | None = Field(default=None, max_length=60)
    start_date: date
    end_date: date | None = None

    @model_validator(mode="after")
    def conversion_needs_pixel(self) -> "TikTokAdGroupPlan":
        if self.optimization_goal == "CONVERT" and not (self.pixel_id and self.optimization_event):
            raise ValueError("otimização por conversão exige pixel e evento")
        if "AGE_13_17" in self.age_groups:
            raise ValueError("anúncios para menores de 18 anos não são permitidos por esta plataforma")
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("a data de término precisa ser igual ou posterior ao início")
        return self


class TikTokCampaignPlan(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    advertiser_id: NumericId
    name: str = Field(min_length=3, max_length=512)
    objective: Literal["TRAFFIC", "LEAD_GENERATION", "WEB_CONVERSIONS", "REACH", "VIDEO_VIEWS", "ENGAGEMENT"]
    landing_page: HttpUrl
    daily_budget: Money
    ad_group: TikTokAdGroupPlan
    initial_status: Literal["DISABLE"] = "DISABLE"


class TikTokSetCampaignStatus(StrictModel):
    action: Literal["SET_CAMPAIGN_STATUS"] = "SET_CAMPAIGN_STATUS"
    campaign_id: NumericId
    status: Literal["DISABLE", "ENABLE"]


class TikTokSetAdGroupStatus(StrictModel):
    action: Literal["SET_ADGROUP_STATUS"] = "SET_ADGROUP_STATUS"
    adgroup_id: NumericId
    status: Literal["DISABLE", "ENABLE"]


class TikTokSetCampaignBudget(StrictModel):
    action: Literal["SET_CAMPAIGN_BUDGET"] = "SET_CAMPAIGN_BUDGET"
    campaign_id: NumericId
    daily_budget: Money


TikTokChange = Annotated[
    TikTokSetCampaignStatus | TikTokSetAdGroupStatus | TikTokSetCampaignBudget, Field(discriminator="action")
]


class TikTokChangePlan(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    advertiser_id: NumericId
    rationale: str = Field(default="", max_length=2000)
    changes: list[TikTokChange] = Field(min_length=1, max_length=25)


PLAN_MODELS: dict[PlanKind, type[StrictModel]] = {
    PlanKind.GOOGLE_SEARCH_CAMPAIGN: GoogleSearchCampaignPlan,
    PlanKind.GOOGLE_CHANGE: GoogleChangePlan,
    PlanKind.TIKTOK_CAMPAIGN: TikTokCampaignPlan,
    PlanKind.TIKTOK_CHANGE: TikTokChangePlan,
}

PLAN_PROVIDER: dict[PlanKind, Provider] = {
    PlanKind.GOOGLE_SEARCH_CAMPAIGN: Provider.GOOGLE_ADS,
    PlanKind.GOOGLE_CHANGE: Provider.GOOGLE_ADS,
    PlanKind.TIKTOK_CAMPAIGN: Provider.TIKTOK_ADS,
    PlanKind.TIKTOK_CHANGE: Provider.TIKTOK_ADS,
}

AnyPlan = GoogleSearchCampaignPlan | GoogleChangePlan | TikTokCampaignPlan | TikTokChangePlan


def parse_plan(kind: PlanKind, content: dict[str, Any]) -> AnyPlan:
    return TypeAdapter(PLAN_MODELS[kind]).validate_python(content)  # type: ignore[return-value]


def dump_plan(plan: BaseModel) -> dict[str, Any]:
    return plan.model_dump(mode="json", exclude_none=False)


def is_activation(change: BaseModel) -> bool:
    if isinstance(change, SetCampaignStatus):
        return change.status == "ENABLED"
    if isinstance(change, TikTokSetCampaignStatus | TikTokSetAdGroupStatus):
        return change.status == "ENABLE"
    return False


def is_budget_change(change: BaseModel) -> bool:
    return isinstance(change, SetBudget | TikTokSetCampaignBudget)


def approval_purpose(plan: AnyPlan) -> ApprovalPurpose:
    """Activation and money are always their own approvals (policy blocks mixing them with other edits)."""
    if isinstance(plan, GoogleChangePlan | TikTokChangePlan):
        if any(isinstance(c, SetBudget | TikTokSetCampaignBudget) for c in plan.changes):
            return ApprovalPurpose.BUDGET_CHANGE
        if any(is_activation(c) for c in plan.changes):
            return ApprovalPurpose.ACTIVATE
        return ApprovalPurpose.APPLY_CHANGE
    return ApprovalPurpose.CREATE_PAUSED


def plan_daily_budget(plan: AnyPlan) -> Money | None:
    if isinstance(plan, GoogleSearchCampaignPlan | TikTokCampaignPlan):
        return plan.daily_budget
    budgets = [c.daily_budget for c in plan.changes if isinstance(c, SetBudget | TikTokSetCampaignBudget)]
    return max(budgets, key=lambda money: money.amount) if budgets else None


def plan_account_id(plan: AnyPlan) -> str:
    if isinstance(plan, GoogleSearchCampaignPlan | GoogleChangePlan):
        return plan.customer_id
    return plan.advertiser_id
