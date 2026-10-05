"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useApp } from "@/components/app/AppContext";
import { useCreatePlan, useRefresh, useSnapshot } from "@/components/app/hooks";
import { Empty, ErrorBox, Loading, NoAccount, PageHead, StatusBadge } from "@/components/app/ui";
import { BIDDING_LABEL, dateBR, dec, int, money, pct } from "@/lib/format";
import type { Campaign, Snapshot } from "@/lib/types";

type Tab = "groups" | "ads" | "negatives" | "terms";

export default function Campaigns() {
  const { account, accounts, accountsLoading } = useApp();
  const snapshot = useSnapshot();
  const { refresh, busy } = useRefresh(() => void snapshot.mutate());
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  if (!accountsLoading && accounts.length === 0) return <><PageHead eyebrow="Operação" title="Campanhas"/><NoAccount/></>;
  const data = snapshot.data;
  const currency = data?.currency ?? account?.currency ?? "BRL";
  const campaigns = (data?.campaigns ?? []).filter(c => c.name.toLowerCase().includes(filter.toLowerCase()));
  const current = data?.campaigns.find(c => c.campaign_id === selected) ?? null;

  return <>
    <PageHead eyebrow="Operação" title="Campanhas" text="Estrutura e desempenho de todas as campanhas da conta. Ações rápidas viram propostas para aprovação."
      actions={<button className="button button-ghost button-sm" type="button" onClick={refresh} disabled={busy}>{busy ? "Atualizando…" : "Atualizar dados"}</button>}/>
    {snapshot.error ? <ErrorBox error={snapshot.error} onRetry={() => snapshot.mutate()}/> : !data ? <Loading/> : data.campaigns.length === 0
      ? <Empty title="Nenhuma campanha nesta conta" text="Crie a primeira a partir de um briefing ou do modelo de imóvel." action={<a className="button button-primary" href="/app/planos/novo">Nova campanha</a>}/>
      : <>
        <div className="card">
          <div className="card-head"><h2>{data.campaigns.length} campanha(s)</h2>
            <label className="visually-hidden" htmlFor="filter">Filtrar campanhas</label>
            <input id="filter" className="input" placeholder="Filtrar por nome…" value={filter} onChange={e => setFilter(e.target.value)}/>
          </div>
          <div className="table-wrap" tabIndex={0}><table className="table">
            <thead><tr><th>Campanha</th><th>Status</th><th>Lance</th><th className="num">Orçamento/dia</th><th className="num">Custo</th><th className="num">Cliques</th><th className="num">CTR</th><th className="num">Conv.</th><th className="num">Custo/conv.</th></tr></thead>
            <tbody>{campaigns.map(c => <tr key={c.campaign_id}>
              <td><button className="row-button" type="button" aria-expanded={selected === c.campaign_id} onClick={() => setSelected(selected === c.campaign_id ? null : c.campaign_id)}>{c.name}</button><br/><small className="muted">{c.objective ?? c.channel} · {c.campaign_id}</small></td>
              <td><StatusBadge status={c.status}/></td>
              <td>{BIDDING_LABEL[c.bidding_strategy ?? ""] ?? c.bidding_strategy ?? "—"}</td>
              <td className="num">{money(c.daily_budget, currency)}</td>
              <td className="num">{money(c.metrics.cost, currency)}</td>
              <td className="num">{int(c.metrics.clicks)}</td>
              <td className="num">{pct(data.campaign_metrics[c.campaign_id]?.ctr)}</td>
              <td className="num">{dec(c.metrics.conversions)}</td>
              <td className="num">{money(data.campaign_metrics[c.campaign_id]?.cost_per_conversion, currency)}</td>
            </tr>)}</tbody>
          </table></div>
        </div>
        {current && <CampaignDetail campaign={current} snapshot={data} currency={currency}/>}
      </>}
  </>;
}

function CampaignDetail({ campaign, snapshot, currency }: { campaign: Campaign; snapshot: Snapshot; currency: string }) {
  const { canEdit } = useApp();
  const router = useRouter();
  const createPlan = useCreatePlan();
  const [tab, setTab] = useState<Tab>("groups");
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const google = snapshot.provider === "GOOGLE_ADS";
  const terms = useMemo(() => snapshot.search_terms.filter(t => t.campaign_id === campaign.campaign_id), [snapshot, campaign]);
  const enabled = campaign.status === "ENABLED";

  async function propose(content: Record<string, unknown>) {
    const kind = google ? "GOOGLE_CHANGE" : "TIKTOK_CHANGE";
    const key = google ? "customer_id" : "advertiser_id";
    const id = await createPlan(kind, { [key]: snapshot.account_id, ...content });
    if (id) router.push(`/app/planos/${id}`);
  }

  const statusChange = google
    ? { action: "SET_CAMPAIGN_STATUS", campaign_id: campaign.campaign_id, status: enabled ? "PAUSED" : "ENABLED" }
    : { action: "SET_CAMPAIGN_STATUS", campaign_id: campaign.campaign_id, status: enabled ? "DISABLE" : "ENABLE" };

  return <section className="card" aria-label={`Detalhes de ${campaign.name}`}>
    <div className="card-head">
      <div><h2>{campaign.name}</h2><small>{google ? `Redes: Pesquisa${campaign.search_partners ? " + Parceiros" : ""}${campaign.display_network ? " + Display" : ""} · Local: ${campaign.geo_target_type === "PRESENCE" ? "presença" : "presença ou interesse"}` : `Objetivo: ${campaign.objective}`} · {campaign.start_date ? `de ${dateBR(campaign.start_date)}` : ""} {campaign.end_date ? `até ${dateBR(campaign.end_date)}` : ""}</small></div>
      {canEdit && <div className="form-actions">
        <button className="button button-ghost button-sm" type="button" onClick={() => propose({ rationale: enabled ? "Pausar campanha." : "Ativar campanha.", changes: [statusChange] })}>{enabled ? "Propor pausa" : "Propor ativação"}</button>
        {google && (campaign.search_partners || campaign.display_network) && <button className="button button-ghost button-sm" type="button" onClick={() => propose({ rationale: "Manter só a Pesquisa do Google.", changes: [{ action: "SET_NETWORKS", campaign_id: campaign.campaign_id, search_partners: false, display_network: false }] })}>Desligar Parceiros e Display</button>}
        {google && campaign.geo_target_type === "PRESENCE_OR_INTEREST" && <button className="button button-ghost button-sm" type="button" onClick={() => propose({ rationale: "Segmentar por presença.", changes: [{ action: "SET_GEO_TARGET_TYPE", campaign_id: campaign.campaign_id, positive: "PRESENCE" }] })}>Usar só presença</button>}
      </div>}
    </div>
    <div className="tabs" role="tablist">
      {([["groups", "Grupos e palavras"], ["ads", "Anúncios"], ...(google ? [["negatives", `Negativas e extensões (${campaign.negatives.length})`], ["terms", `Termos de pesquisa (${terms.length})`]] : [])] as [Tab, string][]).map(([id, label]) =>
        <button key={id} role="tab" type="button" aria-selected={tab === id} onClick={() => setTab(id)}>{label}</button>)}
    </div>

    {tab === "groups" && (campaign.ad_groups.length === 0 ? <p className="muted">Sem grupos de anúncios.</p> : campaign.ad_groups.map(group => <div key={group.ad_group_id} className="card">
      <div className="card-head"><h2>{group.name} <StatusBadge status={group.status}/></h2><small>{money(group.metrics.cost, currency)} · {int(group.metrics.clicks)} cliques · {dec(group.metrics.conversions)} conv.</small></div>
      {group.keywords.length > 0 && <div className="table-wrap" tabIndex={0}><table className="table"><thead><tr><th>Palavra-chave</th><th>Corresp.</th><th>Status</th><th className="num">QS</th><th className="num">Custo</th><th className="num">Cliques</th><th className="num">Conv.</th>{canEdit && <th/>}</tr></thead><tbody>
        {group.keywords.map(k => <tr key={k.criterion_id}><td>{k.text}</td><td>{k.match_type.toLowerCase()}</td><td><StatusBadge status={k.status}/></td><td className="num">{k.quality_score ?? "—"}</td><td className="num">{money(k.metrics.cost, currency)}</td><td className="num">{int(k.metrics.clicks)}</td><td className="num">{dec(k.metrics.conversions)}</td>
          {canEdit && <td>{k.status === "ENABLED" && <button className="button button-ghost button-sm" type="button" onClick={() => propose({ rationale: `Pausar a palavra "${k.text}".`, changes: [{ action: "SET_KEYWORD_STATUS", ad_group_id: group.ad_group_id, criterion_id: k.criterion_id, status: "PAUSED" }] })}>Pausar</button>}</td>}</tr>)}
      </tbody></table></div>}
    </div>))}

    {tab === "ads" && <div className="grid-2">{campaign.ad_groups.flatMap(g => g.ads.map(ad => <div key={ad.ad_id} className="card">
      <div className="card-head"><h2>{g.name}</h2><span className="chips"><StatusBadge status={ad.status}/>{ad.ad_strength && <span className="badge">Força: {ad.ad_strength.toLowerCase()}</span>}</span></div>
      {google ? <div className="preview-ad"><small>Patrocinado · {ad.final_urls[0]?.replace(/^https?:\/\//, "").split("/")[0]}</small><h4>{ad.headlines.slice(0, 3).join(" | ")}</h4><p>{ad.descriptions.slice(0, 2).join(" ")}</p></div> : <p>{ad.headlines[0]} — {ad.descriptions[0]}</p>}
      {google && <details><summary className="muted">{ad.headlines.length} títulos · {ad.descriptions.length} descrições</summary><ul className="list-plain">{[...ad.headlines, ...ad.descriptions].map(t => <li key={t}>{t} <span className="counter">{t.length}</span></li>)}</ul></details>}
    </div>))}</div>}

    {tab === "negatives" && <div className="grid-2">
      <div><h3>Negativas</h3>{campaign.negatives.length === 0 ? <p className="text-warn">Nenhuma negativa nesta campanha.</p> : <div className="chips">{campaign.negatives.map((n, i) => <span className="chip" key={`${n.text}-${i}`}>{n.text} <small className="muted">{n.match_type.toLowerCase()}</small></span>)}</div>}</div>
      <div><h3>Extensões</h3>{campaign.assets.length === 0 ? <p className="text-warn">Nenhuma extensão na campanha.</p> : <ul className="list-plain">{campaign.assets.map((a, i) => <li key={i}><span className="badge">{a.type.toLowerCase()}</span> {a.text}</li>)}</ul>}</div>
    </div>}

    {tab === "terms" && <>
      {terms.length === 0 ? <p className="muted">Nenhum termo com clique no período.</p> : <>
        <div className="table-wrap" tabIndex={0}><table className="table"><thead><tr>{canEdit && <th><span className="visually-hidden">Selecionar</span></th>}<th>Termo pesquisado</th><th className="num">Cliques</th><th className="num">Custo</th><th className="num">Conv.</th></tr></thead><tbody>
          {terms.map(t => <tr key={t.term}>{canEdit && <td><input type="checkbox" aria-label={`Selecionar ${t.term}`} checked={picked.has(t.term)} onChange={e => setPicked(prev => { const next = new Set(prev); if (e.target.checked) next.add(t.term); else next.delete(t.term); return next; })}/></td>}
            <td>{t.term}</td><td className="num">{int(t.metrics.clicks)}</td><td className="num">{money(t.metrics.cost, currency)}</td><td className={`num${Number(t.metrics.conversions) === 0 && Number(t.metrics.cost) > 0 ? " text-bad" : ""}`}>{dec(t.metrics.conversions)}</td></tr>)}
        </tbody></table></div>
        {canEdit && <div className="form-actions"><button className="button button-primary button-sm" type="button" disabled={picked.size === 0}
          onClick={() => propose({ rationale: "Negativar termos sem aderência.", changes: [{ action: "ADD_NEGATIVES", campaign_id: campaign.campaign_id, keywords: [...picked].map(text => ({ text, match_type: "EXACT" })) }] })}>
          Negativar {picked.size || ""} termo(s) selecionado(s) em exata</button></div>}
      </>}
    </>}
  </section>;
}
