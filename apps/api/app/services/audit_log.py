import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditEvent
from ..security import redact

log = logging.getLogger("aln.audit")


def record(
    session: AsyncSession,
    *,
    organization_id: str,
    workspace_id: str | None,
    action: str,
    actor_id: str | None,
    actor_name: str,
    resource_type: str,
    resource_id: str,
    result: str,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    """Adds an audit event to the current transaction. Details are always redacted first."""
    event = AuditEvent(
        organization_id=organization_id,
        workspace_id=workspace_id,
        action=action,
        actor_id=actor_id,
        actor_name=actor_name[:120],
        resource_type=resource_type,
        resource_id=str(resource_id)[:120],
        result=result[:40],
        details=redact(details) if details else None,
    )
    session.add(event)
    log.info(
        "audit",
        extra={"action": action, "result": result, "resource": resource_type, "organization_id": organization_id},
    )
    return event
