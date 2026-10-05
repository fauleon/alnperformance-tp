"use client";

import { useState } from "react";
import { useApp } from "@/components/app/AppContext";
import { useSnapshot } from "@/components/app/hooks";
import { BarList, ErrorBox, Kpi, LineChart, Loading, NoAccount, PageHead } from "@/components/app/ui";
import { dateBR, dec, int, money, pct } from "@/lib/format";

type Metric = "cost" | "clicks" | "impressions" | "conversions";
const LABEL: Record<Metric, string> = { cost: "Investimento", clicks: "Cliques", impressions: "Impressões", conversions: "Conversões" };

export default function MetricsPage() {
  const { account, accounts, accountsLoading } = useApp();
  const snapshot = useSnapshot();
  const [metric, setMetric] = useState<Metric>("cost");

  if (!accountsLoading && accounts.length === 0) return <><PageHead eyebrow="Inteligência" title="Métricas"/><NoAccount/></>;
  const data = snapshot.data;
  const currency = data?.currency ?? account?.currency ?? "BRL";
  const format = (v: number) => (metric === "cost" ? money(v, currency) : metric === "conversions" ? dec(v) : int(v));

  return <>
    <PageHead eyebrow="Inteligência" title="Métricas" text="Desempenho diário da conta. Os dados são sincronizados toda madrugada e podem ser atualizados a qualquer momento."/>
    {snapshot.error ? <ErrorBox error={snapshot.error} onRetry={() => snapshot.mutate()}/> : !data ? <Loading/> : <>
      <div className="kpis">
        <Kpi label="Impressões" value={int(data.totals.impressions)}/>
        <Kpi label="Cliques" value={int(data.totals.clicks)}/>
        <Kpi label="CTR" value={pct(data.totals.ctr)}/>
        <Kpi label="Investimento" value={money(data.totals.cost, currency)}/>
        <Kpi label="Conversões" value={dec(data.totals.conversions)}/>
        <Kpi label="Custo/conversão" value={money(data.totals.cost_per_conversion, currency)}/>
      </div>
      <section className="card">
        <div className="card-head"><h2>{LABEL[metric]} por dia</h2>
          <div className="chart-switch" role="group" aria-label="Métrica do gráfico">{(Object.keys(LABEL) as Metric[]).map(m => <button key={m} type="button" aria-pressed={metric === m} onClick={() => setMetric(m)}>{LABEL[m]}</button>)}</div>
        </div>
        <LineChart label={`${LABEL[metric]} por dia`} points={data.by_day.map(d => ({ x: d.day.slice(5).split("-").reverse().join("/"), y: Number(d[metric]) }))} format={format}/>
      </section>
      <div className="grid-2">
        <section className="card"><div className="card-head"><h2>{LABEL[metric]} por campanha</h2></div>
          <BarList format={format} items={data.campaigns.map(c => ({ label: c.name, value: Number(c.metrics[metric]) })).sort((a, b) => b.value - a.value).slice(0, 10)}/>
        </section>
        <section className="card"><div className="card-head"><h2>Conversões registradas</h2><small>{data.enhanced_conversions_for_leads === false ? "Conversões otimizadas desligadas" : ""}</small></div>
          {data.conversion_actions.length === 0 ? <p className="muted">Nenhuma ação de conversão nesta conta.</p>
            : <ul className="list-plain">{data.conversion_actions.map(a => <li key={a.conversion_action_id} className="account-row"><span>{a.name}<small>{a.primary ? "Principal" : "Secundária"} · {a.status.toLowerCase()}</small></span><b>{dec(a.conversions)}</b></li>)}</ul>}
        </section>
      </div>
      <section className="card">
        <div className="card-head"><h2>Tabela diária</h2></div>
        <div className="table-wrap" tabIndex={0}><table className="table"><thead><tr><th>Dia</th><th className="num">Impressões</th><th className="num">Cliques</th><th className="num">CTR</th><th className="num">CPC</th><th className="num">Investimento</th><th className="num">Conversões</th></tr></thead><tbody>
          {[...data.by_day].reverse().map(d => <tr key={d.day}><td>{dateBR(d.day)}</td><td className="num">{int(d.impressions)}</td><td className="num">{int(d.clicks)}</td><td className="num">{pct(d.ctr)}</td><td className="num">{money(d.cpc, currency)}</td><td className="num">{money(d.cost, currency)}</td><td className="num">{dec(d.conversions)}</td></tr>)}
        </tbody></table></div>
      </section>
    </>}
  </>;
}
