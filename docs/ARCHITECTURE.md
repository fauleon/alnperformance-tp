# Arquitetura do MVP

## Fluxo de autoridade

`Briefing → Plano estruturado → Policy Engine → Aprovação por hash → Worker → Provider → Reconciliação`

A IA é uma camada consultiva. Ela nunca recebe credenciais nem chama providers diretamente. O MVP mantém mutações externas desligadas e usa um provider simulado, permitindo validar todo o fluxo sem risco financeiro.

## Fronteiras

- `apps/web`: experiência de onboarding, preview, aprovação e auditoria.
- `apps/api/app/domain.py`: contratos estritos e versionados.
- `apps/api/app/policy.py`: decisões determinísticas e explicáveis.
- `apps/api/app/main.py`: API, isolamento de tenant e fluxo operacional.
- `apps/api/app/store.py`: store temporário do protótipo; substituir por PostgreSQL + RLS na Sprint 1.

## Providers e autoridade de edição

Os catálogos de capabilities de Google Ads e Meta Ads estão expostos em `GET /v1/providers`. O início de OAuth usa `POST /v1/connections/{provider}/start` e só retorna uma URL oficial quando todas as credenciais obrigatórias estiverem configuradas.

O escopo funcional previsto cobre leitura, criação, pausa e edição de campanhas e recursos associados. Orçamento é tecnicamente editável, mas sempre exige proposta financeira e confirmação humana separada. Payments, billing methods e add funds são capabilities inexistentes.

## Próximas integrações

1. PostgreSQL, Alembic e RLS por organização/workspace.
2. OAuth Google com PKCE/state e vault cifrado.
3. OpenAI Responses API com Structured Outputs e evals.
4. Redis + ARQ para Saga, retry, reconciliação e DLQ.
5. Google Ads validate-only e criação real exclusivamente em `PAUSED`.
