# Segurança e operação

## Controles implementados

- **Autenticação**: senha scrypt (N=2^17), sessão opaca em cookie HttpOnly/SameSite=Lax/Secure (hash no banco, revogável), troca de senha encerra as outras sessões, acesso por convite de uso único (7 dias).
- **CSRF**: toda requisição que altera estado exige `X-Requested-With: alnia` e `Origin` permitido.
- **Rate limit**: global por IP (600/min), login por IP e por e-mail, convites, copiloto, ideias de palavras, refresh.
- **Tenant**: organização e cliente derivados da sessão; testes cobrem acesso cruzado (404) e papéis (403).
- **Mutações**: `GLOBAL_KILL_SWITCH` bloqueia validação, aprovação e execução; flag por plataforma; política reavaliada na validação, na aprovação, no envio e de novo no worker.
- **Aprovação**: presa à versão e ao SHA-256 do conteúdo; consumida por uma execução; orçamento exige confirmação financeira; ativação é aprovação própria.
- **Idempotência**: `Idempotency-Key` única por organização; criação de campanha verifica nome existente; TikTok com compensação (saga).
- **Tokens**: Fernet com `MultiFernet` (rotação `app.cli rotate-keys`); revogação na plataforma ao desconectar; PKCE + `state` aleatório de uso único (10 min).
- **Dados**: auditoria e logs passam por `redact()` (tokens, e-mails, telefones, GCLID); logs JSON; Sentry sem PII.
- **Web**: CSP com nonce por requisição (sem `unsafe-inline`), HSTS, `X-Frame-Options: DENY`, `Permissions-Policy`, COOP/CORP, `noindex` no painel, Next.js 16.3.8 (corrige RCEs da 16.3.1).
- **API**: corpo até 512 KB, `/docs` desligado em produção, validação de configuração de produção no boot.
- **Fora do escopo**: pagamentos, meios de cobrança, saldo.

## Checklist antes de desligar o kill switch

1. Fluxo completo na conta de teste: conectar → auditar → criar pausada → editar → reverter → desconectar.
2. Token revogado no Google → conexão vira “Reconectar”.
3. Alertas ligados para `job.dead_letter`, `quota.alert`, `connection.needs_reconnect`.
4. Backup diário do Postgres ativo no Railway.
