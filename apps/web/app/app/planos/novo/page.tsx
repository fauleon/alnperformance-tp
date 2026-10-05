"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useApp } from "@/components/app/AppContext";
import { GeoPicker, type Geo } from "@/components/app/GeoPicker";
import { NoAccount, PageHead } from "@/components/app/ui";
import { ApiError } from "@/lib/api";
import type { PlanSummary } from "@/lib/types";

type Tab = "briefing" | "imovel" | "tiktok" | "json";
const lines = (value: FormDataEntryValue | null) => String(value ?? "").split("\n").map(l => l.trim()).filter(Boolean);
const today = () => new Date(Date.now() + 86400000).toISOString().slice(0, 10);

export default function NewPlan() {
  const { account, accounts, accountsLoading, call, canEdit, notify } = useApp();
  const router = useRouter();
  const google = account?.provider === "GOOGLE_ADS";
  const [tab, setTab] = useState<Tab | null>(null);
  const active: Tab = tab ?? (google ? "briefing" : "tiktok");
  const [geos, setGeos] = useState<Geo[]>([{ id: "2076", name: "Brasil" }]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  if (!accountsLoading && accounts.length === 0) return <><PageHead eyebrow="Planejamento" title="Novo plano"/><NoAccount/></>;
  if (!canEdit) return <><PageHead eyebrow="Planejamento" title="Novo plano"/><p className="muted">Seu papel é de leitura. Peça a um administrador para criar planos.</p></>;
  const currency = account?.currency ?? "BRL";

  async function submit(path: string, body: unknown) {
    setBusy(true);
    setError(null);
    try {
      const plan = await call<PlanSummary & { notes?: string }>(path, { method: "POST", body });
      notify("ok", plan.notes || "Plano criado. Revise, valide e aprove.");
      router.push(`/app/planos/${plan.id}`);
    } catch (failure) {
      setError(failure instanceof ApiError ? failure : new ApiError(0, "Não foi possível criar o plano."));
      setBusy(false);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }

  function briefing(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const f = new FormData(event.currentTarget);
    void submit("/v1/plans/from-briefing", {
      account_id: account!.id, use_keyword_ideas: f.get("ideas") === "on",
      briefing: { company: f.get("company"), offer: f.get("offer"), audience: f.get("audience") || "", landing_page: f.get("url"),
        seed_keywords: lines(f.get("seeds")), differentials: lines(f.get("differentials")),
        daily_budget: { amount: Number(f.get("budget")).toFixed(2), currency }, geo_target_ids: geos.map(g => g.id), geo_target_names: geos.map(g => g.name),
        start_date: f.get("start"), end_date: f.get("end") || null },
    });
  }

  function realEstate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const f = new FormData(event.currentTarget);
    const num = (key: string) => (f.get(key) ? Number(f.get(key)) : null);
    const sitelinks = lines(f.get("sitelinks")).map(l => l.split("|").map(p => p.trim())).filter(p => p.length === 2).map(([text, url]) => ({ text, final_url: url }));
    void submit("/v1/plans/from-real-estate", {
      account_id: account!.id,
      sheet: { title: f.get("title"), property_type: f.get("type"), condominium: f.get("condo") || null, neighborhood: f.get("hood"), city: f.get("city"),
        price: f.get("price") ? String(f.get("price")) : null, area_m2: num("area"), bedrooms: num("bedrooms"), suites: num("suites"), parking: num("parking"),
        differentials: lines(f.get("differentials")), url: f.get("url"), business_name: f.get("business") || null, sitelinks,
        daily_budget: { amount: Number(f.get("budget")).toFixed(2), currency },
        cpc_ceiling: f.get("cpc") ? { amount: Number(f.get("cpc")).toFixed(2), currency } : null,
        geo_target_ids: geos.map(g => g.id), geo_target_names: geos.map(g => g.name), start_date: f.get("start"), end_date: f.get("end") || null },
    });
  }

  function tiktok(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const f = new FormData(event.currentTarget);
    void submit("/v1/plans", {
      kind: "TIKTOK_CAMPAIGN", account_id: account!.id, content: {
        name: f.get("name"), objective: f.get("objective"), landing_page: f.get("url"),
        daily_budget: { amount: Number(f.get("budget")).toFixed(2), currency },
        ad_group: { name: f.get("group"), location_ids: String(f.get("locations")).split(/[,\s]+/).filter(Boolean),
          age_groups: f.getAll("age"), gender: f.get("gender"), optimization_goal: f.get("goal"),
          pixel_id: f.get("pixel") || null, optimization_event: f.get("event") || null, start_date: f.get("start"), end_date: f.get("end") || null },
      },
    });
  }

  function advanced(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const f = new FormData(event.currentTarget);
    let content: unknown;
    try { content = JSON.parse(String(f.get("json"))); } catch { setError(new ApiError(0, "JSON inválido.")); return; }
    void submit("/v1/plans", { kind: f.get("kind"), account_id: account!.id, content });
  }

  const tabs: [Tab, string, boolean][] = [["briefing", "Briefing (IA)", google], ["imovel", "Imóvel alto padrão", google], ["tiktok", "Campanha TikTok", !google], ["json", "Avançado (JSON)", true]];

  return <>
    <PageHead eyebrow="Planejamento" title="Novo plano" text={`Conta: ${account?.name ?? "—"}. O plano nasce como rascunho; nada é criado na plataforma até validação, aprovação e execução.`}/>
    <div className="tabs" role="tablist">{tabs.filter(([, , show]) => show).map(([id, label]) => <button key={id} type="button" role="tab" aria-selected={active === id} onClick={() => { setTab(id); setError(null); }}>{label}</button>)}</div>
    {error && <div className="alert alert-error" role="alert"><strong>{error.message}</strong>{error.problems.length > 0 && <ul>{error.problems.map(p => <li key={p}>{p}</li>)}</ul>}</div>}

    {active === "briefing" && <form className="card" onSubmit={briefing}>
      <div className="form-grid">
        <label className="field">Empresa ou marca<input className="input" name="company" required minLength={2} maxLength={80}/></label>
        <label className="field">Página de destino<input className="input" name="url" type="url" required placeholder="https://"/></label>
        <label className="field full">Oferta principal<textarea className="textarea" name="offer" required minLength={5} maxLength={300}/></label>
        <label className="field full">Público <small>(opcional)</small><input className="input" name="audience" maxLength={300}/></label>
        <label className="field">Palavras-semente <small>uma por linha</small><textarea className="textarea" name="seeds" required/></label>
        <label className="field">Diferenciais <small>uma por linha, viram títulos e frases</small><textarea className="textarea" name="differentials"/></label>
        <label className="field">Orçamento diário ({currency})<input className="input" name="budget" type="number" min="1" step="0.01" required inputMode="decimal"/></label>
        <div className="form-grid"><label className="field">Início<input className="input" name="start" type="date" required defaultValue={today()}/></label><label className="field">Término <small>(opcional)</small><input className="input" name="end" type="date"/></label></div>
        <div className="full"><GeoPicker value={geos} onChange={setGeos}/></div>
        <label className="checkbox full"><input type="checkbox" name="ideas" defaultChecked/> Usar o Planejador de Palavras-chave do Google (volume de busca) para enriquecer o plano</label>
      </div>
      <div className="form-actions"><button className="button button-primary" disabled={busy || geos.length === 0}>{busy ? "Gerando o plano…" : "Gerar plano"}</button><small className="muted">Com IA ativa, o copiloto organiza os grupos; sem ela, usamos o modelo padrão.</small></div>
    </form>}

    {active === "imovel" && <form className="card" onSubmit={realEstate}>
      <div className="form-grid">
        <label className="field">Título do anúncio do imóvel<input className="input" name="title" required minLength={3} maxLength={80} placeholder="Casa 4 suítes no Itahyê"/></label>
        <label className="field">Tipo<select className="select" name="type" defaultValue="casa"><option value="casa">Casa</option><option value="apartamento">Apartamento</option><option value="cobertura">Cobertura</option><option value="terreno">Terreno</option></select></label>
        <label className="field">Condomínio <small>(opcional)</small><input className="input" name="condo" maxLength={60}/></label>
        <label className="field">Bairro<input className="input" name="hood" required maxLength={60}/></label>
        <label className="field">Cidade<input className="input" name="city" required maxLength={60}/></label>
        <label className="field">Preço <small>(opcional)</small><input className="input" name="price" type="number" min="1" step="1"/></label>
        <label className="field">Área (m²)<input className="input" name="area" type="number" min="1"/></label>
        <label className="field">Quartos<input className="input" name="bedrooms" type="number" min="0"/></label>
        <label className="field">Suítes<input className="input" name="suites" type="number" min="0"/></label>
        <label className="field">Vagas<input className="input" name="parking" type="number" min="0"/></label>
        <label className="field">Página do imóvel<input className="input" name="url" type="url" required placeholder="https://"/></label>
        <label className="field">Nome da imobiliária <small>(até 25)</small><input className="input" name="business" maxLength={25}/></label>
        <label className="field">Diferenciais <small>um por linha</small><textarea className="textarea" name="differentials"/></label>
        <label className="field">Sitelinks <small>“Texto | URL”, um por linha (mín. 2)</small><textarea className="textarea" name="sitelinks" placeholder="Fotos | https://site.com.br/imovel/fotos"/></label>
        <label className="field">Orçamento diário ({currency})<input className="input" name="budget" type="number" min="1" step="0.01" required/></label>
        <label className="field">Teto de CPC <small>(recomendado)</small><input className="input" name="cpc" type="number" min="0.01" step="0.01"/></label>
        <div className="form-grid"><label className="field">Início<input className="input" name="start" type="date" required defaultValue={today()}/></label><label className="field">Término<input className="input" name="end" type="date"/></label></div>
        <div className="full"><GeoPicker value={geos} onChange={setGeos}/></div>
      </div>
      <div className="form-actions"><button className="button button-primary" disabled={busy || geos.length === 0}>{busy ? "Montando…" : "Montar campanha"}</button><small className="muted">Palavras de frase e exata, negativas do setor e textos sem contradição.</small></div>
    </form>}

    {active === "tiktok" && <form className="card" onSubmit={tiktok}>
      <div className="form-grid">
        <label className="field">Nome da campanha<input className="input" name="name" required minLength={3} maxLength={200}/></label>
        <label className="field">Objetivo<select className="select" name="objective" defaultValue="TRAFFIC"><option value="TRAFFIC">Tráfego</option><option value="LEAD_GENERATION">Geração de leads</option><option value="WEB_CONVERSIONS">Conversões no site</option><option value="REACH">Alcance</option><option value="VIDEO_VIEWS">Visualizações</option><option value="ENGAGEMENT">Engajamento</option></select></label>
        <label className="field">Página de destino<input className="input" name="url" type="url" required/></label>
        <label className="field">Orçamento diário ({currency})<input className="input" name="budget" type="number" min="1" step="0.01" required/></label>
        <label className="field">Nome do grupo de anúncios<input className="input" name="group" required minLength={2} maxLength={100}/></label>
        <label className="field">IDs de localização do TikTok <small>separados por vírgula</small><input className="input" name="locations" required placeholder="ex.: 3469034"/></label>
        <fieldset className="field full"><legend>Idade</legend><div className="chips">{["AGE_18_24", "AGE_25_34", "AGE_35_44", "AGE_45_54", "AGE_55_100"].map(a => <label className="checkbox" key={a}><input type="checkbox" name="age" value={a}/> {a.replace("AGE_", "").replace("_", "–").replace("100", "+")}</label>)}</div></fieldset>
        <label className="field">Gênero<select className="select" name="gender"><option value="GENDER_UNLIMITED">Todos</option><option value="GENDER_FEMALE">Feminino</option><option value="GENDER_MALE">Masculino</option></select></label>
        <label className="field">Otimizar para<select className="select" name="goal"><option value="CLICK">Cliques</option><option value="CONVERT">Conversões</option><option value="REACH">Alcance</option><option value="LEAD_GENERATION">Leads</option></select></label>
        <label className="field">Pixel <small>(conversões)</small><input className="input" name="pixel" inputMode="numeric"/></label>
        <label className="field">Evento de otimização<input className="input" name="event" placeholder="ex.: SUBMIT_FORM"/></label>
        <div className="form-grid full"><label className="field">Início<input className="input" name="start" type="date" required defaultValue={today()}/></label><label className="field">Término<input className="input" name="end" type="date"/></label></div>
      </div>
      <div className="form-actions"><button className="button button-primary" disabled={busy}>{busy ? "Criando…" : "Criar plano"}</button><small className="muted">Campanha e grupo são criados desativados. Os criativos (vídeos) são adicionados no Gerenciador de Anúncios do TikTok.</small></div>
    </form>}

    {active === "json" && <form className="card" onSubmit={advanced}>
      <div className="form-grid">
        <label className="field">Tipo<select className="select" name="kind" defaultValue={google ? "GOOGLE_CHANGE" : "TIKTOK_CHANGE"}>{google ? <><option value="GOOGLE_SEARCH_CAMPAIGN">Nova campanha Google</option><option value="GOOGLE_CHANGE">Alteração Google</option></> : <><option value="TIKTOK_CAMPAIGN">Nova campanha TikTok</option><option value="TIKTOK_CHANGE">Alteração TikTok</option></>}</select></label>
        <label className="field full">Conteúdo (o ID da conta é preenchido automaticamente)
          <textarea className="textarea code" name="json" required spellCheck={false} defaultValue={JSON.stringify(google ? { rationale: "", changes: [{ action: "SET_NETWORKS", campaign_id: "", search_partners: false, display_network: false }] } : { rationale: "", changes: [{ action: "SET_CAMPAIGN_STATUS", campaign_id: "", status: "DISABLE" }] }, null, 2)}/></label>
      </div>
      <div className="form-actions"><button className="button button-primary" disabled={busy}>Criar plano</button><Link className="text-link" href="/app/copiloto">Prefere pedir ao copiloto?</Link></div>
    </form>}
  </>;
}
