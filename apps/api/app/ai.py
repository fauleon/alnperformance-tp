"""Copilot. The model only proposes; every proposal is parsed, policy-checked and approved by a person.

It never receives tokens, e-mails or credentials: only the aggregated account snapshot and audit findings.
"""

import json
import logging
from typing import Any

import httpx
from pydantic import ValidationError

from .audit_rules import AuditReport
from .config import settings
from .domain import PlanKind, dump_plan, parse_plan
from .snapshot import AccountSnapshot

log = logging.getLogger("aln.ai")
OPENAI_URL = "https://api.openai.com/v1/responses"

SYSTEM_PROMPT = """Você é o copiloto do ALN Hub ia, a plataforma de gestão de mídia paga da ALN Performance.
Plataformas: Google Ads (Rede de Pesquisa) e TikTok Ads.

Regras:
- Responda em português do Brasil, de forma direta, com números do contexto. Nunca invente métricas, metas ou dados.
  Se faltar dado, diga qual dado falta.
- Você não executa nada. Pode sugerir no máximo UMA proposta, que será validada pela política e aprovada por uma pessoa.
- Mudança de orçamento e ativação de campanha são sempre propostas separadas, sem nenhuma outra alteração junto.
- Prefira correspondência de frase ou exata. Negativas sempre que houver termos sem conversão.
- Títulos de anúncio até 30 caracteres; descrições até 90; sem repetir texto; sem contradizer números.

Formato da proposta (proposal_json, texto JSON; use "{}" e proposal_kind "NONE" quando não houver proposta):
- GOOGLE_CHANGE: {"rationale": str, "changes": [ação, ...]} com ações:
  {"action":"SET_NETWORKS","campaign_id":"123","search_partners":false,"display_network":false}
  {"action":"ADD_NEGATIVES","campaign_id":"123","keywords":[{"text":"grátis","match_type":"PHRASE"}]}
  {"action":"SET_KEYWORD_STATUS","ad_group_id":"1","criterion_id":"2","status":"PAUSED"}
  {"action":"ADD_KEYWORDS","ad_group_id":"1","keywords":[{"text":"...","match_type":"EXACT"}]}
  {"action":"UPDATE_RSA","ad_id":"9","headlines":["..."],"descriptions":["..."]}
  {"action":"SET_BIDDING","campaign_id":"123","bidding":{"type":"MAXIMIZE_CLICKS","cpc_ceiling":{"amount":"3.50","currency":"BRL"}}}
  {"action":"SET_END_DATE","campaign_id":"123","end_date":"2026-12-31"}
  {"action":"SET_GEO_TARGET_TYPE","campaign_id":"123","positive":"PRESENCE"}
  {"action":"SET_CAMPAIGN_STATUS","campaign_id":"123","status":"PAUSED"}
  {"action":"SET_BUDGET","campaign_id":"123","daily_budget":{"amount":"50.00","currency":"BRL"}}
- TIKTOK_CHANGE: {"rationale": str, "changes": [{"action":"SET_CAMPAIGN_STATUS","campaign_id":"1","status":"DISABLE"},
  {"action":"SET_CAMPAIGN_BUDGET","campaign_id":"1","daily_budget":{"amount":"100.00","currency":"BRL"}}]}
"""

PLAN_PROMPT = """Crie uma campanha de Pesquisa do Google Ads a partir do briefing. Devolva em plan_json um objeto com:
name, final_url, daily_budget {amount, currency}, start_date, end_date (ou null), geo_target_ids, geo_target_names,
language_ids ["1014"], bidding {"type":"MAXIMIZE_CLICKS"}, ad_groups [{name, keywords [{text, match_type PHRASE|EXACT}],
negative_keywords [], ads [{headlines (10 a 15, até 30 caracteres), descriptions (4, até 90), path1, path2}]}],
campaign_negatives [{text, match_type}], callouts (até 25 caracteres), sitelinks [] (só se o briefing trouxer URLs).
Agrupe por intenção (no máximo 5 grupos). Use somente fatos do briefing. Nada de preços ou promessas não informados."""

REPLY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["reply", "proposal_kind", "proposal_json"],
    "properties": {
        "reply": {"type": "string"},
        "proposal_kind": {"type": "string", "enum": ["NONE", "GOOGLE_CHANGE", "TIKTOK_CHANGE"]},
        "proposal_json": {"type": "string"},
    },
}
PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["notes", "plan_json"],
    "properties": {"notes": {"type": "string"}, "plan_json": {"type": "string"}},
}


def enabled() -> bool:
    return bool(settings.openai_api_key)


def account_context(snapshot: AccountSnapshot | None, report: AuditReport | None) -> dict[str, Any]:
    if not snapshot:
        return {"conta": None}
    return {
        "plataforma": snapshot.provider,
        "conta": snapshot.account_id,
        "moeda": snapshot.currency,
        "periodo": [snapshot.period_start.isoformat(), snapshot.period_end.isoformat()],
        "totais": snapshot.totals().public(),
        "campanhas": [
            {
                "id": c.campaign_id,
                "nome": c.name,
                "status": c.status,
                "lance": c.bidding_strategy,
                "orcamento_diario": str(c.daily_budget) if c.daily_budget is not None else None,
                "parceiros": c.search_partners,
                "display": c.display_network,
                "geo": c.geo_target_type,
                "negativas": len(c.negatives),
                "metricas": c.metrics.public(),
                "grupos": [
                    {
                        "id": g.ad_group_id,
                        "nome": g.name,
                        "palavras": [
                            {
                                "id": k.criterion_id,
                                "texto": k.text,
                                "tipo": k.match_type,
                                "status": k.status,
                                "custo": str(k.metrics.cost),
                                "conv": str(k.metrics.conversions),
                            }
                            for k in g.keywords[:25]
                        ],
                        "anuncios": [
                            {"id": a.ad_id, "forca": a.ad_strength, "titulos": a.headlines[:15]} for a in g.ads[:3]
                        ],
                    }
                    for g in c.ad_groups[:8]
                ],
            }
            for c in snapshot.campaigns[:15]
        ],
        "conversoes": [
            {"nome": a.name, "principal": a.primary, "status": a.status, "conversoes": str(a.conversions)}
            for a in snapshot.conversion_actions[:20]
        ],
        "termos_de_pesquisa": [
            {
                "termo": t.term,
                "campanha": t.campaign_id,
                "cliques": t.metrics.clicks,
                "custo": str(t.metrics.cost),
                "conv": str(t.metrics.conversions),
            }
            for t in snapshot.search_terms[:40]
        ],
        "auditoria": {
            "nota": report.score,
            "achados": [
                {"regra": f.rule, "gravidade": f.severity, "titulo": f.title, "campanha": f.campaign_name}
                for f in report.findings[:20]
            ],
        }
        if report
        else None,
    }


async def _call(input_items: list[dict[str, str]], schema: dict[str, Any], name: str) -> dict[str, Any]:
    body = {
        "model": settings.openai_model,
        "input": input_items,
        "store": False,
        "max_output_tokens": 6000,
        "text": {"format": {"type": "json_schema", "name": name, "schema": schema, "strict": True}},
    }
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            OPENAI_URL, json=body, headers={"Authorization": f"Bearer {settings.openai_api_key}"}
        )
    if response.is_error:
        log.warning("ai.error", extra={"status": response.status_code})
        raise RuntimeError("O copiloto de IA está indisponível agora.")
    data = response.json()
    text = "".join(
        part.get("text", "")
        for item in data.get("output", [])
        if item.get("type") == "message"
        for part in item.get("content", [])
        if part.get("type") == "output_text"
    )
    return json.loads(text)


def check_proposal(kind: str, raw: str, account_external_id: str) -> dict[str, Any] | None:
    """Parses what the model proposed. Invalid proposals are dropped, with the reason."""
    if kind not in {"GOOGLE_CHANGE", "TIKTOK_CHANGE", "GOOGLE_SEARCH_CAMPAIGN"}:
        return None
    try:
        content = json.loads(raw or "{}")
        key = "advertiser_id" if kind.startswith("TIKTOK") else "customer_id"
        model = parse_plan(PlanKind(kind), {**content, key: account_external_id})
    except (ValueError, ValidationError) as error:
        return {
            "kind": kind,
            "content": None,
            "error": f"Proposta descartada por não passar na validação: {error}"[:600],
        }
    return {"kind": kind, "content": dump_plan(model), "error": None}


def fallback_reply(message: str, snapshot: AccountSnapshot | None, report: AuditReport | None) -> dict[str, Any]:
    if not snapshot:
        return {
            "reply": "Conecte uma conta do Google Ads ou do TikTok Ads em Integrações para eu analisar dados reais.",
            "proposal": None,
        }
    totals = snapshot.totals()
    lines = [
        f"Nos últimos dias ({snapshot.period_start:%d/%m} a {snapshot.period_end:%d/%m}) a conta teve "
        f"{totals.impressions} impressões, {totals.clicks} cliques, custo de {totals.cost} {snapshot.currency or ''} "
        f"e {totals.conversions} conversões."
    ]
    proposal = None
    if report and report.findings:
        lines.append(f"Nota da auditoria: {report.score}/100. Principais pontos:")
        for finding in report.findings[:5]:
            where = f" ({finding.campaign_name})" if finding.campaign_name else ""
            lines.append(f"• {finding.title}{where}: {finding.fix}")
        first = next((f for f in report.findings if f.proposal), None)
        if first:
            kind = "GOOGLE_CHANGE" if snapshot.provider == "GOOGLE_ADS" else "TIKTOK_CHANGE"
            proposal = {"kind": kind, "content": first.proposal, "error": None}
            lines.append(f"Preparei uma proposta para o primeiro item corrigível: {first.title}.")
    else:
        lines.append("A auditoria não encontrou problemas nas regras atuais.")
    lines.append("(Modo sem IA: configure OPENAI_API_KEY para conversar livremente.)")
    return {"reply": "\n".join(lines), "proposal": proposal}


async def chat(
    message: str, history: list[dict[str, str]], snapshot: AccountSnapshot | None, report: AuditReport | None
) -> dict[str, Any]:
    if not enabled():
        return fallback_reply(message, snapshot, report)
    items = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "Contexto da conta (JSON):\n"
            + json.dumps(account_context(snapshot, report), ensure_ascii=False, default=str)[:60000],
        },
    ]
    items += [
        {"role": h["role"], "content": h["content"][:4000]}
        for h in history[-10:]
        if h.get("role") in {"user", "assistant"}
    ]
    items.append({"role": "user", "content": message[:4000]})
    try:
        result = await _call(items, REPLY_SCHEMA, "copilot_reply")
    except (RuntimeError, httpx.HTTPError, ValueError):
        return fallback_reply(message, snapshot, report)
    proposal = (
        check_proposal(result.get("proposal_kind", "NONE"), result.get("proposal_json", "{}"), snapshot.account_id)
        if snapshot
        else None
    )
    return {"reply": result.get("reply", ""), "proposal": proposal}


async def generate_plan(
    briefing: dict[str, Any], keyword_ideas: list[dict[str, Any]], customer_id: str, fallback: dict[str, Any]
) -> dict[str, Any]:
    """Returns {"content", "notes", "source"}; falls back to the deterministic template on any failure."""
    if not enabled():
        return {"content": fallback, "notes": "Plano gerado pelo modelo padrão (sem IA).", "source": "template"}
    items = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n" + PLAN_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                {"briefing": briefing, "ideias_de_palavras": keyword_ideas[:60]}, ensure_ascii=False, default=str
            ),
        },
    ]
    try:
        result = await _call(items, PLAN_SCHEMA, "campaign_plan")
        content = {**json.loads(result["plan_json"]), "customer_id": customer_id}
        model = parse_plan(PlanKind.GOOGLE_SEARCH_CAMPAIGN, content)
    except (RuntimeError, httpx.HTTPError, ValueError, ValidationError, KeyError) as error:
        log.info("ai.plan_fallback", extra={"reason": type(error).__name__})
        return {
            "content": fallback,
            "notes": "A IA não gerou um plano válido; usei o modelo padrão.",
            "source": "template",
        }
    return {"content": dump_plan(model), "notes": result.get("notes", ""), "source": "copilot"}
