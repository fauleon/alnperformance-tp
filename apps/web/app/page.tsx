"use client";

import { useMemo, useState } from "react";

type Stage = "briefing" | "strategy" | "approval" | "executed";

const nav = ["Visão geral", "Estratégias", "Campanhas", "Aprovações", "Métricas", "Auditoria"];
const steps = ["Briefing", "Estratégia", "Validar", "Aprovar", "Criar pausada"];

export default function Home() {
  const [stage, setStage] = useState<Stage>("briefing");
  const [company, setCompany] = useState("KubeGame Pro");
  const [offer, setOffer] = useState("Pacote completo de certificações por R$ 60");
  const [budget, setBudget] = useState("25");
  const [url, setUrl] = useState("https://kubegame.com.br");
  const [toast, setToast] = useState("");
  const [planId, setPlanId] = useState("");
  const [busy, setBusy] = useState(false);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const progress = useMemo(() => ({ briefing: 20, strategy: 60, approval: 80, executed: 100 }[stage]), [stage]);

  function advance(next: Stage, message: string) {
    setStage(next); setToast(message); window.setTimeout(() => setToast(""), 3200);
  }

  async function api(path: string, init: RequestInit = {}) {
    const response = await fetch(`${apiUrl}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init.headers || {}) },
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || "Não foi possível concluir a operação.");
    }
    return response.json();
  }

  async function generateStrategy() {
    setBusy(true);
    try {
      const created = await api("/v1/plans", { method: "POST", body: JSON.stringify({
        customer_id: "demo", name: `${company} | Search | MVP`, final_url: url,
        daily_budget: { amount: budget, currency: "BRL" },
        period: { start: "2026-08-14", end: "2026-08-31" },
        geo_targets: ["Brasil"], language_targets: ["pt-BR"],
        conversion_goal_ids: ["purchase"], campaign_negatives: ["grátis", "pirata", "dump"],
        ad_groups: [{ name: "Oferta principal", keywords: ["curso kubernetes", "certificação cloud", "treinamento devops"], headlines: [company, "Prepare-se com prática", "Pacote completo"], descriptions: [offer, "Conheça a oferta e comece agora."] }],
      }) });
      const validation = await api(`/v1/plans/${created.id}/validate`, { method: "POST" });
      if (!validation.allowed) throw new Error(validation.violations.join(" "));
      setPlanId(created.id);
      advance("strategy", "Estratégia gerada e validada com sucesso.");
    } catch (error) { setToast(error instanceof Error ? error.message : "Falha inesperada."); }
    finally { setBusy(false); }
  }

  async function approvePlan() {
    setBusy(true);
    try {
      await api(`/v1/plans/${planId}/approve`, { method: "POST", body: JSON.stringify({ approved_by: "Felipe Auleon" }) });
      advance("approval", "Plano aprovado e vinculado ao hash desta versão.");
    } catch (error) { setToast(error instanceof Error ? error.message : "Falha inesperada."); }
    finally { setBusy(false); }
  }

  async function executePlan() {
    setBusy(true);
    try {
      await api(`/v1/plans/${planId}/execute`, { method: "POST", headers: { "Idempotency-Key": `web-${planId}` } });
      advance("executed", "Campanha criada em modo simulado e mantida PAUSADA.");
    } catch (error) { setToast(error instanceof Error ? error.message : "Falha inesperada."); }
    finally { setBusy(false); }
  }

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="brandMark">A</span><div><strong>ALN</strong><small>PERFORMANCE</small></div></div>
        <nav>{nav.map((item, i) => <button className={i === 0 ? "active" : ""} key={item}><span>{["⌂","✦","◎","✓","↗","≡"][i]}</span>{item}</button>)}</nav>
        <div className="safe"><span>●</span><div><strong>Modo seguro</strong><small>Mutações reais desligadas</small></div></div>
        <div className="profile"><div className="avatar">FA</div><div><strong>Felipe Auleon</strong><small>Administrador</small></div><b>⋯</b></div>
      </aside>

      <section className="content">
        <header><div><small>WORKSPACE / KUBEGAME PRO</small><h1>Nova campanha de pesquisa</h1><p>Da estratégia à criação pausada, com governança em cada etapa.</p></div><div className="headerActions"><button className="ghost">Salvar rascunho</button><button className="icon">?</button></div></header>

        <div className="stepper">{steps.map((s, i) => <div className={i * 20 < progress ? "done" : i * 20 === progress ? "current" : ""} key={s}><span>{i * 20 < progress ? "✓" : i + 1}</span><b>{s}</b></div>)}</div>

        <div className="grid">
          <section className="card formCard">
            <div className="cardTitle"><div><span className="eyebrow">ETAPA 01</span><h2>Conte sobre o negócio</h2><p>Essas informações orientam a estratégia e os anúncios.</p></div><span className="status">RASCUNHO</span></div>
            <label>Empresa<input value={company} onChange={e => setCompany(e.target.value)} /></label>
            <label>Oferta principal<textarea value={offer} onChange={e => setOffer(e.target.value)} /></label>
            <div className="two"><label>Orçamento diário<div className="money"><span>R$</span><input value={budget} onChange={e => setBudget(e.target.value)} /></div></label><label>Objetivo<select><option>Vendas</option><option>Leads</option><option>Tráfego</option></select></label></div>
            <label>Landing page<input value={url} onChange={e => setUrl(e.target.value)} /></label>
            <div className="notice"><b>🔒 Seus dados estão protegidos</b><span>A IA nunca recebe tokens, senhas ou informações financeiras.</span></div>
            <button className="primary" disabled={busy} onClick={generateStrategy}>{busy ? "Processando..." : "Gerar estratégia"} <span>→</span></button>
          </section>

          <aside className="card preview">
            <div className="previewHead"><div><span className="pulse"/>PREVIEW DO PLANO</div><span>Google Ads · Pesquisa</span></div>
            <div className="campaign"><div className="campaignTop"><span className="google">G</span><div><strong>{company || "Sua empresa"} | Search</strong><small>Campanha · <i>PAUSADA</i></small></div><button>⋯</button></div>
              <dl><div><dt>Orçamento diário</dt><dd>R$ {Number(budget || 0).toFixed(2).replace(".", ",")}</dd></div><div><dt>Projeção mensal</dt><dd>R$ {(Number(budget || 0) * 30.4).toFixed(2).replace(".", ",")}</dd></div><div><dt>Local</dt><dd>Brasil</dd></div><div><dt>Idioma</dt><dd>Português</dd></div></dl>
            </div>
            <div className="adgroup"><div><span>01</span><strong>Oferta principal</strong><b>3 anúncios</b></div><div className="chips"><span>curso kubernetes</span><span>certificação cloud</span><span>treinamento devops</span></div></div>
            <div className="checks"><h3>Verificações de segurança</h3>{["Status inicial pausado", "Orçamento dentro do limite", "URL com conexão segura", "Nenhuma ação de pagamento"].map(x => <div key={x}><span>✓</span>{x}</div>)}</div>
            {stage === "strategy" && <button className="approve" disabled={busy} onClick={approvePlan}>{busy ? "Processando..." : "Validar e aprovar plano"}</button>}
            {stage === "approval" && <button className="execute" disabled={busy} onClick={executePlan}>{busy ? "Enfileirando..." : "Criar campanha pausada"}</button>}
            {stage === "executed" && <div className="success"><b>✓ Campanha criada pausada</b><span>Gasto externo: R$ 0,00</span></div>}
          </aside>
        </div>

        <section className="assurance"><div><span>◉</span><p><b>Execução com aprovação humana</b><small>Nenhuma campanha é ativada ou gera gastos sem uma nova aprovação específica.</small></p></div><a href="#">Ver política de segurança →</a></section>
      </section>
      {toast && <div className="toast"><span>✓</span>{toast}</div>}
    </main>
  );
}
