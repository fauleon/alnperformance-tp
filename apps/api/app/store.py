from uuid import UUID

from .domain import Approval, AuditEvent, PlanRecord


class InMemoryStore:
    def __init__(self) -> None:
        self.plans: dict[UUID, PlanRecord] = {}
        self.approvals: dict[UUID, Approval] = {}
        self.audits: list[AuditEvent] = []
        self.idempotency: dict[str, dict[str, object]] = {}


store = InMemoryStore()

