# ALN Hub ia

Plataforma da ALN Performance para **auditar, planejar e operar Google Ads e TikTok Ads com IA e aprovação humana**.
Site público no formato do ecossistema ALN (Digital, Performance, Branding Studio, Deploy, Hub) + painel em `/app`.

## O que faz

| Área | Google Ads (API v25) | TikTok Ads (Marketing API v1.3) |
| --- | --- | --- |
| Conexão | OAuth com PKCE e `state` de uso único; descoberta da hierarquia MCC | OAuth do TikTok for Business; lista de anunciantes |
| Leitura | campanhas, grupos, palavras (QS), RSA (força), negativas, listas compartilhadas, extensões, termos de pesquisa, conversões, métricas diárias, ideias de palavras com volume | campanhas, grupos, anúncios, pixel, relatório diário |
| Auditoria | 15 regras (G001–G016) com nota 0–100 e proposta pronta | 5 regras (T001–T005) |
| Escrita (sempre via proposta → validação → aprovação → fila) | campanha de Pesquisa completa **pausada** numa única operação atômica (orçamento, campanha, local, idioma, negativas, grupos, palavras, RSA, sitelinks, frases, snippet, nome da empresa), `validate_only` antes de aprovar, redes, negativas, palavras, RSA, lance, data, presença, status, orçamento, ação de conversão (+ código da tag), conversão offline por GCLID, remover campanha (reversão) | campanha + grupo **desativados** (com compensação se o grupo falhar), status, orçamento |
| IA | copiloto (OpenAI Responses API + Structured Outputs) que só propõe; sem chave, responde pela auditoria | idem |

Garantias: kill switch global, flag de escrita por plataforma, limite diário por cliente, URL de destino pública, aprovação presa ao SHA-256 da versão, orçamento e ativação como propostas separadas (“O dinheiro já está disponível. Deseja aplicar?”), `Idempotency-Key`, antes/depois de cada execução com **Reverter**, trilha de auditoria sem tokens, isolamento por organização/cliente derivado do login.

## Estrutura

```
apps/api   FastAPI + SQLAlchemy async + Alembic + google-ads 33 (API v25) — API e worker
apps/web   Next.js 16 (App Router) — site, login, painel e proxy /api
docs/      arquitetura e segurança
```

## Rodar localmente

```bash
cp .env.example .env            # gere TOKEN_ENCRYPTION_KEYS (veja abaixo)
docker compose up --build       # Postgres + API + worker + web em http://localhost:3000
docker compose exec api python -m app.cli bootstrap --email voce@alndigital.com.br --name "Seu Nome" --org "ALN Performance" --workspace "Primeiro cliente"
```

Sem Docker:

```bash
cd apps/api && python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/python -m app.cli generate-key          # cole em TOKEN_ENCRYPTION_KEYS
.venv/Scripts/alembic upgrade head
.venv/Scripts/python -m app.cli bootstrap --email ... --name ... --org ... --workspace ...
.venv/Scripts/uvicorn app.main:app --reload            # API em :8000
.venv/Scripts/python -m app.worker                     # worker (outro terminal)

cd apps/web && npm ci && npm run dev                   # web em :3000 (API_INTERNAL_URL=http://localhost:8000)
```

Testes: `cd apps/api && pytest` (48 testes: política, auditoria, operações protobuf reais da v25, gateways HTTP, fluxo completo da API com isolamento, kill switch, idempotência, retry/DLQ). `ruff check app tests`, `mypy app`. Web: `npm run lint && npm run build`.

## Publicar no Railway (projeto `alnapi`)

| Serviço | Root | Config | Variáveis principais |
| --- | --- | --- | --- |
| Postgres | plugin | — | — |
| `api` | `apps/api` | `railway.toml` (migra no boot) | todas as da API no `.env.example`, `APP_ENV=production`, `DATABASE_URL=${{Postgres.DATABASE_URL}}` |
| `worker` | `apps/api` | `railway.worker.toml` | mesmas da `api` |
| `web` | `apps/web` | `railway.toml` | `NEXT_PUBLIC_SITE_URL`, `API_INTERNAL_URL=http://${{api.RAILWAY_PRIVATE_DOMAIN}}:8000` |

- Só o `web` precisa de domínio público (ex.: `app.alnperformance.com.br`). A API fica na rede privada; o navegador fala com ela via `/api`.
- `APP_URL=https://app.alnperformance.com.br` e `PUBLIC_API_URL=https://app.alnperformance.com.br/api`.
- **Desligue o App Sleeping** em `api` e `worker` (callback OAuth e fila precisam estar acordados).
- Mantenha `GLOBAL_KILL_SWITCH=true` até terminar os testes na conta de teste.

## O que falta (só depende do Google/TikTok)

1. Google Cloud: ativar a Google Ads API, tela de consentimento (*External*) com `/privacidade` e `/termos` do site, OAuth Client *Web* com a redirect URI `https://<domínio>/api/v1/connections/google/callback`.
2. MCC: Developer Token (nasce em modo teste) → preencher `GOOGLE_*` → conectar uma **conta de teste** e rodar o fluxo completo.
3. Pedir o **acesso Básico** do Developer Token (a página `/seguranca` e `docs/ARCHITECTURE.md` servem de documento de design).
4. TikTok for Business: app no Marketing API com redirect `https://<domínio>/api/v1/connections/tiktok/callback` → `TIKTOK_APP_ID/SECRET`.
5. Virada: `GOOGLE_ADS_MUTATIONS_ENABLED=true` e `GLOBAL_KILL_SWITCH=false`; primeira mutação pequena e reversível.

## Operação

- Rotação de chave: adicione a nova chave **no início** de `TOKEN_ENCRYPTION_KEYS`, faça deploy, rode `python -m app.cli rotate-keys`, depois remova a antiga.
- Kill switch de emergência: `GLOBAL_KILL_SWITCH=true` + redeploy bloqueia validação, aprovação e execução (leitura continua).
- Jobs mortos (DLQ): tabela `jobs` com `status='DEAD'`; o log `job.dead_letter` sai em JSON (ligue alertas no Sentry/Railway).
- Cota: `api_usage` conta operações do Google por dia; alerta `quota.alert` em 80% de 15.000.
- Marca: `npm run brand -- "<matriz PNG transparente>"` regenera símbolo e ícones (`apps/web/public/brand`).
