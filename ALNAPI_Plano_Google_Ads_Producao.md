# ALNAPI — Plano para deixar o Google Ads 100% real

> Repositório: `fauleon/alnperformance-tp` · Escopo: **somente Google Ads** (Meta fica para depois)
> Objetivo: sistema pronto em produção, faltando apenas o Developer Token com acesso Básico aprovado.
> Gerado em 05/10/2026 a partir da leitura do código atual.

---

## Status em 05/10/2026 (produto renomeado para **ALN Hub ia**, Meta substituído por TikTok Ads)

| Fase | Status |
|---|---|
| 0 Credenciais Google | ⏳ depende de você/Google (ver README → "O que falta") |
| 1 Segurança (login, tenant pela sessão, kill switch real, limite por cliente, CORS/CSRF, rate limit, headers) | ✅ |
| 2 Postgres + Alembic + versionamento + `lifespan` | ✅ (RLS fica como 2ª barreira opcional) |
| 3 OAuth completo (redirect ao painel, `access_denied`, refresh_token obrigatório, PKCE, state de uso único, MCC/subcontas, várias contas, refresh com lock, revogar, `invalid_grant`, MultiFernet, google-ads v25) | ✅ |
| 4 Leitura GAQL + auditoria (nota 0–100) + telas Campanhas/Métricas/Auditoria | ✅ |
| 5 Escrita real pausada (mutate atômico, `validate_only`, assets, edições, conversões + tag, offline, antes/depois, Reverter) | ✅ código e testes offline; falta rodar na conta de teste |
| 6 Fila/worker (Postgres SKIP LOCKED em vez de ARQ/Redis), retry, DLQ, reconciliação, sync noturna, cota | ✅ |
| 7 Painel com dados reais (rotas, SWR, login, seletor de cliente, diff, aprovação, auditoria) | ✅ |
| 8 Modelo "Imóvel alto padrão" + checagem de consistência | ✅ |
| 9 Copiloto (OpenAI Structured Outputs, só propõe, validado) | ✅ (falta `OPENAI_API_KEY`) |
| 10 Deploy (Dockerfiles, Railway api/worker/web, logs JSON, Sentry, CI com Postgres + mypy + lint) | ✅ configuração; falta criar os serviços |
| 11 Testes | ✅ 48 automatizados; ⏳ fluxo na conta de teste do Google |
| 12 Contas reais | ⏳ após acesso Básico |

---

## Como usar este documento

- Siga as fases na ordem. Cada fase termina com um **critério de pronto**.
- `[ ]` = a fazer. Marque `[x]` conforme concluir.
- 🔴 = bloqueia produção · 🟠 = importante · 🟢 = melhoria
- Tudo até a Fase 7 pode ser feito e testado com **Developer Token em modo teste** + **conta de teste do Google Ads**.

---

## Fase 0 — Credenciais e contas Google (iniciar HOJE, roda em paralelo)

Essas etapas dependem do Google e levam dias ou semanas. Comece antes de codar.

- [ ] 🔴 **Conta MCC (Gerente)** do Google Ads da ALN Performance
  - Vincular as contas dos clientes (ex.: Porto imóveis `370-241-8595`) como subcontas.
- [ ] 🔴 **Conta de teste**: criar uma **MCC de teste** e, dentro dela, uma conta de cliente de teste.
  - Conta de teste não veicula anúncios nem cobra. É onde todo o desenvolvimento acontece.
- [ ] 🔴 **Developer Token**: MCC real → *Admin* → *Central de API*
  - Nasce com **acesso de teste**, que só funciona em contas de teste.
  - Preencher os dados da empresa, o site e o e-mail de contato da API.
- [ ] 🔴 **Pedir acesso Básico** do Developer Token
  - É o pedido que libera contas reais.
  - Preparar um documento de design da ferramenta (fluxo, telas, quem usa, como protege os dados). O `docs/ARCHITECTURE.md` e este plano servem de base.
  - Prazo típico: alguns dias úteis; pode haver perguntas do Google.
- [ ] 🔴 **Projeto no Google Cloud**
  - Ativar a **Google Ads API**.
  - Configurar a tela de consentimento OAuth: tipo *External*, nome do app, logo, domínio, política de privacidade e termos de uso (URLs públicas).
  - Criar a credencial **OAuth Client ID** do tipo *Web application*.
  - Redirect URI autorizada: `https://<api-em-produção>/v1/connections/google/callback`, mais a URL de localhost para desenvolvimento.
- [ ] 🟠 **Verificação do app OAuth**
  - O escopo `https://www.googleapis.com/auth/adwords` é sensível. Enquanto o app não for verificado, ele fica em modo *Testing*, limitado a 100 usuários de teste cadastrados manualmente.
  - Para uso interno da ALN, o modo *Testing* resolve. Para vender como SaaS, é preciso pedir a verificação.
- [ ] 🟠 **Domínio e páginas públicas**: política de privacidade e termos de uso hospedados, que são exigidos pela tela de consentimento.

**Pronto quando:** você tiver `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_ADS_DEVELOPER_TOKEN` (teste), o ID da MCC de teste e uma conta de teste.

---

## Fase 1 — Correções de segurança no código atual 🔴

Bugs e riscos encontrados na leitura do código. Corrigir antes de conectar qualquer conta.

### 1.1 Não existe autenticação de usuário
- **Onde:** `apps/api/app/main.py` → `tenant_context()`
- **Problema:** a organização vem do cabeçalho `X-Organization-Id`, e quando ele não é enviado usa `DEMO_ORG` como padrão. Qualquer pessoa com a URL da API lê e altera dados de qualquer tenant.
- [ ] Implementar login (sugestões: Clerk, Auth0, Supabase Auth ou sessão própria com JWT).
- [ ] Derivar `organization_id` e `workspace_id` **do usuário autenticado**, nunca do cabeçalho.
- [ ] Criar tabelas `users`, `organizations`, `workspaces` e `memberships` (com papel: owner, admin, viewer).
- [ ] Remover `DEMO_ORG` e `DEMO_WORKSPACE` como padrão em produção.
- [ ] Teste: um usuário da org A recebe 404 ao tentar acessar recurso da org B.

### 1.2 O kill switch global é ignorado
- **Onde:** `main.py` → `validate()` e `approve()` chamam `evaluate_plan(..., kill_switch=False)` com valor fixo.
- **Onde:** `execute()` não verifica `settings.global_kill_switch` nem `settings.google_ads_mutations_enabled`.
- [ ] Usar `kill_switch=settings.global_kill_switch` nas duas chamadas.
- [ ] Em `execute()`, recusar com 423 ou 409 se `global_kill_switch=true` ou `google_ads_mutations_enabled=false`.
- [ ] Ajustar `tests/test_policy.py` e `tests/test_api_flow.py`.

### 1.3 Limite de orçamento
- [ ] O limite (`DEFAULT_DAILY_BUDGET_LIMIT`) deve existir **por workspace/cliente** no banco, não só global.
- [ ] Qualquer mudança de orçamento vira uma proposta separada com confirmação explícita, como já prevê o README.

### 1.4 CORS e headers
- [ ] Em produção, `CORS_ORIGINS` só com o domínio do painel.
- [ ] Rate limit por usuário e por IP (ex.: `slowapi`).
- [ ] Headers de segurança no Next.js (CSP, HSTS, X-Frame-Options).

**Pronto quando:** não existir nenhuma rota que funcione sem login, e o kill switch bloquear validação, aprovação e execução.

---

## Fase 2 — Persistência real (banco de dados) 🔴

- **Onde:** `apps/api/app/store.py` usa `InMemoryStore`. Planos, aprovações, auditoria e idempotência **somem quando o servidor reinicia**. No Railway com App Sleeping, isso acontece a toda hora.
- **Onde:** `config.py` tem `sqlite` como padrão; o `docker-compose` usa Postgres.

- [ ] Adicionar **Alembic** e criar as migrations.
- [ ] Criar tabelas: `plans` (com `version` e `content` JSONB), `approvals`, `audit_events`, `idempotency_keys`, `executions`, além das da Fase 1.
- [ ] Trocar todos os usos de `store.*` por consultas SQLAlchemy.
- [ ] Remover o `create_tables()` do startup e rodar migration no deploy.
- [ ] Usar **Postgres em produção** (Railway Postgres). SQLite só em testes.
- [ ] 🟠 Row Level Security por `organization_id`, como diz o `docs/SECURITY.md`.
- [ ] 🟠 Versionamento do plano: toda edição gera `version+1`, e a aprovação antiga deixa de valer, porque o hash muda.
- [ ] Trocar o `@app.on_event("startup")`, que está obsoleto, por `lifespan`.

**Pronto quando:** reiniciar a API e todos os planos, aprovações e auditorias continuarem lá.

---

## Fase 3 — Conexão OAuth com o Google completa 🔴

O que já existe: geração da URL OAuth, `state` assinado com HMAC e callback que troca o `code` por token e salva cifrado.

### 3.1 Callback
- [ ] Depois de salvar o token, **redirecionar para o painel** (`https://painel/integracoes?google=ok`) em vez de retornar JSON. Hoje o usuário cai numa tela de JSON da API.
- [ ] Tratar `error=access_denied`, quando o usuário cancela.
- [ ] Verificar se veio `refresh_token`. Se não vier, a conexão não serve (exige `prompt=consent`, que já está configurado).
- [ ] 🟠 Adicionar **PKCE** (`code_challenge`/`code_verifier`).
- [ ] 🟠 Tornar o `state` de **uso único**: guardar um nonce e invalidar depois de usar.

### 3.2 Escolha da conta de anúncio
- **Problema:** `provider_account_id` nunca é preenchido. O sistema não sabe qual conta do Google Ads foi conectada.
- [ ] Depois do OAuth, chamar `CustomerService.ListAccessibleCustomers`.
- [ ] Para MCC: listar a hierarquia (`customer_client`) e mostrar as subcontas com nome e ID.
- [ ] Tela para o usuário escolher **qual conta** associar a cada workspace/cliente.
- [ ] Salvar `customer_id` e `login_customer_id` (o ID da MCC, necessário no header da API).
- [ ] Permitir **várias contas por workspace**. A unique constraint atual (`org, workspace, provider`) permite só uma.

### 3.3 Tokens
- [ ] **Renovação automática** do access token com o refresh token. Na prática, a biblioteca `google-ads` faz isso sozinha se receber o refresh token.
- [ ] Lock de refresh para evitar duas renovações simultâneas.
- [ ] Botão **Desconectar**, que revoga o token em `https://oauth2.googleapis.com/revoke` e apaga do banco.
- [ ] Detectar token revogado (`invalid_grant`) e marcar a conexão como "reconectar".
- [ ] 🟠 Rotação da `TOKEN_ENCRYPTION_KEY` (Fernet `MultiFernet`).
- [ ] 🟠 Ideal: guardar segredos num vault (GCP Secret Manager, Doppler etc.) em vez de variável de ambiente pura.

### 3.4 Biblioteca
- [ ] Adicionar `google-ads` ao `pyproject.toml`, fixando a versão da API (ex.: `v21` ou a mais recente suportada).
- [ ] Criar `apps/api/app/google_ads/client.py`, que monta o `GoogleAdsClient` a partir do token do banco, do developer token e do `login_customer_id`.
- [ ] A biblioteca é síncrona: rodar as chamadas em `run_in_threadpool` ou num worker (Fase 6).

**Pronto quando:** você clicar em "Conectar com Google" no painel, autorizar, escolher a conta de teste e ela aparecer como conectada.

---

## Fase 4 — Leitura e auditoria automática (o que o Adspirer fez hoje) 🔴

Só leitura, sem risco, e já entrega valor.

### 4.1 Endpoints de leitura (GAQL)
- [ ] `GET /v1/google/campaigns`: nome, status, tipo, orçamento, estratégia de lance, redes (`network_settings`) e localização.
- [ ] `GET /v1/google/campaigns/{id}`: grupos, palavras-chave (texto, correspondência, status), anúncios RSA (títulos, descrições, força), negativas e extensões.
- [ ] `GET /v1/google/metrics?range=LAST_30_DAYS`: impressões, cliques, custo, conversões, CPC, CTR e custo por conversão, por campanha e por dia.
- [ ] `GET /v1/google/search-terms`: termos de pesquisa reais.
- [ ] `GET /v1/google/conversions`: ações de conversão, status, se é primária, conversões no período e se as conversões otimizadas estão ativas.
- [ ] Converter `cost_micros` ÷ 1.000.000 e usar `Decimal`.
- [ ] Cache curto (ex.: 15 min, no Redis) para não estourar a cota da API.

### 4.2 Auditoria automática (regras fixas, sem IA)
Cada regra devolve: severidade, achado, por que importa e correção sugerida.

- [ ] Campanha com Maximizar Conversões e **0 conversões em 30 dias** → 🔴
- [ ] Nenhuma conversão primária registrando no período → 🔴
- [ ] Conversões otimizadas desligadas → 🟠
- [ ] Pesquisa com **Display Expansion ligada** → 🟠
- [ ] Pesquisa com **Parceiros de Pesquisa ligados** → 🟡
- [ ] Campanha **sem palavras negativas** → 🟠
- [ ] Palavras-chave em correspondência ampla sem Smart Bidding com conversões → 🟡
- [ ] Força do anúncio "Ruim" ou "Média", ou RSA com menos de 15 títulos → 🟡
- [ ] Extensões repetidas ou contraditórias (ex.: "4 vagas" e "5 vagas") → 🟡
- [ ] Localização em "Presença ou interesse" → 🟡
- [ ] Gasto alto sem conversão em termo de pesquisa → 🟠 (sugerir negativa)
- [ ] Data de término passada ou próxima → 🟡
- [ ] Nota geral de 0 a 100, como o Adspirer mostra.

### 4.3 Painel
- [ ] Tela **Campanhas** com dados reais, substituindo o estado vazio.
- [ ] Tela **Métricas** com gráfico por dia.
- [ ] Tela **Auditoria da conta** com a lista de achados e um botão "Criar proposta de correção" para cada um.

**Pronto quando:** você conectar a conta de teste, ver as campanhas e as métricas, e a auditoria apontar os problemas certos.

---

## Fase 5 — Escrita real (criar e editar), sempre pausado 🔴

O que já existe: plano → validação → aprovação por hash → execução **simulada** (`simulated_execution`).

### 5.1 Executor real
- [ ] Criar `apps/api/app/google_ads/executor.py`, que substitui `simulated_execution`.
- [ ] Criar, numa única operação `GoogleAdsService.Mutate` com IDs temporários:
  - `CampaignBudget` (diário, `delivery_method=STANDARD`, sem compartilhar)
  - `Campaign`:
    - `SEARCH` com status **PAUSED**
    - `network_settings`: Search ligada; Parceiros e Display **desligados**
    - `geo_target_type_setting = PRESENCE`
    - estratégia de lance
    - declaração de anúncio político da UE como `DOES_NOT_CONTAIN`
  - `CampaignCriterion`: localização (via `GeoTargetConstantService.SuggestGeoTargetConstants`), idioma e **negativas**
  - `AdGroup`
  - `AdGroupCriterion`: palavras-chave com correspondência (frase ou exata por padrão)
  - `AdGroupAd`: RSA (até 15 títulos ≤30 caracteres, até 4 descrições ≤90 caracteres, URL final)
- [ ] **Primeiro `validate_only=True`**: o Google confere tudo sem criar nada. Mostrar os erros na tela antes da aprovação.
- [ ] Depois da aprovação, executar de verdade e salvar os resource names retornados (`customers/x/campaigns/y`).
- [ ] Tratar `GoogleAdsException`: mostrar `error.message` e o campo com erro, sem vazar dados sensíveis na auditoria.
- [ ] Idempotência: se a execução cair no meio, não duplicar a campanha (checar pelo nome + workspace antes de recriar).

### 5.2 Extensões (assets)
- [ ] Sitelinks, frases de destaque, snippet estruturado, nome da empresa e logo.

### 5.3 Edições em campanhas existentes (cada uma vira proposta → aprovação → execução)
- [ ] Ligar/desligar Parceiros e Display.
- [ ] Adicionar ou remover negativas, com uma lista compartilhada padrão "Imóveis alto padrão".
- [ ] Pausar, ativar e remover palavra-chave.
- [ ] Editar títulos e descrições do RSA.
- [ ] Trocar a estratégia de lance (Maximizar Cliques com teto de CPC ou Maximizar Conversões).
- [ ] Mudar a data de término.
- [ ] Pausar e retomar campanha.
- [ ] Mudar orçamento: **proposta financeira separada**, com a frase de confirmação.
- [ ] **Ativar campanha**: aprovação separada (`purpose="ACTIVATE"` já existe no modelo).

### 5.4 Conversões
- [ ] Criar ação de conversão (`ConversionActionService`): Lead, clique no WhatsApp e ligação.
- [ ] Devolver o snippet da tag (`tag_snippets`) para instalar no site ou no GTM.
- [ ] 🟠 Importação de conversão offline (lead qualificado e visita agendada) via `ConversionUploadService`, usando o GCLID salvo no formulário.

### 5.5 Desfazer
- [ ] Para cada execução, salvar o "antes" e o "depois" (diff).
- [ ] Botão **Reverter**, que gera uma proposta inversa.

**Pronto quando:** na conta de teste você criar uma campanha completa pelo painel, ela aparecer **pausada** no Google Ads, e uma edição (ex.: desligar Parceiros) funcionar e for registrada na auditoria.

---

## Fase 6 — Fila, worker e confiabilidade 🟠

- **Hoje:** a execução usa `BackgroundTasks` do FastAPI, que se perde se o processo reiniciar.
- [ ] Redis + **ARQ** (já previsto no ARCHITECTURE.md) para executar as mutações.
- [ ] Retry com backoff para erros temporários (`RESOURCE_EXHAUSTED`, `INTERNAL_ERROR`, timeout).
- [ ] Sem retry para erro de validação ou política.
- [ ] Dead-letter queue com alerta.
- [ ] Job de **reconciliação**: comparar periodicamente o que o banco acha que existe com o que existe no Google.
- [ ] Job de **sincronização de métricas** diária (madrugada) para o painel abrir rápido.
- [ ] Respeitar as cotas da API: até 15.000 operações/dia no acesso Básico; contar e alertar.

---

## Fase 7 — Painel (frontend) ligado aos dados reais 🟠

Hoje `apps/web/app/page.tsx` é praticamente uma vitrine com dados fixos.

- [ ] Remover os números falsos: "2 alterações pendentes", "24 ações da IA" e o badge "2" em Aprovações.
- [ ] Remover os dados de exemplo (KubeGame, `customer_id: "demo"`, período fixo de agosto/2026, `conversion_goal_ids: ["purchase"]`).
- [ ] O texto "Credenciais Google configuradas" só aparece se a API disser que estão configuradas (`GET /v1/providers`).
- [ ] O botão **Conectar com Google** precisa chamar `POST /v1/connections/GOOGLE_ADS/start` e redirecionar. Hoje só mostra um aviso.
- [ ] Tela de login e seletor de cliente/workspace.
- [ ] Fluxo completo na tela: briefing → plano (editável) → validação (com erros do `validate_only`) → aprovação → execução → resultado.
- [ ] Tela de aprovação com **diff** antes/depois.
- [ ] Tela de auditoria lendo `GET /v1/audit`.
- [ ] Dividir o `page.tsx` (tudo num arquivo só) em componentes e rotas (`/campanhas`, `/integracoes`, `/aprovacoes`...).
- [ ] Usar React Query/SWR para buscar dados e tratar estados de carregando e erro.

---

## Fase 8 — Modelos de campanha (o diferencial ALN) 🟢

Pode vir antes da IA e já resolve 80% dos casos.

- [ ] Cadastro de **Imóvel**: condomínio, bairro, cidade, preço, metragem, suítes, vagas, diferenciais, URL e fotos.
- [ ] Modelo **"Imóvel alto padrão — Pesquisa"** que gera automaticamente:
  - palavras-chave de frase e exata (`casa à venda {bairro}`, `{condomínio}`, `casa porteira fechada {bairro}`...)
  - lista de negativas padrão (aluguel, leilão, caixa, minha casa minha vida, planta, curso, emprego...)
  - títulos e descrições a partir da ficha, **sem contradições**
  - sitelinks e frases de destaque a partir da ficha
  - configuração segura: só Pesquisa, PRESENCE e Maximizar Cliques com teto até ter conversões
- [ ] Checagem de consistência: o mesmo número de vagas, suítes e m² em todos os textos.

---

## Fase 9 — IA (copiloto) 🟢

- [ ] Adicionar `openai_api_key` ao `config.py` (está no `.env.example`, mas não é lido).
- [ ] A IA **só gera propostas** no formato `GoogleSearchCampaignPlan` (Structured Outputs). Nunca recebe token nem chama a API do Google.
- [ ] Usos: sugerir palavras-chave e negativas, escrever títulos e descrições, explicar a auditoria e analisar termos de pesquisa.
- [ ] Validar todo output da IA com o Pydantic e o Policy Engine antes de mostrar.
- [ ] Nunca mandar token, e-mail ou dado sensível no prompt.
- [ ] Evals: um conjunto de briefings de teste com o resultado esperado.

---

## Fase 10 — Deploy e operação 🔴

### Railway
- [ ] Serviço `api`: Postgres e Redis do Railway ligados.
- [ ] Serviço `worker` (ARQ) separado.
- [ ] Serviço `web`.
- [ ] Domínio próprio com HTTPS (ex.: `app.alnperformance.com.br` e `api.alnperformance.com.br`).
- [ ] **Atenção ao App Sleeping:** o callback OAuth e o worker precisam estar acordados. Desligar o sleep na API e no worker em produção.

### Variáveis de ambiente (produção)
- [ ] `APP_ENV=production`
- [ ] `DATABASE_URL` (Postgres)
- [ ] `REDIS_URL`
- [ ] `PUBLIC_API_URL=https://api...` (precisa bater com a redirect URI do Google Cloud)
- [ ] `CORS_ORIGINS=https://app...`
- [ ] `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_ADS_DEVELOPER_TOKEN`
- [ ] `GOOGLE_ADS_LOGIN_CUSTOMER_ID` (ID da MCC, sem traços) — **criar no `config.py`**
- [ ] `TOKEN_ENCRYPTION_KEY`, gerada com `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- [ ] `OAUTH_STATE_SECRET`, uma string aleatória longa
- [ ] `GLOBAL_KILL_SWITCH=true` e `GOOGLE_ADS_MUTATIONS_ENABLED=false` até a Fase 5 estar testada
- [ ] Observação: o `docker-compose.yml` não define `TOKEN_ENCRYPTION_KEY` nem `OAUTH_STATE_SECRET`, então `GET /v1/providers` responde 503 localmente. Adicionar ao `.env` local.

### Observabilidade
- [ ] Logs estruturados (JSON) sem tokens nem dados sensíveis.
- [ ] Sentry (ou similar) na API, no worker e no web.
- [ ] Alertas: falha de execução, token revogado, cota da API perto do limite e DLQ com item.
- [ ] Backup diário do Postgres.

### CI (já existe `.github/workflows/ci.yml`)
- [ ] Adicionar `mypy`, que está nas dependências mas não roda no CI.
- [ ] Adicionar `npm run lint`.
- [ ] Testes de integração contra a **conta de teste** do Google, rodando manualmente ou à noite, com segredos no GitHub.
- [ ] Deploy automático no Railway só depois do CI verde.

---

## Fase 11 — Testes antes de virar a chave 🔴

- [ ] Fluxo completo na **conta de teste**: conectar → auditar → criar campanha pausada → editar → reverter → desconectar.
- [ ] Teste de isolamento: org A não enxerga nada da org B.
- [ ] Kill switch ligado → nenhuma mutação passa.
- [ ] Token revogado → o sistema detecta e pede reconexão.
- [ ] Aprovação de uma versão antiga do plano → é recusada.
- [ ] Mesmo `Idempotency-Key` enviado duas vezes → executa só uma vez.
- [ ] Orçamento acima do limite → bloqueado.
- [ ] URL de destino local ou privada → bloqueada (já existe, manter o teste).

---

## Fase 12 — Virada para contas reais (quando o acesso Básico sair)

- [ ] Trocar o Developer Token de teste pelo aprovado (é o mesmo token, só muda o nível de acesso).
- [ ] Trocar `GOOGLE_ADS_LOGIN_CUSTOMER_ID` pela MCC real.
- [ ] Conectar primeiro uma conta real **só em leitura** (kill switch ligado) e conferir a auditoria contra o que o Adspirer mostrou.
- [ ] Ligar `GOOGLE_ADS_MUTATIONS_ENABLED=true` e `GLOBAL_KILL_SWITCH=false`.
- [ ] Primeira mutação real: algo reversível e pequeno, como desligar Parceiros de Pesquisa na campanha Itahyê.

---

## Resumo da ordem

| # | Fase | Depende do Google? | Prioridade |
|---|------|--------------------|-----------|
| 0 | Credenciais e contas | Sim (iniciar já) | 🔴 |
| 1 | Correções de segurança | Não | 🔴 |
| 2 | Banco de dados | Não | 🔴 |
| 3 | OAuth completo + escolha de conta | Conta de teste | 🔴 |
| 4 | Leitura e auditoria | Conta de teste | 🔴 |
| 5 | Escrita real (pausada) | Conta de teste | 🔴 |
| 6 | Fila e worker | Não | 🟠 |
| 7 | Painel com dados reais | Não | 🟠 |
| 8 | Modelos de imóvel | Não | 🟢 |
| 9 | IA | Não | 🟢 |
| 10 | Deploy e operação | Não | 🔴 |
| 11 | Testes finais | Conta de teste | 🔴 |
| 12 | Contas reais | **Acesso Básico aprovado** | — |

**Ao fim da Fase 11, o sistema está 100% pronto e só aguardando a aprovação do Google.**
