"use client";

import { useState } from "react";

type Keyword = { text: string; match_type: "EXACT" | "PHRASE" | "BROAD" };
type Ad = { headlines: string[]; descriptions: string[]; path1?: string | null; path2?: string | null; final_url?: string | null };
type Group = { name: string; keywords: Keyword[]; negative_keywords?: Keyword[]; ads: Ad[]; cpc_bid?: { amount: string; currency: string } | null };
export type SearchPlan = {
  name: string; final_url: string; daily_budget: { amount: string; currency: string }; start_date: string; end_date: string | null;
  geo_target_ids: string[]; geo_target_names: string[]; bidding: { type: string; cpc_ceiling?: { amount: string; currency: string } | null; target_cpa?: { amount: string; currency: string } | null };
  ad_groups: Group[]; campaign_negatives: Keyword[]; callouts: string[]; sitelinks: { text: string; final_url: string; description1?: string | null; description2?: string | null }[];
  [key: string]: unknown;
};

/** Google Ads Editor notation: [exata], "frase", ampla sem marcação. */
export const keywordsToText = (list: Keyword[]) => list.map(k => (k.match_type === "EXACT" ? `[${k.text}]` : k.match_type === "PHRASE" ? `"${k.text}"` : k.text)).join("\n");
export function textToKeywords(text: string): Keyword[] {
  return text.split("\n").map(l => l.trim()).filter(Boolean).map(line => {
    const exact = line.match(/^\[(.+)\]$/);
    if (exact) return { text: exact[1], match_type: "EXACT" };
    const phrase = line.match(/^"(.+)"$/);
    if (phrase) return { text: phrase[1], match_type: "PHRASE" };
    return { text: line, match_type: "BROAD" };
  });
}
const toLines = (list: string[]) => list.join("\n");
const fromLines = (text: string) => text.split("\n").map(l => l.trim()).filter(Boolean);

function Counted({ label, value, onChange, limit, hint }: { label: string; value: string; onChange: (v: string) => void; limit: number; hint?: string }) {
  const lines = value.split("\n").filter(l => l.trim());
  const over = lines.filter(l => l.trim().length > limit);
  return <label className="field">{label} <small>{hint ?? `um por linha, até ${limit} caracteres`} · {lines.length} item(ns)</small>
    <textarea className="textarea" value={value} onChange={e => onChange(e.target.value)} aria-invalid={over.length > 0}/>
    {over.length > 0 && <small className="counter over">Acima do limite: {over.map(l => `“${l.trim()}” (${l.trim().length})`).join(", ")}</small>}
  </label>;
}

export function CampaignEditor({ initial, onSave, busy }: { initial: SearchPlan; onSave: (plan: SearchPlan) => void; busy: boolean }) {
  const [plan, setPlan] = useState<SearchPlan>(initial);
  const [groups, setGroups] = useState(initial.ad_groups.map(g => ({
    name: g.name, keywords: keywordsToText(g.keywords), negatives: keywordsToText(g.negative_keywords ?? []),
    headlines: toLines(g.ads[0]?.headlines ?? []), descriptions: toLines(g.ads[0]?.descriptions ?? []), path1: g.ads[0]?.path1 ?? "", path2: g.ads[0]?.path2 ?? "",
    extraAds: g.ads.slice(1), cpc: g.cpc_bid?.amount ?? "",
  })));
  const [negatives, setNegatives] = useState(keywordsToText(initial.campaign_negatives));
  const [callouts, setCallouts] = useState(toLines(initial.callouts ?? []));
  const [sitelinks, setSitelinks] = useState((initial.sitelinks ?? []).map(s => `${s.text} | ${s.final_url}`).join("\n"));
  const currency = plan.daily_budget.currency;
  const set = (patch: Partial<SearchPlan>) => setPlan(current => ({ ...current, ...patch }));
  const setGroup = (index: number, patch: Partial<(typeof groups)[number]>) => setGroups(current => current.map((g, i) => (i === index ? { ...g, ...patch } : g)));

  function save(event: React.FormEvent) {
    event.preventDefault();
    const bidding: SearchPlan["bidding"] = { type: plan.bidding.type };
    if (plan.bidding.type === "MAXIMIZE_CLICKS" && plan.bidding.cpc_ceiling?.amount) bidding.cpc_ceiling = { amount: plan.bidding.cpc_ceiling.amount, currency };
    if (plan.bidding.type === "MAXIMIZE_CONVERSIONS" && plan.bidding.target_cpa?.amount) bidding.target_cpa = { amount: plan.bidding.target_cpa.amount, currency };
    onSave({
      ...plan, bidding, end_date: plan.end_date || null, campaign_negatives: textToKeywords(negatives).map(k => ({ ...k, match_type: k.match_type === "BROAD" ? "PHRASE" : k.match_type })),
      callouts: fromLines(callouts),
      sitelinks: fromLines(sitelinks).map(l => l.split("|").map(p => p.trim())).filter(p => p.length === 2).map(([text, final_url]) => ({ text, final_url })),
      ad_groups: groups.map(g => ({
        name: g.name, keywords: textToKeywords(g.keywords), negative_keywords: textToKeywords(g.negatives),
        cpc_bid: plan.bidding.type === "MANUAL_CPC" && g.cpc ? { amount: Number(g.cpc).toFixed(2), currency } : null,
        ads: [{ headlines: fromLines(g.headlines), descriptions: fromLines(g.descriptions), path1: g.path1 || null, path2: g.path2 || null }, ...g.extraAds],
      })),
    });
  }

  return <form onSubmit={save}>
    <div className="form-grid">
      <label className="field">Nome da campanha<input className="input" value={plan.name} onChange={e => set({ name: e.target.value })} maxLength={128} required/></label>
      <label className="field">URL final<input className="input" type="url" value={plan.final_url} onChange={e => set({ final_url: e.target.value })} required/></label>
      <label className="field">Orçamento diário ({currency})<input className="input" type="number" step="0.01" min="0.01" value={plan.daily_budget.amount} onChange={e => set({ daily_budget: { amount: e.target.value, currency } })} required/></label>
      <div className="form-grid"><label className="field">Início<input className="input" type="date" value={plan.start_date} onChange={e => set({ start_date: e.target.value })} required/></label><label className="field">Término<input className="input" type="date" value={plan.end_date ?? ""} onChange={e => set({ end_date: e.target.value || null })}/></label></div>
      <label className="field">Estratégia de lance<select className="select" value={plan.bidding.type} onChange={e => set({ bidding: { type: e.target.value } })}><option value="MAXIMIZE_CLICKS">Maximizar cliques</option><option value="MAXIMIZE_CONVERSIONS">Maximizar conversões</option><option value="MANUAL_CPC">CPC manual</option></select></label>
      {plan.bidding.type === "MAXIMIZE_CLICKS" && <label className="field">Teto de CPC ({currency})<input className="input" type="number" step="0.01" min="0.01" value={plan.bidding.cpc_ceiling?.amount ?? ""} onChange={e => set({ bidding: { type: "MAXIMIZE_CLICKS", cpc_ceiling: e.target.value ? { amount: e.target.value, currency } : null } })}/></label>}
      {plan.bidding.type === "MAXIMIZE_CONVERSIONS" && <label className="field">CPA desejado ({currency}) <small>opcional</small><input className="input" type="number" step="0.01" min="0.01" value={plan.bidding.target_cpa?.amount ?? ""} onChange={e => set({ bidding: { type: "MAXIMIZE_CONVERSIONS", target_cpa: e.target.value ? { amount: e.target.value, currency } : null } })}/></label>}
      <p className="full muted">Localização: {(plan.geo_target_names.length ? plan.geo_target_names : plan.geo_target_ids).join(", ")} · segmentação por presença · só Rede de Pesquisa · criada pausada.</p>
    </div>
    {groups.map((g, i) => <fieldset key={i} className="card">
      <legend className="visually-hidden">Grupo {i + 1}</legend>
      <div className="form-grid">
        <label className="field">Grupo de anúncios<input className="input" value={g.name} onChange={e => setGroup(i, { name: e.target.value })} required/></label>
        {plan.bidding.type === "MANUAL_CPC" ? <label className="field">Lance CPC ({currency})<input className="input" type="number" step="0.01" value={g.cpc} onChange={e => setGroup(i, { cpc: e.target.value })} required/></label> : <span/>}
        <label className="field">Palavras-chave <small>[exata] · &quot;frase&quot; · ampla sem marcação</small><textarea className="textarea" value={g.keywords} onChange={e => setGroup(i, { keywords: e.target.value })} required/></label>
        <label className="field">Negativas do grupo <small>mesma notação</small><textarea className="textarea" value={g.negatives} onChange={e => setGroup(i, { negatives: e.target.value })}/></label>
        <Counted label="Títulos" value={g.headlines} onChange={v => setGroup(i, { headlines: v })} limit={30} hint="3 a 15, até 30 caracteres"/>
        <Counted label="Descrições" value={g.descriptions} onChange={v => setGroup(i, { descriptions: v })} limit={90} hint="2 a 4, até 90 caracteres"/>
        <label className="field">Caminho 1 <small>até 15</small><input className="input" value={g.path1} maxLength={15} onChange={e => setGroup(i, { path1: e.target.value })}/></label>
        <label className="field">Caminho 2 <small>até 15</small><input className="input" value={g.path2} maxLength={15} onChange={e => setGroup(i, { path2: e.target.value })}/></label>
      </div>
    </fieldset>)}
    <div className="form-grid card">
      <label className="field">Negativas da campanha <small>[exata] ou &quot;frase&quot;; sem marcação vira frase</small><textarea className="textarea" value={negatives} onChange={e => setNegatives(e.target.value)}/></label>
      <Counted label="Frases de destaque" value={callouts} onChange={setCallouts} limit={25}/>
      <label className="field full">Sitelinks <small>“Texto | URL”, um por linha (mínimo 2)</small><textarea className="textarea" value={sitelinks} onChange={e => setSitelinks(e.target.value)}/></label>
    </div>
    <div className="form-actions"><button className="button button-primary" disabled={busy}>{busy ? "Salvando…" : "Salvar nova versão"}</button><small className="muted">Salvar cria a versão seguinte e exige nova validação e aprovação.</small></div>
  </form>;
}
