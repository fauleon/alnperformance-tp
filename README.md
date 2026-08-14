# ALNAPI — AI Ads Manager da ALN Performance

MVP seguro e multiempresa para planejar, revisar, aprovar e executar campanhas de mídia paga com supervisão humana.

## O que já funciona

- painel responsivo para briefing, plano Google Search, aprovação, execução e auditoria;
- API FastAPI com isolamento por `organization_id` e `workspace_id`;
- contratos Pydantic versionados e orçamento em `Decimal`;
- Policy Engine com limite diário, URL segura, status inicial `PAUSED` e kill switch;
- aprovação vinculada ao hash canônico da versão do plano;
- idempotência e execução assíncrona simulada, sempre em `PAUSED`;
- trilha de auditoria sanitizada e testes unitários dos guardrails.

Google Ads e Meta Ads ficam em modo protegido por padrão. A área de integrações documenta os escopos de leitura e edição, mas nenhuma credencial, cobrança, campanha ativa ou mutação externa é realizada até OAuth, vault, contas de teste e as respectivas aprovações das plataformas estarem configurados.

## Integrações oficiais

- Google Ads: OAuth com escopo `adwords`, Developer Token e acesso a campanhas, grupos, anúncios, assets, keywords, negativas, públicos, segmentação, lances, orçamento, conversões e métricas.
- Meta Ads: OAuth com `ads_management`, `ads_read`, `business_management` e `read_insights`, cobrindo campanhas, conjuntos, anúncios, criativos, públicos, posicionamentos, pixel/eventos, otimização e insights.
- Pagamentos, cartões, billing e adição de saldo não existem como capabilities.
- Toda alteração de orçamento é uma proposta separada, com confirmação humana explícita: “O dinheiro já está disponível. Deseja aplicar?”.

## Railway

O projeto Railway deve se chamar `alnapi`, com dois serviços apontando para `apps/web` e `apps/api`. Ative Serverless/App Sleeping nos dois serviços enquanto o produto não estiver em uso. As mutações continuam bloqueadas por `GLOBAL_KILL_SWITCH=true` mesmo quando o serviço acordar.

## Rodar com Docker

```bash
docker compose up --build
```

- Web: http://localhost:3000
- API e documentação: http://localhost:8000/docs

## Rodar em desenvolvimento

Backend:

```bash
cd apps/api
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/uvicorn app.main:app --reload
```

Frontend:

```bash
cd apps/web
npm install
npm run dev
```

Copie `.env.example` para `.env` quando for conectar serviços reais. Consulte [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) e [docs/SECURITY.md](docs/SECURITY.md).
