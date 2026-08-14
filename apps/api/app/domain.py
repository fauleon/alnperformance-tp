import json
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Money(StrictModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class DateRange(StrictModel):
    start: date
    end: date

    @field_validator("end")
    @classmethod
    def end_after_start(cls, value: date, info):
        start = info.data.get("start")
        if start and value < start:
            raise ValueError("end must be on or after start")
        return value


class BusinessProfile(StrictModel):
    company_name: str = Field(min_length=2, max_length=120)
    offer: str = Field(min_length=5, max_length=500)
    audience: str = Field(min_length=5, max_length=500)
    landing_page: HttpUrl
    objective: Literal["SALES", "LEADS", "TRAFFIC", "AWARENESS"] = "LEADS"
    total_budget: Money


class AdGroupPlan(StrictModel):
    name: str = Field(min_length=2, max_length=120)
    keywords: list[str] = Field(min_length=1, max_length=50)
    headlines: list[str] = Field(min_length=3, max_length=15)
    descriptions: list[str] = Field(min_length=2, max_length=4)


class GoogleSearchCampaignPlan(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    platform: Literal["GOOGLE_ADS"] = "GOOGLE_ADS"
    campaign_type: Literal["SEARCH"] = "SEARCH"
    customer_id: str = Field(pattern=r"^(?:demo|\d{10})$")
    name: str = Field(min_length=3, max_length=128)
    final_url: HttpUrl
    daily_budget: Money
    period: DateRange
    geo_targets: list[str] = Field(min_length=1)
    language_targets: list[str] = Field(min_length=1)
    conversion_goal_ids: list[str] = Field(min_length=1)
    ad_groups: list[AdGroupPlan] = Field(min_length=1)
    campaign_negatives: list[str] = Field(default_factory=list)
    initial_status: Literal["PAUSED"] = "PAUSED"


class PlanStatus(StrEnum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"
    CREATED_PAUSED = "CREATED_PAUSED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class PlanRecord(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    organization_id: UUID
    workspace_id: UUID
    version: int = 1
    status: PlanStatus = PlanStatus.DRAFT
    content: GoogleSearchCampaignPlan
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def canonical_hash(self) -> str:
        payload = self.content.model_dump(mode="json")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return sha256(canonical.encode()).hexdigest()


class Approval(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    plan_id: UUID
    plan_version: int
    plan_hash: str
    purpose: Literal["CREATE_PAUSED", "ACTIVATE"]
    approved_by: str
    approved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    policy_snapshot: dict[str, object]


class AuditEvent(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    organization_id: UUID
    workspace_id: UUID
    action: str
    actor: str
    resource_id: str
    result: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
