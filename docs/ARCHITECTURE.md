# Arquitetura

## Fluxo de autoridade

`Leitura → Auditoria/Copiloto/Pessoa → Proposta (versão + hash) → Policy Engine + validate_only → Aprovação humana → Fila → Provider → Antes/depois → Reconciliação`

A IA é consultiva: recebe apenas o snapshot agregado da conta e devolve uma proposta que precisa passar pelos contratos Pydantic, pela política e por uma aprovação. Ela nunca recebe tokens nem chama as plataformas.

## Componentes

| Peça | Onde | Papel |
| --- | --- | --- |
| Web | `apps/web` (Next.js 16) | site público, login, painel; `app/api/[...path]` faz proxy para a API (mesma origem, cookie first-party, CSP `connect-src 'self'`) |
| API | `apps/api/app/main.py` + `routers/` | autenticação, tenant, conexões, leitura, planos, copiloto |
| Worker | `apps/api/app/worker.py` | execuções, sync noturna de métricas, reconciliação, limpeza; fila em Postgres (`FOR UPDATE SKIP LOCKED`), retry exponencial, DLQ (`DEAD`) |
| Contratos | `domain.py` | planos versionados: `GOOGLE_SEARCH_CAMPAIGN`, `GOOGLE_CHANGE`, `TIKTOK_CAMPAIGN`, `TIKTOK_CHANGE` |
| Política | `policy.py` | kill switch, limite por cliente, moeda, URL pública, separação orçamento/ativação, consistência de números nos textos |
| Auditoria | `audit_rules.py` | regras fixas, nota 0–100, proposta pronta por achado |
| Providers | `providers/google_ads.py`, `providers/tiktok_ads.py` | OAuth, leitura normalizada (`snapshot.py`), `OperationBuilder` (mutate atômico com IDs temporários), erros traduzidos (retryable / reconectar) |
| Reversão | `services/revert.py` | proposta inversa a partir do antes/depois |
| Dados | `models.py` + Alembic | usuários, organizações, clientes (workspaces), papéis, convites, sessões, states OAuth, conexões, contas, planos + revisões, aprovações, execuções, jobs, auditoria, cache, cota |

## Isolamento

`organization_id` e `workspace_id` vêm da sessão (`deps.tenant`): o cabeçalho `X-Workspace-Id` só escolhe entre clientes das organizações do usuário. Todas as consultas de domínio filtram pelos dois. Papéis: `owner` (limites, equipe), `admin` (propor, aprovar, executar, conectar), `viewer` (leitura).

## Google Ads

- Versão fixa: `GOOGLE_ADS_API_VERSION = "v25"` (`google-ads==33.0.0`).
- `login_customer_id` por conta, descoberto via `ListAccessibleCustomers` + `customer_client`.
- Criação: um único `GoogleAdsService.Mutate` (atômico). Antes de recriar, procura campanha com o mesmo nome (idempotência entre tentativas).
- Rede: só Pesquisa do Google; `PRESENCE`; `DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING`; status `PAUSED`.
- Refresh de token com lock por processo e `SELECT … FOR UPDATE` entre processos; `invalid_grant` marca a conexão como `NEEDS_RECONNECT`.

## Próximos passos possíveis

- Row Level Security no Postgres como segunda barreira (hoje o isolamento é na aplicação e coberto por testes).
- Vault externo (GCP Secret Manager/Doppler) para as chaves Fernet.
- Criativos do TikTok (upload de vídeo) pelo painel.
