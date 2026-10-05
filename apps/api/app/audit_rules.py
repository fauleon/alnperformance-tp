"""Account audit with fixed, explainable rules (no AI). Each finding may carry a ready change proposal."""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel

from .policy import consistency_issues
from .snapshot import AccountSnapshot, CampaignInfo

Severity = Literal["critical", "high", "medium", "low"]
WEIGHTS: dict[str, int] = {"critical": 20, "high": 10, "medium": 5, "low": 2}
SMART_BIDDING = {"MAXIMIZE_CONVERSIONS", "TARGET_CPA", "TARGET_ROAS", "MAXIMIZE_CONVERSION_VALUE"}
ACTIVE = {"ENABLED", "ENABLE", "CAMPAIGN_STATUS_ENABLE"}


class Finding(BaseModel):
    rule: str
    severity: Severity
    title: str
    why: str
    fix: str
    campaign_id: str | None = None
    campaign_name: str | None = None
    evidence: dict[str, Any] = {}
    proposal: dict[str, Any] | None = None  # content for a GOOGLE_CHANGE / TIKTOK_CHANGE plan


class AuditReport(BaseModel):
    provider: str
    account_id: str
    score: int
    findings: list[Finding]
    summary: dict[str, int]
    period_start: date
    period_end: date


def _active(campaign: CampaignInfo) -> bool:
    return campaign.status.upper() in ACTIVE


def _google_change(snapshot: AccountSnapshot, changes: list[dict[str, Any]], rationale: str) -> dict[str, Any]:
    return {"schema_version": "1.0", "customer_id": snapshot.account_id, "rationale": rationale, "changes": changes}


def _tiktok_change(snapshot: AccountSnapshot, changes: list[dict[str, Any]], rationale: str) -> dict[str, Any]:
    return {"schema_version": "1.0", "advertiser_id": snapshot.account_id, "rationale": rationale, "changes": changes}


def audit_google(snapshot: AccountSnapshot, today: date | None = None) -> list[Finding]:
    today = today or date.today()
    findings: list[Finding] = []
    totals = snapshot.totals()
    avg_cpc = totals.cpc or Decimal("0")

    primary = [a for a in snapshot.conversion_actions if a.primary and a.status.upper() == "ENABLED"]
    if not primary:
        findings.append(
            Finding(
                rule="G002",
                severity="critical",
                title="Nenhuma ação de conversão principal ativa",
                why="Sem conversão principal o Google não sabe o que é um resultado e o Smart Bidding fica cego.",
                fix="Crie a conversão de lead (formulário, WhatsApp ou ligação) e instale a tag no site.",
                proposal=_google_change(
                    snapshot,
                    [
                        {
                            "action": "CREATE_CONVERSION_ACTION",
                            "name": "Lead - Formulário",
                            "category": "SUBMIT_LEAD_FORM",
                            "counting": "ONE_PER_CLICK",
                            "primary": True,
                        }
                    ],
                    "Criar conversão principal de lead.",
                ),
            )
        )
    elif sum((a.conversions for a in primary), Decimal("0")) == 0 and totals.clicks > 0:
        findings.append(
            Finding(
                rule="G002",
                severity="critical",
                title="Conversões principais sem registro no período",
                why=f"{len(primary)} conversão(ões) principal(is) ativa(s), mas nenhuma registrou resultado nos últimos dias "
                "com cliques acontecendo. Normalmente é tag quebrada ou conversão errada marcada como principal.",
                fix="Teste a tag com o Tag Assistant e confira se a ação principal é a que realmente mede o lead.",
                evidence={"primary_actions": [a.name for a in primary], "clicks": totals.clicks},
            )
        )

    if snapshot.enhanced_conversions_for_leads is False:
        findings.append(
            Finding(
                rule="G003",
                severity="high",
                title="Conversões otimizadas para leads desligadas",
                why="Sem conversões otimizadas, parte dos leads deixa de ser atribuída e o lance aprende com menos dados.",
                fix="Ative em Metas > Configurações e envie o e-mail ou telefone com hash pela tag do formulário.",
            )
        )

    wasted_by_campaign: dict[str, list[str]] = defaultdict(list)
    for term in snapshot.search_terms:
        m = term.metrics
        threshold = max(avg_cpc * 3, Decimal("1"))
        if m.conversions == 0 and m.clicks >= 5 and m.cost >= threshold and term.status != "EXCLUDED":
            wasted_by_campaign[term.campaign_id].append(term.term)

    for campaign in snapshot.campaigns:
        base = {"campaign_id": campaign.campaign_id, "campaign_name": campaign.name}
        enabled = _active(campaign)
        search = campaign.channel.upper() == "SEARCH"
        m = campaign.metrics

        if enabled and campaign.bidding_strategy in SMART_BIDDING and m.conversions == 0 and m.cost > 0:
            ceiling = (avg_cpc * Decimal("1.3")).quantize(Decimal("0.01")) if avg_cpc else None
            bidding: dict[str, Any] = {"type": "MAXIMIZE_CLICKS"}
            if ceiling and ceiling > 0:
                bidding["cpc_ceiling"] = {"amount": str(ceiling), "currency": snapshot.currency or "BRL"}
            findings.append(
                Finding(
                    rule="G001",
                    severity="critical",
                    **base,
                    title="Lance por conversão sem nenhuma conversão",
                    why=f"A campanha usa {campaign.bidding_strategy} e gastou {m.cost} sem converter. O algoritmo "
                    "não tem sinal para aprender e tende a pagar caro por cliques aleatórios.",
                    fix="Volte para Maximizar Cliques com teto de CPC até acumular conversões reais.",
                    evidence={"cost": str(m.cost), "clicks": m.clicks},
                    proposal=_google_change(
                        snapshot,
                        [{"action": "SET_BIDDING", "campaign_id": campaign.campaign_id, "bidding": bidding}],
                        "Trocar para Maximizar Cliques até ter conversões.",
                    ),
                )
            )

        if search and campaign.display_network:
            findings.append(
                Finding(
                    rule="G004",
                    severity="high",
                    **base,
                    title="Pesquisa com expansão para Display ligada",
                    why="O orçamento da Pesquisa vaza para banners na Rede de Display, com intenção muito menor.",
                    fix="Desligue a Rede de Display nesta campanha.",
                    proposal=_google_change(
                        snapshot,
                        [
                            {
                                "action": "SET_NETWORKS",
                                "campaign_id": campaign.campaign_id,
                                "search_partners": bool(campaign.search_partners),
                                "display_network": False,
                            }
                        ],
                        "Desligar Display.",
                    ),
                )
            )
        if search and campaign.search_partners:
            findings.append(
                Finding(
                    rule="G005",
                    severity="medium",
                    **base,
                    title="Parceiros de Pesquisa ligados",
                    why="Sites parceiros costumam trazer cliques mais baratos e de qualidade menor, difíceis de controlar.",
                    fix="Desligue os Parceiros de Pesquisa até a campanha ter conversões estáveis.",
                    proposal=_google_change(
                        snapshot,
                        [
                            {
                                "action": "SET_NETWORKS",
                                "campaign_id": campaign.campaign_id,
                                "search_partners": False,
                                "display_network": bool(campaign.display_network),
                            }
                        ],
                        "Desligar Parceiros de Pesquisa.",
                    ),
                )
            )

        if search and not campaign.negatives:
            terms = wasted_by_campaign.get(campaign.campaign_id, [])[:30]
            findings.append(
                Finding(
                    rule="G006",
                    severity="high",
                    **base,
                    title="Campanha sem palavras-chave negativas",
                    why="Sem negativas, a campanha aparece para buscas de emprego, aluguel, grátis e curiosidade.",
                    fix="Adicione uma lista de negativas do setor e revise os termos de pesquisa toda semana.",
                    proposal=_google_change(
                        snapshot,
                        [
                            {
                                "action": "ADD_NEGATIVES",
                                "campaign_id": campaign.campaign_id,
                                "keywords": [{"text": t, "match_type": "EXACT"} for t in terms],
                            }
                        ],
                        "Negativar termos com gasto e sem conversão.",
                    )
                    if terms
                    else None,
                )
            )

        broad = [
            k
            for g in campaign.ad_groups
            for k in g.keywords
            if k.match_type.upper() == "BROAD" and k.status.upper() == "ENABLED"
        ]
        if broad and (campaign.bidding_strategy not in SMART_BIDDING or m.conversions == 0):
            changes: list[dict[str, Any]] = []
            for group in campaign.ad_groups:
                group_broad = [k for k in group.keywords if k in broad]
                if group_broad:
                    changes.append(
                        {
                            "action": "ADD_KEYWORDS",
                            "ad_group_id": group.ad_group_id,
                            "keywords": [{"text": k.text, "match_type": "PHRASE"} for k in group_broad[:80]],
                        }
                    )
                    changes += [
                        {
                            "action": "SET_KEYWORD_STATUS",
                            "ad_group_id": group.ad_group_id,
                            "criterion_id": k.criterion_id,
                            "status": "PAUSED",
                        }
                        for k in group_broad
                    ]
            findings.append(
                Finding(
                    rule="G007",
                    severity="low",
                    **base,
                    title="Correspondência ampla sem Smart Bidding com conversões",
                    why="A ampla depende de sinais de conversão para filtrar buscas. Sem eles, abre demais o leque.",
                    fix="Troque por correspondência de frase ou exata até a conta ter conversões.",
                    evidence={"keywords": [k.text for k in broad[:20]]},
                    proposal=_google_change(snapshot, changes[:25], "Trocar ampla por frase.") if changes else None,
                )
            )

        for group in campaign.ad_groups:
            for ad in group.ads:
                if ad.type.upper() != "RESPONSIVE_SEARCH_AD" or ad.status.upper() != "ENABLED":
                    continue
                strength = (ad.ad_strength or "").upper()
                if strength in {"POOR", "AVERAGE"} or len(ad.headlines) < 15:
                    findings.append(
                        Finding(
                            rule="G008",
                            severity="low",
                            **base,
                            title=f"Anúncio com força {strength.lower() or 'baixa'} ({len(ad.headlines)} títulos)",
                            why="Anúncios com 15 títulos variados e 4 descrições entram em mais leilões e custam menos.",
                            fix="Complete os 15 títulos com variações de oferta, benefício, prova e chamada.",
                            evidence={"ad_group": group.name, "ad_id": ad.ad_id, "ad_strength": ad.ad_strength},
                        )
                    )

            low_qs = [
                k for k in group.keywords if k.quality_score is not None and k.quality_score <= 3 and k.metrics.cost > 0
            ]
            if low_qs:
                findings.append(
                    Finding(
                        rule="G015",
                        severity="medium",
                        **base,
                        title=f"Palavras com Índice de Qualidade baixo em {group.name}",
                        why="Índice de Qualidade até 3 encarece cada clique e reduz a posição do anúncio.",
                        fix="Aproxime anúncio e página da palavra-chave ou pause as que não têm relação com a oferta.",
                        evidence={"keywords": [f"{k.text} (QS {k.quality_score})" for k in low_qs[:15]]},
                    )
                )

        asset_texts = [a.text for a in campaign.assets]
        ad_texts = [t for g in campaign.ad_groups for ad in g.ads for t in (*ad.headlines, *ad.descriptions)]
        duplicated = sorted({t for t in asset_texts if asset_texts.count(t) > 1})
        contradictions = consistency_issues(asset_texts + ad_texts)
        if duplicated or contradictions:
            findings.append(
                Finding(
                    rule="G009",
                    severity="low",
                    **base,
                    title="Extensões repetidas ou contraditórias",
                    why="Informação repetida desperdiça espaço; números diferentes (ex.: 4 e 5 vagas) passam desconfiança.",
                    fix="Unifique os dados do produto em todos os textos e remova as extensões duplicadas.",
                    evidence={"duplicated": duplicated, "contradictions": contradictions},
                )
            )
        if search and enabled and not any(a.type == "SITELINK" for a in campaign.assets):
            findings.append(
                Finding(
                    rule="G016",
                    severity="low",
                    **base,
                    title="Campanha sem sitelinks",
                    why="Sitelinks aumentam a área do anúncio e a taxa de cliques sem custo extra.",
                    fix="Adicione pelo menos 4 sitelinks para páginas relevantes.",
                )
            )

        if campaign.geo_target_type and campaign.geo_target_type.upper() == "PRESENCE_OR_INTEREST":
            findings.append(
                Finding(
                    rule="G010",
                    severity="low",
                    **base,
                    title='Localização em "Presença ou interesse"',
                    why="O anúncio aparece para quem só pesquisou sobre a região, mesmo morando longe.",
                    fix='Use "Presença": pessoas que estão ou costumam estar na região.',
                    proposal=_google_change(
                        snapshot,
                        [
                            {
                                "action": "SET_GEO_TARGET_TYPE",
                                "campaign_id": campaign.campaign_id,
                                "positive": "PRESENCE",
                            }
                        ],
                        "Segmentar só por presença.",
                    ),
                )
            )

        if enabled and campaign.end_date:
            if campaign.end_date < today:
                findings.append(
                    Finding(
                        rule="G012",
                        severity="low",
                        **base,
                        title="Data de término já passou",
                        why="A campanha está ativa no painel, mas não veicula mais.",
                        fix="Atualize a data de término ou pause a campanha.",
                        evidence={"end_date": campaign.end_date.isoformat()},
                    )
                )
            elif campaign.end_date <= today + timedelta(days=7):
                findings.append(
                    Finding(
                        rule="G012",
                        severity="low",
                        **base,
                        title="Campanha termina em até 7 dias",
                        why="Sem renovação a veiculação para e o aprendizado recomeça depois.",
                        fix="Confirme se a data de término é intencional.",
                        evidence={"end_date": campaign.end_date.isoformat()},
                    )
                )

        if enabled and campaign.ad_groups:
            has_ad = any(ad.status.upper() == "ENABLED" for g in campaign.ad_groups for ad in g.ads)
            has_kw = any(k.status.upper() == "ENABLED" for g in campaign.ad_groups for k in g.keywords)
            if not has_ad or (search and not has_kw):
                findings.append(
                    Finding(
                        rule="G013",
                        severity="medium",
                        **base,
                        title="Campanha ativa sem anúncio ou palavra-chave ativa",
                        why="Ativa no painel, mas sem itens elegíveis ela não entra em leilão.",
                        fix="Ative ou crie anúncios e palavras-chave nos grupos.",
                    )
                )

        wasted = wasted_by_campaign.get(campaign.campaign_id, [])
        if wasted and campaign.negatives:
            findings.append(
                Finding(
                    rule="G011",
                    severity="high",
                    **base,
                    title=f"{len(wasted)} termo(s) de pesquisa gastando sem converter",
                    why="Esses termos receberam vários cliques e custo acima da média sem nenhuma conversão.",
                    fix="Negative em correspondência exata e revise se a palavra-chave que os aciona faz sentido.",
                    evidence={"terms": wasted[:30]},
                    proposal=_google_change(
                        snapshot,
                        [
                            {
                                "action": "ADD_NEGATIVES",
                                "campaign_id": campaign.campaign_id,
                                "keywords": [{"text": t, "match_type": "EXACT"} for t in wasted[:100]],
                            }
                        ],
                        "Negativar termos sem conversão.",
                    ),
                )
            )
    return findings


def audit_tiktok(snapshot: AccountSnapshot, today: date | None = None) -> list[Finding]:
    findings: list[Finding] = []
    totals = snapshot.totals()
    avg_cpc = totals.cpc
    for campaign in snapshot.campaigns:
        base = {"campaign_id": campaign.campaign_id, "campaign_name": campaign.name}
        m = campaign.metrics
        enabled = _active(campaign)
        objective = (campaign.objective or "").upper()
        if objective in {"WEB_CONVERSIONS", "LEAD_GENERATION", "CONVERSIONS"} and m.cost > 0 and m.conversions == 0:
            findings.append(
                Finding(
                    rule="T001",
                    severity="critical",
                    **base,
                    title="Objetivo de conversão sem nenhuma conversão",
                    why=f"A campanha gastou {m.cost} otimizando para conversão e não registrou nenhuma.",
                    fix="Confira o pixel e o evento; se ainda não houver volume, otimize para cliques primeiro.",
                )
            )
        if objective in {"WEB_CONVERSIONS", "CONVERSIONS"} and campaign.has_pixel is False:
            findings.append(
                Finding(
                    rule="T002",
                    severity="high",
                    **base,
                    title="Campanha de conversão sem pixel",
                    why="Sem pixel o TikTok não mede nem otimiza o resultado do site.",
                    fix="Instale o Pixel do TikTok e vincule o evento ao grupo de anúncios.",
                )
            )
        if m.impressions >= 5000 and (m.ctr or Decimal(0)) < Decimal("0.5"):
            findings.append(
                Finding(
                    rule="T003",
                    severity="medium",
                    **base,
                    title=f"CTR baixo ({m.ctr}%)",
                    why="No TikTok, CTR abaixo de 0,5% indica criativo que não prende nos primeiros segundos.",
                    fix="Teste ganchos novos nos 2 primeiros segundos e formatos nativos (Spark Ads).",
                )
            )
        if (
            enabled
            and campaign.ad_groups
            and not any(ad.status.upper() in ACTIVE for g in campaign.ad_groups for ad in g.ads)
        ):
            findings.append(
                Finding(
                    rule="T004",
                    severity="medium",
                    **base,
                    title="Campanha ativa sem anúncio ativo",
                    why="Sem anúncio ativo a campanha não veicula.",
                    fix="Ative ou crie anúncios nos grupos.",
                    proposal=_tiktok_change(
                        snapshot,
                        [{"action": "SET_CAMPAIGN_STATUS", "campaign_id": campaign.campaign_id, "status": "DISABLE"}],
                        "Pausar campanha sem anúncio ativo.",
                    ),
                )
            )
        if avg_cpc and m.cpc and m.clicks >= 20 and m.cpc > avg_cpc * 2:
            findings.append(
                Finding(
                    rule="T005",
                    severity="low",
                    **base,
                    title=f"CPC {m.cpc} é mais que o dobro da média da conta",
                    why="Público pequeno demais ou criativo fraco encarecem o leilão.",
                    fix="Amplie o público ou troque os criativos de menor desempenho.",
                )
            )
    return findings


def build_report(snapshot: AccountSnapshot, today: date | None = None) -> AuditReport:
    findings = audit_google(snapshot, today) if snapshot.provider == "GOOGLE_ADS" else audit_tiktok(snapshot, today)
    order = list(WEIGHTS)
    findings.sort(key=lambda f: (order.index(f.severity), f.rule))
    penalty_by_rule: dict[str, int] = defaultdict(int)
    for finding in findings:
        weight = WEIGHTS[finding.severity]
        penalty_by_rule[finding.rule] = min(penalty_by_rule[finding.rule] + weight, weight * 2)
    score = max(0, 100 - sum(penalty_by_rule.values()))
    summary = {severity: sum(1 for f in findings if f.severity == severity) for severity in WEIGHTS}
    return AuditReport(
        provider=snapshot.provider,
        account_id=snapshot.account_id,
        score=score,
        findings=findings,
        summary=summary,
        period_start=snapshot.period_start,
        period_end=snapshot.period_end,
    )
