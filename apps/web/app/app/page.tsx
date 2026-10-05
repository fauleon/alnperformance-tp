"use client";

import Link from "next/link";
import { useApp, useApi } from "@/components/app/AppContext";
import { useAuditReport, useRefresh, useSnapshot } from "@/components/app/hooks";
import { Empty, ErrorBox, Kpi, LineChart, Loading, PageHead, ScoreRing, StatusBadge } from "@/components/app/ui";
import { Arrow } from "@/components/ui";
import { dec, int, KIND_LABEL, money, pct, SEVERITY_LABEL } from "@/lib/format";
import type { PlanSummary } from "@/lib/types";

export default function Overview() {
  const { me, account, accounts, accountsLoading, canEdit, system } = useApp();
  const snapshot = useSnapshot();
  const audit = useAuditReport();
  const plans = useApi<PlanSummary[]>("/v1/plans");
  const { refresh, busy } = useRefresh(() => { void snapshot.mutate(); void audit.mutate(); });
  const pending = (plans.data ?? []).filter(p => ["DRAFT", "VALIDATED", "APPROVED", "QUEUED"].includes(p.status));
  const currency = snapshot.data?.currency ?? account?.currency ?? "BRL";
  const firstName = me?.user.name.split(" ")[0];

  if (!accountsLoading && accounts.length === 0) {
    return <>
      <PageHead eyebrow="Primeiros passos" title={`Olá${firstName ? `, ${firstName}` : ""}. Vamos começar.`} text="Três passos para a primeira auditoria."/>
      <div className="grid-3">
        <div className="card"><p className="eyebrow">01</p><h2>Conectar</h2><p className="muted">Autorize o Google Ads ou o TikTok Ads pelo login oficial.</p></div>
        <div className="card"><p className="eyebrow">02</p><h2>Escolher a conta</h2><p className="muted">Selecione a conta de anúncio deste cliente (para MCC, a subconta).</p></div>
        <div className="card"><p className="eyebrow">03</p><h2>Ler a auditoria</h2><p className="muted">A conta é lida e os problemas aparecem com a correção sugerida.</p></div>
      </div>
      <div className="form-actions">{canEdit ? <Link className="button button-primary" href="/app/integracoes">Conectar uma conta <Arrow/></Link> : <p className="muted">Peça a um administrador para conectar a conta.</p>}</div>
    </>;
  }

  return <>
    <PageHead eyebrow={account ? `${account.name}` : "Visão geral"} title="Visão geral"
      text={snapshot.data ? `Período: ${snapshot.data.period_start.split("-").reverse().join("/")} a ${snapshot.data.period_end.split("-").reverse().join("/")}.` : undefined}
      actions={<>
        <button className="button button-ghost button-sm" type="button" onClick={refresh} disabled={busy || !account}>{busy ? "Atualizando…" : "Atualizar dados"}</button>
        {canEdit && <Link className="button button-primary button-sm" href="/app/planos/novo">Nova campanha <Arrow/></Link>}
      </>}/>

    {system?.kill_switch && <div className="alert alert-warn"><strong>Modo protegido ativo.</strong><span className="muted">Você pode ler, auditar e preparar propostas. A aplicação nas plataformas está desligada pelo kill switch.</span></div>}

    {snapshot.error ? <ErrorBox error={snapshot.error} onRetry={() => snapshot.mutate()}/> : !snapshot.data ? <Loading/> : <>
      <div className="kpis">
        <Kpi label="Investimento" value={money(snapshot.data.totals.cost, currency)}/>
        <Kpi label="Cliques" value={int(snapshot.data.totals.clicks)}/>
        <Kpi label="CTR" value={pct(snapshot.data.totals.ctr)}/>
        <Kpi label="CPC médio" value={money(snapshot.data.totals.cpc, currency)}/>
        <Kpi label="Conversões" value={dec(snapshot.data.totals.conversions)}/>
        <Kpi label="Custo/conversão" value={money(snapshot.data.totals.cost_per_conversion, currency)}/>
      </div>
      <div className="grid-main">
        <section className="card">
          <div className="card-head"><h2>Investimento por dia</h2><Link className="text-link" href="/app/metricas">Ver métricas <Arrow/></Link></div>
          <LineChart label="Investimento por dia" points={snapshot.data.by_day.map(d => ({ x: d.day.slice(5).split("-").reverse().join("/"), y: Number(d.cost) }))} format={v => money(v, currency)}/>
        </section>
        <section className="card">
          <div className="card-head"><h2>Auditoria da conta</h2><Link className="text-link" href="/app/auditoria">Abrir <Arrow/></Link></div>
          {audit.error ? <ErrorBox error={audit.error}/> : !audit.data ? <Loading/> : <>
            <div className="score"><ScoreRing score={audit.data.score}/><div><b>{audit.data.findings.length} achado(s)</b><p className="muted">{audit.data.summary.critical ?? 0} crítico(s), {audit.data.summary.high ?? 0} alto(s)</p></div></div>
            <ul className="list-plain" aria-label="Principais achados">
              {audit.data.findings.slice(0, 4).map((f, i) => <li key={`${f.rule}-${i}`} className={`finding ${f.severity}`}><div className="meta"><span className="badge">{SEVERITY_LABEL[f.severity]}</span>{f.campaign_name && <small className="muted">{f.campaign_name}</small>}</div><h3>{f.title}</h3></li>)}
            </ul>
          </>}
        </section>
      </div>
    </>}

    <section className="card">
      <div className="card-head"><h2>Propostas em andamento</h2><Link className="text-link" href="/app/planos">Todas <Arrow/></Link></div>
      {plans.error ? <ErrorBox error={plans.error}/> : !plans.data ? <Loading/> : pending.length === 0
        ? <Empty title="Nada aguardando você" text="Propostas criadas pela auditoria, pelo copiloto ou por você aparecem aqui até serem aplicadas."/>
        : <div className="table-wrap" tabIndex={0}><table className="table"><thead><tr><th>Proposta</th><th>Tipo</th><th>Status</th><th>Versão</th></tr></thead><tbody>
          {pending.slice(0, 6).map(p => <tr key={p.id}><td><Link className="row-button" href={`/app/planos/${p.id}`}>{p.title}</Link></td><td>{KIND_LABEL[p.kind]}</td><td><StatusBadge status={p.status}/></td><td>v{p.version}</td></tr>)}
        </tbody></table></div>}
    </section>
  </>;
}
