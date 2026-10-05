"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useApp, useApi } from "@/components/app/AppContext";
import { ErrorBox, Loading, PageHead, StatusBadge, customerId } from "@/components/app/ui";
import { ApiError } from "@/lib/api";
import { int, PROVIDER_LABEL } from "@/lib/format";
import type { AdAccount, Connection, ProviderId, ProviderInfo } from "@/lib/types";

type Providers = { kill_switch: boolean; providers: ProviderInfo[]; google_operations_today: number; google_daily_quota: number };
type Connections = { connections: Connection[]; accounts: AdAccount[] };
const SLUG: Record<ProviderId, string> = { GOOGLE_ADS: "google", TIKTOK_ADS: "tiktok" };
const REASON: Record<string, string> = {
  state: "O link de autorização expirou ou já foi usado. Tente conectar de novo.",
  exchange: "A plataforma recusou a autorização. Tente de novo.",
  no_refresh_token: "O Google não devolveu acesso offline. Remova o ALN Hub ia em myaccount.google.com/permissions e conecte de novo.",
};

function Banner() {
  const params = useSearchParams();
  const status = params.get("status");
  if (!status) return null;
  const provider = params.get("provider") === "tiktok" ? "TikTok Ads" : "Google Ads";
  if (status === "connected") return <div className="alert alert-ok" role="status"><strong>{provider} conectado.</strong><span className="muted">Agora escolha abaixo qual conta de anúncio pertence a este cliente.</span></div>;
  if (status === "denied") return <div className="alert alert-warn" role="status"><strong>Autorização cancelada.</strong><span className="muted">Nada foi conectado.</span></div>;
  return <div className="alert alert-error" role="alert"><strong>Não foi possível conectar o {provider}.</strong><span className="muted">{REASON[params.get("reason") ?? ""] ?? "Tente novamente."}</span></div>;
}

export default function Integrations() {
  const { call, canEdit, notify, reloadAccounts } = useApp();
  const providers = useApi<Providers>("/v1/providers");
  const connections = useApi<Connections>("/v1/connections");
  const [busy, setBusy] = useState<string | null>(null);

  async function run(key: string, action: () => Promise<unknown>, success?: string) {
    setBusy(key);
    try {
      await action();
      if (success) notify("ok", success);
      await connections.mutate();
      reloadAccounts();
    } catch (error) {
      notify("error", error instanceof ApiError ? [error.message, ...error.problems.slice(0, 2)].join(" ") : "Falhou.");
    } finally {
      setBusy(null);
    }
  }

  async function connect(provider: ProviderId) {
    setBusy(`connect-${provider}`);
    try {
      const { authorization_url } = await call<{ authorization_url: string }>(`/v1/connections/${SLUG[provider]}/start`, { method: "POST" });
      window.location.assign(authorization_url);
    } catch (error) {
      notify("error", error instanceof ApiError ? error.message : "Não foi possível iniciar a conexão.");
      setBusy(null);
    }
  }

  const linked = new Set((connections.data?.accounts ?? []).map(a => `${a.provider}:${a.external_id}`));
  const quota = providers.data ? Math.round((providers.data.google_operations_today / providers.data.google_daily_quota) * 100) : 0;

  return <>
    <PageHead eyebrow="Conexões oficiais" title="Integrações" text="Autorize pelo login da própria plataforma. Sua senha nunca passa pelo ALN Hub ia e você pode revogar quando quiser."/>
    <Suspense><Banner/></Suspense>
    {providers.error ? <ErrorBox error={providers.error}/> : !providers.data ? <Loading/> : <>
      <div className="grid-2">{providers.data.providers.map(info => {
        const own = (connections.data?.connections ?? []).filter(c => c.provider === info.provider);
        return <section className="card" key={info.provider}>
          <div className="provider-head"><span className={`provider-logo ${info.provider === "GOOGLE_ADS" ? "google" : "tiktok"}`} aria-hidden="true">{info.provider === "GOOGLE_ADS" ? "G" : "♪"}</span>
            <div><h2>{info.name}</h2><span className="chips">{info.configured ? <span className="badge badge-ok">Credenciais do app configuradas</span> : <span className="badge badge-bad">Aguardando credenciais no servidor</span>}{info.mutations_enabled ? <span className="badge badge-warn">Escrita liberada</span> : <span className="badge">Somente leitura</span>}</span></div></div>
          <ul className="mini-list">{info.readable.slice(0, 6).map(item => <li key={item}>{item}</li>)}</ul>
          <details><summary className="muted">O que pode editar (sempre com aprovação)</summary><ul className="mini-list">{info.editable.map(item => <li key={item}>{item}</li>)}</ul><p className="muted">* Ativação e orçamento têm aprovação própria. Fora do escopo: {info.excluded.join(", ").toLowerCase()}.</p></details>
          {canEdit && <div className="form-actions"><button className="button button-primary" type="button" disabled={!info.configured || busy !== null} onClick={() => connect(info.provider)}>{busy === `connect-${info.provider}` ? "Abrindo…" : own.length ? `Conectar outra autorização` : `Conectar ${info.name}`}</button></div>}
          {own.map(connection => <div key={connection.id} className="card">
            <div className="card-head"><h2>Autorização de {new Date(connection.created_at).toLocaleDateString("pt-BR")} <StatusBadge status={connection.status}/></h2>
              {canEdit && <span className="form-actions">
                {connection.status === "ACTIVE" && <button className="button button-ghost button-sm" type="button" disabled={busy !== null} onClick={() => run(`disc-${connection.id}`, () => call(`/v1/connections/${connection.id}/discover`, { method: "POST" }), "Lista de contas atualizada.")}>Atualizar lista</button>}
                {connection.status !== "ACTIVE" && <button className="button button-primary button-sm" type="button" onClick={() => connect(info.provider)}>Reconectar</button>}
                <button className="button button-danger button-sm" type="button" disabled={busy !== null} onClick={() => { if (confirm("Desconectar revoga o acesso na plataforma e remove as contas vinculadas deste cliente. Continuar?")) void run(`del-${connection.id}`, () => call(`/v1/connections/${connection.id}`, { method: "DELETE" }), "Conexão revogada e removida."); }}>Desconectar</button>
              </span>}
            </div>
            {connection.last_error && <div className="alert alert-warn"><strong>{connection.last_error}</strong></div>}
            {connection.discovered_accounts.length === 0 ? <p className="muted">Nenhuma conta encontrada nesta autorização.</p> : connection.discovered_accounts.map(account => {
              const isLinked = linked.has(`${info.provider}:${account.external_id}`);
              return <div className="account-row" key={account.external_id}>
                <span><b>{account.name}</b><small>{customerId(account.external_id)}{account.parent_name ? ` · via ${account.parent_name}` : ""}{account.currency ? ` · ${account.currency}` : ""}{account.is_test_account ? " · conta de teste" : ""}{account.is_manager ? " · administradora (MCC)" : ""}</small></span>
                {isLinked ? <span className="badge badge-ok">Vinculada a este cliente</span>
                  : account.selectable && canEdit && connection.status === "ACTIVE"
                    ? <button className="button button-ghost button-sm" type="button" disabled={busy !== null} onClick={() => run(`link-${account.external_id}`, () => call(`/v1/connections/${connection.id}/accounts`, { method: "POST", body: { external_id: account.external_id } }), `${account.name} vinculada.`)}>Vincular a este cliente</button>
                    : <span className="badge">{account.is_manager ? "MCC" : "—"}</span>}
              </div>;
            })}
          </div>)}
        </section>;
      })}</div>

      <div className="grid-2">
        <section className="card">
          <div className="card-head"><h2>Contas vinculadas a este cliente</h2></div>
          {(connections.data?.accounts ?? []).length === 0 ? <p className="muted">Nenhuma ainda.</p> : connections.data!.accounts.map(account => <div className="account-row" key={account.id}>
            <span><b>{account.name}</b><small>{PROVIDER_LABEL[account.provider]} · {customerId(account.external_id)}{account.login_customer_id ? ` · MCC ${customerId(account.login_customer_id)}` : ""}</small></span>
            {canEdit && <button className="button button-ghost button-sm" type="button" disabled={busy !== null} onClick={() => run(`unlink-${account.id}`, () => call(`/v1/accounts/${account.id}`, { method: "DELETE" }), "Conta desvinculada.")}>Desvincular</button>}
          </div>)}
        </section>
        <section className="card">
          <div className="card-head"><h2>Proteções</h2></div>
          <dl className="kv">
            <div className="kv-row"><dt>Kill switch</dt><dd>{providers.data.kill_switch ? <span className="text-ok">Ligado — nada é aplicado nas plataformas</span> : <span className="text-warn">Desligado — aplicação liberada com aprovação</span>}</dd></div>
            <div className="kv-row"><dt>Cota Google hoje</dt><dd>{int(providers.data.google_operations_today)} de {int(providers.data.google_daily_quota)} operações ({quota}%)</dd></div>
            <div className="kv-row"><dt>Dinheiro</dt><dd>Toda mudança de orçamento pergunta: “O dinheiro já está disponível. Deseja aplicar?”</dd></div>
          </dl>
        </section>
      </div>
    </>}
  </>;
}
