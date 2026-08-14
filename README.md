# ALN Performance AI Ads Manager

MVP seguro e multiempresa para planejar, revisar, aprovar e executar campanhas de mídia paga com supervisão humana.

## O que já funciona

- painel responsivo para briefing, plano Google Search, aprovação, execução e auditoria;
- API FastAPI com isolamento por `organization_id` e `workspace_id`;
- contratos Pydantic versionados e orçamento em `Decimal`;
- Policy Engine com limite diário, URL segura, status inicial `PAUSED` e kill switch;
- aprovação vinculada ao hash canônico da versão do plano;
- idempotência e execução assíncrona simulada, sempre em `PAUSED`;
- trilha de auditoria sanitizada e testes unitários dos guardrails.

O provider do Google Ads está em modo simulado por padrão. Nenhuma credencial, cobrança, campanha ativa ou mutação externa é realizada.

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

