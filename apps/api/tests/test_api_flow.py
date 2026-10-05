from decimal import Decimal
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import AdConnection, AuditEvent, Job, Membership, Organization, User, Workspace
from app.providers import ProviderError
from app.security import hash_password
from app.worker import run_once

HEADERS = {"X-Requested-With": "alnia", "Origin": "http://localhost:3000"}
PASSWORD = "senha-forte-123"


async def make_owner(role: str = "owner", org_id: str | None = None) -> tuple[str, str, str]:
    """Creates a user (and, unless given, an organization + workspace). Returns (email, org_id, workspace_id)."""
    async with SessionLocal() as session:
        email = f"{uuid4().hex[:10]}@exemplo-aln.com.br"
        user = User(email=email, name="Pessoa Teste", password_hash=hash_password(PASSWORD))
        session.add(user)
        if not org_id:
            org = Organization(name=f"Org {uuid4().hex[:6]}")
            session.add(org)
            await session.flush()
            org_id = org.id
            session.add(Workspace(organization_id=org_id, name="Porto Imóveis", daily_budget_limit=Decimal("100.00")))
        await session.flush()
        session.add(Membership(user_id=user.id, organization_id=org_id, role=role))
        await session.commit()
        workspace = await session.scalar(select(Workspace).where(Workspace.organization_id == org_id))
        return email, org_id, workspace.id


async def client_for(email: str) -> httpx.AsyncClient:
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost:3000",
                               headers=HEADERS)
    response = await client.post("/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return client


async def drain() -> None:
    while await run_once():
        pass


async def connect_google(client: httpx.AsyncClient) -> str:
    start = await client.post("/v1/connections/google/start")
    assert start.status_code == 200, start.text
    query = parse_qs(urlparse(start.json()["authorization_url"]).query)
    assert query["code_challenge"][0]
    state = query["state"][0]
    callback = await client.get(f"/v1/connections/google/callback?code=abc&state={state}")
    assert callback.status_code == 303
    assert "status=connected" in callback.headers["location"]
    replay = await client.get(f"/v1/connections/google/callback?code=abc&state={state}")
    assert "reason=state" in replay.headers["location"], "state must be single use"

    listing = (await client.get("/v1/connections")).json()
    connection = listing["connections"][0]
    assert {a["external_id"] for a in connection["discovered_accounts"]} == {"9990001111", "1234567890"}
    manager = await client.post(f"/v1/connections/{connection['id']}/accounts", json={"external_id": "9990001111"})
    assert manager.status_code == 422, "MCC accounts cannot receive campaigns"
    linked = await client.post(f"/v1/connections/{connection['id']}/accounts", json={"external_id": "1234567890"})
    assert linked.status_code == 201
    assert linked.json()["login_customer_id"] == "9990001111"
    return linked.json()["id"]


def search_plan(budget: str = "50.00") -> dict:
    return {"name": f"Itahyê | Pesquisa | {uuid4().hex[:4]}", "final_url": "https://portoimoveis.com.br/itahye",
            "daily_budget": {"amount": budget, "currency": "BRL"}, "start_date": "2026-11-01",
            "geo_target_ids": ["1001773"], "bidding": {"type": "MAXIMIZE_CLICKS", "cpc_ceiling": {"amount": "4.00"}},
            "campaign_negatives": [{"text": "aluguel"}],
            "ad_groups": [{"name": "Casa Itahyê", "keywords": [{"text": "casa itahye", "match_type": "EXACT"}],
                           "ads": [{"headlines": ["Casa no Itahyê", "4 Suítes", "Agende Visita"],
                                    "descriptions": ["Casa com 4 suítes.", "Fale com um especialista."]}]}]}


async def test_requires_login_and_csrf():
    raw = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost:3000")
    assert (await raw.get("/v1/plans")).status_code == 401
    assert (await raw.post("/v1/auth/login", json={"email": "a@b.co", "password": "x"})).status_code == 403
    evil = await raw.post("/v1/auth/login", json={"email": "a@b.co", "password": "x"},
                          headers={"X-Requested-With": "alnia", "Origin": "https://evil.example"})
    assert evil.status_code == 403
    wrong = await raw.post("/v1/auth/login", json={"email": "nobody@exemplo-aln.com.br", "password": "x"}, headers=HEADERS)
    assert wrong.status_code == 401
    health = await raw.get("/health")
    assert health.json()["mutations"] == "disabled"
    assert health.headers["x-frame-options"] == "DENY"


async def test_full_google_flow(fake_google):
    email, org_id, workspace_id = await make_owner()
    client = await client_for(email)
    account_id = await connect_google(client)

    snapshot = await client.get(f"/v1/accounts/{account_id}/snapshot")
    assert snapshot.status_code == 200 and snapshot.json()["totals"]["clicks"] == 200
    audit = (await client.get(f"/v1/accounts/{account_id}/audit")).json()
    assert audit["score"] < 50 and audit["findings"][0]["severity"] == "critical"

    created = await client.post("/v1/plans", json={"kind": "GOOGLE_SEARCH_CAMPAIGN", "account_id": account_id,
                                                   "content": search_plan()})
    assert created.status_code == 201, created.text
    plan = created.json()
    plan_id = plan["id"]

    # Kill switch on (default): validation runs, but the plan is blocked.
    validation = (await client.post(f"/v1/plans/{plan_id}/validate")).json()
    assert validation["allowed"] is False and validation["remote_status"] == "ok"
    assert any("kill switch" in v for v in validation["violations"])
    blocked = await client.post(f"/v1/plans/{plan_id}/approve", json={"plan_hash": plan["plan_hash"]})
    assert blocked.status_code == 409

    settings.global_kill_switch = False
    settings.google_ads_mutations_enabled = True
    fake_google.validate_errors = ["Título inválido [ad_error.TOO_LONG]"]
    rejected = (await client.post(f"/v1/plans/{plan_id}/validate")).json()
    assert rejected["allowed"] is False and rejected["remote_status"] == "rejected"
    fake_google.validate_errors = []
    assert (await client.post(f"/v1/plans/{plan_id}/validate")).json()["allowed"] is True

    stale = await client.post(f"/v1/plans/{plan_id}/approve", json={"plan_hash": "0" * 64})
    assert stale.status_code == 409
    approved = await client.post(f"/v1/plans/{plan_id}/approve", json={"plan_hash": plan["plan_hash"]})
    assert approved.status_code == 200 and approved.json()["purpose"] == "CREATE_PAUSED"

    settings.google_ads_mutations_enabled = False
    locked = await client.post(f"/v1/plans/{plan_id}/execute", headers={"Idempotency-Key": f"k-{plan_id}"})
    assert locked.status_code == 423
    settings.google_ads_mutations_enabled = True

    key = {"Idempotency-Key": f"k-{plan_id}"}
    first = await client.post(f"/v1/plans/{plan_id}/execute", headers=key)
    second = await client.post(f"/v1/plans/{plan_id}/execute", headers=key)
    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    await drain()
    assert len(fake_google.executed) == 1, "same Idempotency-Key must execute once"

    detail = (await client.get(f"/v1/plans/{plan_id}")).json()
    assert detail["status"] == "EXECUTED"
    assert detail["executions"][0]["status"] == "SUCCEEDED"
    assert detail["executions"][0]["result"]["status"] == "CREATED_PAUSED"

    reuse = await client.post(f"/v1/plans/{plan_id}/execute", headers={"Idempotency-Key": f"other-{plan_id}"})
    assert reuse.status_code == 409, "an approval is consumed by one execution"

    reverted = await client.post(f"/v1/executions/{detail['executions'][0]['id']}/revert")
    assert reverted.status_code == 201 and reverted.json()["kind"] == "GOOGLE_CHANGE"

    async with SessionLocal() as session:
        events = list(await session.scalars(select(AuditEvent).where(AuditEvent.organization_id == org_id)))
        actions = {e.action for e in events}
        assert {"connection.connected", "plan.created", "plan.validated", "plan.approved", "plan.executed"} <= actions
        assert "ya29" not in str([e.details for e in events]) and "1//refresh" not in str([e.details for e in events])
        connection = await session.scalar(select(AdConnection).where(AdConnection.organization_id == org_id))
        assert connection.encrypted_refresh_token and "1//refresh" not in connection.encrypted_refresh_token


async def test_revision_invalidates_approval_and_budget_needs_confirmation(fake_google):
    settings.global_kill_switch = False
    settings.google_ads_mutations_enabled = True
    email, _, _ = await make_owner()
    client = await client_for(email)
    account_id = await connect_google(client)

    plan = (await client.post("/v1/plans", json={"kind": "GOOGLE_SEARCH_CAMPAIGN", "account_id": account_id,
                                                 "content": search_plan()})).json()
    await client.post(f"/v1/plans/{plan['id']}/validate")
    await client.post(f"/v1/plans/{plan['id']}/approve", json={"plan_hash": plan["plan_hash"]})
    revised = (await client.put(f"/v1/plans/{plan['id']}", json={"content": search_plan("60.00")})).json()
    assert revised["version"] == 2 and revised["status"] == "DRAFT"
    execute = await client.post(f"/v1/plans/{plan['id']}/execute", headers={"Idempotency-Key": f"r-{plan['id']}"})
    assert execute.status_code == 409, "approval of version 1 cannot execute version 2"

    over = (await client.post("/v1/plans", json={"kind": "GOOGLE_SEARCH_CAMPAIGN", "account_id": account_id,
                                                 "content": search_plan("500.00")})).json()
    validation = (await client.post(f"/v1/plans/{over['id']}/validate")).json()
    assert validation["allowed"] is False and "limite" in validation["violations"][0]

    budget = (await client.post("/v1/plans", json={"kind": "GOOGLE_CHANGE", "account_id": account_id, "content": {
        "changes": [{"action": "SET_BUDGET", "campaign_id": "111", "daily_budget": {"amount": "40.00"}}]}})).json()
    assert (await client.post(f"/v1/plans/{budget['id']}/validate")).json()["purpose"] == "BUDGET_CHANGE"
    unconfirmed = await client.post(f"/v1/plans/{budget['id']}/approve", json={"plan_hash": budget["plan_hash"]})
    assert unconfirmed.status_code == 422 and "dinheiro" in unconfirmed.text
    confirmed = await client.post(f"/v1/plans/{budget['id']}/approve",
                                  json={"plan_hash": budget["plan_hash"], "confirm_funds": True})
    assert confirmed.status_code == 200


async def test_tenant_isolation_and_roles(fake_google):
    owner_a, org_a, _ = await make_owner()
    client_a = await client_for(owner_a)
    account_a = await connect_google(client_a)
    plan_a = (await client_a.post("/v1/plans", json={"kind": "GOOGLE_SEARCH_CAMPAIGN", "account_id": account_a,
                                                     "content": search_plan()})).json()

    owner_b, _, workspace_b = await make_owner()
    client_b = await client_for(owner_b)
    assert (await client_b.get(f"/v1/plans/{plan_a['id']}")).status_code == 404
    assert (await client_b.get(f"/v1/accounts/{account_a}/snapshot")).status_code == 404
    _, _, workspace_a = await make_owner(org_id=org_a, role="viewer")
    spoof = await client_b.get("/v1/plans", headers={"X-Workspace-Id": workspace_a})
    assert spoof.status_code == 404, "a header cannot open another organization's workspace"
    assert (await client_b.get("/v1/plans")).json() == []

    viewer_email, _, _ = await make_owner(role="viewer", org_id=org_a)
    viewer = await client_for(viewer_email)
    assert (await viewer.get(f"/v1/plans/{plan_a['id']}")).status_code == 200
    forbidden = await viewer.post("/v1/plans", json={"kind": "GOOGLE_SEARCH_CAMPAIGN", "account_id": account_a,
                                                     "content": search_plan()})
    assert forbidden.status_code == 403
    assert (await viewer.post(f"/v1/plans/{plan_a['id']}/validate")).status_code == 403
    assert workspace_b


async def test_revoked_token_marks_reconnect(fake_google):
    email, org_id, _ = await make_owner()
    client = await client_for(email)
    account_id = await connect_google(client)
    async with SessionLocal() as session:
        connection = await session.scalar(select(AdConnection).where(AdConnection.organization_id == org_id))
        connection.access_token_expires_at = None  # force a refresh
        await session.commit()
    fake_google.refresh_error = ProviderError("revogado", needs_reconnect=True)
    response = await client.get(f"/v1/accounts/{account_id}/snapshot?refresh=true")
    assert response.status_code == 409 and response.json()["detail"]["needs_reconnect"] is True
    listing = (await client.get("/v1/connections")).json()
    assert listing["connections"][0]["status"] == "NEEDS_RECONNECT"

    disconnect = await client.delete(f"/v1/connections/{listing['connections'][0]['id']}")
    assert disconnect.status_code == 204
    assert fake_google.revoked == ["1//refresh"]
    assert (await client.get("/v1/accounts")).json() == []


async def test_transient_failures_retry_then_dead_letter(fake_google):
    settings.global_kill_switch = False
    settings.google_ads_mutations_enabled = True
    email, _, _ = await make_owner()
    client = await client_for(email)
    account_id = await connect_google(client)
    plan = (await client.post("/v1/plans", json={"kind": "GOOGLE_SEARCH_CAMPAIGN", "account_id": account_id,
                                                 "content": search_plan()})).json()
    await client.post(f"/v1/plans/{plan['id']}/validate")
    await client.post(f"/v1/plans/{plan['id']}/approve", json={"plan_hash": plan["plan_hash"]})
    execution = (await client.post(f"/v1/plans/{plan['id']}/execute",
                                   headers={"Idempotency-Key": f"t-{plan['id']}"})).json()
    fake_google.execute_error = ProviderError("RESOURCE_EXHAUSTED", retryable=True)

    async with SessionLocal() as session:
        job = await session.scalar(select(Job).where(Job.payload["execution_id"].as_string() == execution["id"]))
        job_id = job.id
    for _ in range(5):
        async with SessionLocal() as session:
            job = await session.get(Job, job_id)
            if job.status == "DEAD":
                break
            job.run_after = job.created_at  # skip the backoff wait
            await session.commit()
        await run_once()
    async with SessionLocal() as session:
        assert (await session.get(Job, job_id)).status == "DEAD"
    final = (await client.get(f"/v1/executions/{execution['id']}")).json()
    assert final["status"] == "FAILED" and "tentativas" in final["error"]


async def test_copilot_without_ai_uses_audit(fake_google):
    email, _, _ = await make_owner()
    client = await client_for(email)
    account_id = await connect_google(client)
    reply = (await client.post("/v1/copilot/chat", json={"account_id": account_id, "message": "o que corrigir?"})).json()
    assert reply["ai_enabled"] is False and "Nota da auditoria" in reply["reply"]
    assert reply["proposal"]["kind"] == "GOOGLE_CHANGE"
    created = await client.post("/v1/plans", json={"kind": "GOOGLE_CHANGE", "account_id": account_id,
                                                   "content": reply["proposal"]["content"], "source": "copilot"})
    assert created.status_code == 201


async def test_invitations_and_members():
    email, _, _ = await make_owner()
    client = await client_for(email)
    invite = await client.post("/v1/invitations", json={"email": "novo@exemplo-aln.com.br", "role": "viewer"})
    assert invite.status_code == 201
    token = invite.json()["invite_url"].rsplit("/", 1)[-1]
    guest = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost:3000", headers=HEADERS)
    info = (await guest.get(f"/v1/invitations/{token}")).json()
    assert info["role"] == "viewer" and info["existing_user"] is False
    weak = await guest.post(f"/v1/invitations/{token}/accept", json={"name": "Novo", "password": "curta"})
    assert weak.status_code == 422
    accepted = await guest.post(f"/v1/invitations/{token}/accept", json={"name": "Novo", "password": PASSWORD + "x"})
    assert accepted.status_code == 200 and accepted.json()["workspaces"][0]["role"] == "viewer"
    assert (await guest.get(f"/v1/invitations/{token}")).status_code == 404, "invitations are single use"
    members = (await client.get("/v1/members")).json()["members"]
    assert {m["role"] for m in members} == {"owner", "viewer"}


@pytest.mark.parametrize("attempt", range(1))
async def test_login_rate_limit(attempt):
    raw = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost:3000", headers=HEADERS)
    codes = [(await raw.post("/v1/auth/login", json={"email": "alvo@exemplo-aln.com.br", "password": "x"})).status_code
             for _ in range(10)]
    assert codes[-1] == 429
