"""Deterministic campaign templates. They cover most cases without AI and never contradict the source data."""

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import Field, HttpUrl

from .domain import GOOGLE_RSA_DESCRIPTION_MAX, GOOGLE_RSA_HEADLINE_MAX, Money, StrictModel

REAL_ESTATE_NEGATIVES = [
    "aluguel",
    "alugar",
    "locação",
    "leilão",
    "caixa",
    "minha casa minha vida",
    "mcmv",
    "na planta",
    "planta baixa",
    "curso",
    "emprego",
    "trabalho",
    "vaga de emprego",
    "grátis",
    "gratuito",
    "barato",
    "popular",
    "temporada",
    "airbnb",
    "kitnet",
    "quitinete",
    "consórcio",
    "financiamento caixa",
    "reclame aqui",
    "corretor de imóveis curso",
]


GENERIC_NEGATIVES = ["grátis", "gratuito", "emprego", "vaga de emprego", "curso", "download", "pdf", "reclame aqui"]


class SitelinkInput(StrictModel):
    text: str = Field(min_length=1, max_length=25)
    final_url: HttpUrl


class PropertySheet(StrictModel):
    """Ficha do imóvel. Todos os textos do anúncio saem daqui, por isso não há contradição."""

    title: str = Field(min_length=3, max_length=80)
    property_type: str = Field(default="casa", max_length=30)
    condominium: str | None = Field(default=None, max_length=60)
    neighborhood: str = Field(min_length=2, max_length=60)
    city: str = Field(min_length=2, max_length=60)
    price: Decimal | None = Field(default=None, gt=0)
    area_m2: int | None = Field(default=None, gt=0, lt=100000)
    bedrooms: int | None = Field(default=None, ge=0, le=30)
    suites: int | None = Field(default=None, ge=0, le=30)
    parking: int | None = Field(default=None, ge=0, le=50)
    differentials: list[str] = Field(default_factory=list, max_length=12)
    url: HttpUrl
    business_name: str | None = Field(default=None, max_length=25)
    sitelinks: list[SitelinkInput] = Field(default_factory=list, max_length=8)
    daily_budget: Money
    cpc_ceiling: Money | None = None
    geo_target_ids: list[str] = Field(min_length=1, max_length=20)
    geo_target_names: list[str] = Field(default_factory=list)
    start_date: date
    end_date: date | None = None


class Briefing(StrictModel):
    company: str = Field(min_length=2, max_length=80)
    offer: str = Field(min_length=5, max_length=300)
    audience: str = Field(default="", max_length=300)
    landing_page: HttpUrl
    seed_keywords: list[str] = Field(min_length=1, max_length=30)
    differentials: list[str] = Field(default_factory=list, max_length=10)
    daily_budget: Money
    geo_target_ids: list[str] = Field(min_length=1, max_length=20)
    geo_target_names: list[str] = Field(default_factory=list)
    start_date: date
    end_date: date | None = None


def _fit(texts: list[str], limit: int, maximum: int) -> list[str]:
    out: list[str] = []
    for text in texts:
        text = " ".join(text.split())
        if text and len(text) <= limit and text.lower() not in {t.lower() for t in out}:
            out.append(text)
    return out[:maximum]


def _money_short(value: Decimal) -> str:
    if value >= 1_000_000:
        millions = (value / 1_000_000).quantize(Decimal("0.01")).normalize()
        return f"R$ {str(millions).replace('.', ',')} mi"
    return f"R$ {int(value):,}".replace(",", ".")


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def real_estate_plan(sheet: PropertySheet, customer_id: str) -> dict[str, Any]:
    kind, hood, condo = sheet.property_type.lower(), sheet.neighborhood, sheet.condominium
    facts = []
    if sheet.suites:
        facts.append(_plural(sheet.suites, "Suíte", "Suítes"))
    if sheet.parking:
        facts.append(_plural(sheet.parking, "Vaga", "Vagas"))
    if sheet.area_m2:
        facts.append(f"{sheet.area_m2} m²")

    keyword_texts = [
        f"{kind} à venda {hood}",
        f"{kind} em condomínio {hood}",
        f"{kind} alto padrão {hood}",
        f"{kind} de luxo {hood}",
        f"{kind} porteira fechada {hood}",
        f"imóvel à venda {hood}",
        f"comprar {kind} {hood}",
    ]
    if sheet.suites:
        keyword_texts.append(f"{kind} {sheet.suites} suítes {hood}")
    exact = []
    if condo:
        exact = [condo, f"{kind} {condo}", f"{condo} {hood}", f"{kind} à venda {condo}"]
    keywords = [{"text": t, "match_type": "PHRASE"} for t in keyword_texts]
    keywords += [{"text": t, "match_type": "EXACT"} for t in exact]
    keywords = [k for k in keywords if len(k["text"]) <= 80 and len(k["text"].split()) <= 10]

    headlines = _fit(
        [
            f"{kind.title()} à Venda em {hood}",
            condo or "",
            f"{kind.title()} no {condo}" if condo else "",
            " e ".join(facts[:2]),
            f"{sheet.area_m2} m² de Área" if sheet.area_m2 else "",
            f"Alto Padrão em {hood}",
            f"{hood}, {sheet.city}",
            _money_short(sheet.price) if sheet.price else "",
            *sheet.differentials,
            "Agende Sua Visita",
            "Fale com um Especialista",
            "Veja Fotos e Detalhes",
            "Pronto para Morar",
            f"{kind.title()} Exclusiva" if kind.endswith("a") else f"{kind.title()} Exclusivo",
            "Atendimento Personalizado",
        ],
        GOOGLE_RSA_HEADLINE_MAX,
        15,
    )
    description_facts = ", ".join(facts) if facts else "acabamento de alto padrão"
    descriptions = _fit(
        [
            f"{kind.title()} em {hood} com {description_facts}. Agende uma visita.",
            f"{sheet.title}. Fotos, planta e condições direto com a imobiliária.",
            f"Diferenciais: {', '.join(sheet.differentials[:3])}." if sheet.differentials else "",
            f"Localização privilegiada em {hood}, {sheet.city}. Fale com um especialista hoje.",
            f"Valor: {_money_short(sheet.price)}. Condições sob consulta." if sheet.price else "",
        ],
        GOOGLE_RSA_DESCRIPTION_MAX,
        4,
    )
    if len(descriptions) < 2:
        descriptions.append("Atendimento personalizado e visita agendada no seu horário.")

    callouts = _fit([*facts, *sheet.differentials, "Visita Agendada", "Atendimento Exclusivo"], 25, 10)
    plan: dict[str, Any] = {
        "customer_id": customer_id,
        "name": f"{sheet.title} | Pesquisa | Imóvel"[:128],
        "final_url": str(sheet.url),
        "daily_budget": sheet.daily_budget.model_dump(mode="json"),
        "start_date": sheet.start_date.isoformat(),
        "end_date": sheet.end_date.isoformat() if sheet.end_date else None,
        "geo_target_ids": sheet.geo_target_ids,
        "geo_target_names": sheet.geo_target_names,
        "language_ids": ["1014"],
        "bidding": {
            "type": "MAXIMIZE_CLICKS",
            **({"cpc_ceiling": sheet.cpc_ceiling.model_dump(mode="json")} if sheet.cpc_ceiling else {}),
        },
        "ad_groups": [
            {
                "name": f"{kind.title()} {condo or hood}"[:120],
                "keywords": keywords,
                "ads": [
                    {
                        "headlines": headlines,
                        "descriptions": descriptions,
                        "path1": "imovel",
                        "path2": hood.lower().replace(" ", "-")[:15],
                    }
                ],
            }
        ],
        "campaign_negatives": [{"text": n, "match_type": "PHRASE"} for n in REAL_ESTATE_NEGATIVES],
        "sitelinks": [{"text": s.text, "final_url": str(s.final_url)} for s in sheet.sitelinks]
        if len(sheet.sitelinks) >= 2
        else [],
        "callouts": callouts,
        "business_name": sheet.business_name,
    }
    return plan


def briefing_plan(briefing: Briefing, customer_id: str) -> dict[str, Any]:
    company = briefing.company
    seeds = [s for s in (" ".join(x.lower().split()) for x in briefing.seed_keywords) if s][:30]
    headlines = _fit(
        [
            company,
            *[s.title() for s in seeds[:5]],
            *briefing.differentials,
            "Fale com a Gente Hoje",
            "Atendimento Rápido",
            "Peça Seu Orçamento",
            f"Conheça a {company}",
            "Solicite Uma Proposta",
            "Saiba Mais Agora",
        ],
        GOOGLE_RSA_HEADLINE_MAX,
        15,
    )
    descriptions = _fit(
        [
            briefing.offer,
            f"{company}: {briefing.offer}",
            "Fale com a nossa equipe e receba uma proposta sob medida.",
            f"{', '.join(briefing.differentials[:3])}."
            if briefing.differentials
            else "Atendimento próximo, do primeiro contato à entrega.",
        ],
        GOOGLE_RSA_DESCRIPTION_MAX,
        4,
    )
    while len(headlines) < 3:
        headlines.append(["Fale Conosco", "Saiba Mais", "Peça Orçamento"][len(headlines)])
    if len(descriptions) < 2:
        descriptions.append("Fale com a nossa equipe e receba uma proposta sob medida.")
    return {
        "customer_id": customer_id,
        "name": f"{company} | Pesquisa | {date.today():%m/%Y}"[:128],
        "final_url": str(briefing.landing_page),
        "daily_budget": briefing.daily_budget.model_dump(mode="json"),
        "start_date": briefing.start_date.isoformat(),
        "end_date": briefing.end_date.isoformat() if briefing.end_date else None,
        "geo_target_ids": briefing.geo_target_ids,
        "geo_target_names": briefing.geo_target_names,
        "language_ids": ["1014"],
        "bidding": {"type": "MAXIMIZE_CLICKS"},
        "ad_groups": [
            {
                "name": "Oferta principal",
                "keywords": [{"text": s, "match_type": "PHRASE"} for s in seeds],
                "ads": [{"headlines": headlines, "descriptions": descriptions}],
            }
        ],
        # Generic negatives, minus any that collide with what the business actually sells.
        "campaign_negatives": [
            {"text": n, "match_type": "PHRASE"}
            for n in GENERIC_NEGATIVES
            if not any(n in seed or seed in n for seed in seeds)
        ],
    }
