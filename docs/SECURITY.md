# Segurança e operação

- `GLOBAL_KILL_SWITCH=true` e `GOOGLE_ADS_MUTATIONS_ENABLED=false` por padrão.
- Campanhas novas aceitam somente `initial_status=PAUSED`.
- Aprovação é vinculada ao conteúdo, versão e SHA-256 do JSON canônico.
- A execução exige `Idempotency-Key` e recusa aprovação divergente.
- O TenantContext é obrigatório em todas as operações de domínio.
- URLs privadas, localhost, link-local e metadata são bloqueadas.
- O sistema não possui capability de billing ou armazenamento de cartões.
- Tokens, headers e payloads sensíveis não entram em prompts ou auditoria.

Antes de ativar providers reais, implementar vault com envelope encryption, RLS, RBAC, rate limit, refresh lock, redaction, alertas e testes de escape entre tenants.

