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

## Próximas integrações

1. PostgreSQL, Alembic e RLS por organização/workspace.
2. OAuth Google com PKCE/state e vault cifrado.
3. OpenAI Responses API com Structured Outputs e evals.
4. Redis + ARQ para Saga, retry, reconciliação e DLQ.
5. Google Ads validate-only e criação real exclusivamente em `PAUSED`.

