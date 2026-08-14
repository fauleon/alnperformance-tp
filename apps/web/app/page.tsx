"use client";

import Image from "next/image";
import { useMemo, useState } from "react";

type Provider = "google" | "meta";
type Stage = "briefing" | "strategy" | "approval" | "executed";
const menu = [["◫", "Visão geral"], ["✦", "Copiloto IA"], ["◎", "Campanhas"], ["⌁", "Integrações"], ["✓", "Aprovações"], ["↗", "Métricas"], ["≡", "Auditoria"]];
const permissions = {
  google: ["Campanhas e grupos", "Anúncios e assets", "Palavras-chave e negativas", "Segmentação", "Lances e orçamento*", "Conversões e métricas"],
  meta: ["Campanhas e conjuntos", "Anúncios e criativos", "Públicos e posicionamentos", "Pixel e eventos", "Otimização e orçamento*", "Insights e métricas"],
};

export default function Home() {
  const [stage, setStage] = useState<Stage>("briefing");
  const [active, setActive] = useState("Visão geral");
  const [provider, setProvider] = useState<Provider>("google");
  const [company, setCompany] = useState("KubeGame Pro");
  const [offer, setOffer] = useState("Pacote completo de certificações por R$ 60");
  const [budget, setBudget] = useState("25");
  const [url, setUrl] = useState("https://kubegame.com.br");
  const [toast, setToast] = useState("");
  const [planId, setPlanId] = useState("");
  const [busy, setBusy] = useState(false);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const progress = useMemo(() => ({ briefing: 20, strategy: 60, approval: 80, executed: 100 }[stage]), [stage]);

  function notify(message: string) { setToast(message); window.setTimeout(() => setToast(""), 4200); }
  async function api(path: string, init: RequestInit = {}) {
    const response = await fetch(`${apiUrl}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(init.headers || {}) } });
    if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || "Não foi possível concluir a operação."); }
    return response.json();
  }
  async function generateStrategy() {
    setBusy(true);
    try {
      const created = await api("/v1/plans", { method: "POST", body: JSON.stringify({ customer_id: "demo", name: `${company} | Search | ALNAPI`, final_url: url, daily_budget: { amount: budget, currency: "BRL" }, period: { start: "2026-08-14", end: "2026-08-31" }, geo_targets: ["Brasil"], language_targets: ["pt-BR"], conversion_goal_ids: ["purchase"], campaign_negatives: ["grátis", "pirata", "dump"], ad_groups: [{ name: "Oferta principal", keywords: ["curso kubernetes", "certificação cloud", "treinamento devops"], headlines: [company, "Prepare-se com prática", "Pacote completo"], descriptions: [offer, "Conheça a oferta e comece agora."] }] }) });
      const validation = await api(`/v1/plans/${created.id}/validate`, { method: "POST" });
      if (!validation.allowed) throw new Error(validation.violations.join(" "));
      setPlanId(created.id); setStage("strategy"); notify("Estratégia gerada e validada com sucesso.");
    } catch (error) { notify(error instanceof Error ? error.message : "Falha inesperada."); } finally { setBusy(false); }
  }
  async function approvePlan() {
    setBusy(true); try { await api(`/v1/plans/${planId}/approve`, { method: "POST", body: JSON.stringify({ approved_by: "Felipe Auleon" }) }); setStage("approval"); notify("Plano aprovado e vinculado ao hash desta versão."); } catch (error) { notify(error instanceof Error ? error.message : "Falha inesperada."); } finally { setBusy(false); }
  }
  async function executePlan() {
    setBusy(true); try { await api(`/v1/plans/${planId}/execute`, { method: "POST", headers: { "Idempotency-Key": `web-${planId}` } }); setStage("executed"); notify("Campanha criada em modo seguro e mantida PAUSADA."); } catch (error) { notify(error instanceof Error ? error.message : "Falha inesperada."); } finally { setBusy(false); }
  }

  return <main className="shell">
    <aside className="sidebar">
      <button className="logo" onClick={() => setActive("Visão geral")} aria-label="ALNAPI — início"><span><Image src="/logoalnperformance.png" alt="ALN Performance" width={1280} height={1280} priority /></span><div><strong>ALNAPI</strong><small>AI ADS MANAGER</small></div></button>
      <nav>{menu.map(([icon, label]) => <button className={active === label ? "active" : ""} onClick={() => setActive(label)} key={label}><span>{icon}</span>{label}{label === "Aprovações" && <i>2</i>}</button>)}</nav>
      <div className="sidebarFooter"><div className="safe"><span>●</span><div><strong>Modo protegido</strong><small>Alterações exigem aprovação</small></div></div><div className="profile"><div className="avatar">FA</div><div><strong>Felipe Auleon</strong><small>Administrador</small></div><b>⋯</b></div></div>
    </aside>
    <section className="content">
      <header className="topbar"><div><span className="breadcrumb">ALN PERFORMANCE / <b>ALNAPI</b></span><h1>{active}</h1><p>Google Ads e Meta Ads operados por IA, com controle humano em cada mudança.</p></div><div className="topActions"><span className="live"><i/> SISTEMA PROTEGIDO</span><button className="bell">♢</button><div className="miniAvatar">FA</div></div></header>
      {active === "Integrações" ? <Integrations provider={provider} setProvider={setProvider} notify={notify} /> : <>
        <section className="heroStrip"><div><span className="eyebrow">CENTRAL DE OPERAÇÃO INTELIGENTE</span><h2>Planeje, edite e otimize <em>cada campanha.</em></h2><p>A IA recomenda e prepara alterações. Você confere, aprova e decide o que entra no ar.</p></div><div className="orbGraphic"><i/><i/><i/><strong>ALN<span>AI</span></strong></div></section>
        <div className="stats"><article><span className="icon cyan">◎</span><div><small>CONTAS CONECTADAS</small><strong>0 <i>aguardando conexão</i></strong></div></article><article><span className="icon pink">↗</span><div><small>ALTERAÇÕES PENDENTES</small><strong>2 <i>para sua aprovação</i></strong></div></article><article><span className="icon purple">✦</span><div><small>AÇÕES DA IA</small><strong>24 <i>esta semana</i></strong></div></article></div>
        <div className="workspaceGrid">
          <section className="panel formPanel"><div className="panelHead"><div><span>PLANO DE CAMPANHA</span><h3>Briefing inteligente</h3></div><b>RASCUNHO</b></div><div className="steps">{["Briefing", "Estratégia", "Validar", "Aprovar", "Aplicar"].map((item, index) => <div className={index * 20 < progress ? "done" : index * 20 === progress ? "current" : ""} key={item}><i>{index * 20 < progress ? "✓" : index + 1}</i><span>{item}</span></div>)}</div>
            <label>Empresa<input value={company} onChange={e => setCompany(e.target.value)} /></label><label>Oferta principal<textarea value={offer} onChange={e => setOffer(e.target.value)} /></label><div className="two"><label>Orçamento diário<div className="money"><span>R$</span><input value={budget} onChange={e => setBudget(e.target.value)} /></div></label><label>Canal<select value={provider} onChange={e => setProvider(e.target.value as Provider)}><option value="google">Google Ads</option><option value="meta">Meta Ads</option></select></label></div><label>Landing page<input value={url} onChange={e => setUrl(e.target.value)} /></label>
            <div className="budgetRule"><span>◈</span><p><b>Orçamento nunca é alterado automaticamente</b><small>A IA prepara a sugestão e pergunta: “O dinheiro já está disponível. Deseja aplicar?”</small></p></div><button className="primary" disabled={busy || provider === "meta"} onClick={generateStrategy}>{provider === "meta" ? "Planejador Meta — próxima etapa" : busy ? "Processando..." : "Gerar estratégia com IA"}<span>→</span></button>
          </section>
          <aside className="panel planPanel"><div className="panelHead"><div><span>PREVIEW EM TEMPO REAL</span><h3>Plano de execução</h3></div><b className="paused">PAUSADA</b></div><div className="providerTabs"><button className={provider === "google" ? "selected" : ""} onClick={() => setProvider("google")}><span className="g">G</span>Google Ads</button><button className={provider === "meta" ? "selected" : ""} onClick={() => setProvider("meta")}><span className="m">∞</span>Meta Ads</button></div>
            <div className="campaignCard"><div className="campaignTitle"><span className={provider === "google" ? "g" : "m"}>{provider === "google" ? "G" : "∞"}</span><div><strong>{company} | {provider === "google" ? "Search" : "Conversões"}</strong><small>{provider === "google" ? "Rede de Pesquisa" : "Instagram + Facebook"}</small></div><button>•••</button></div><div className="metrics"><div><small>DIÁRIO</small><strong>R$ {Number(budget || 0).toFixed(2).replace(".", ",")}</strong></div><div><small>MENSAL EST.</small><strong>R$ {(Number(budget || 0) * 30.4).toFixed(2).replace(".", ",")}</strong></div><div><small>STATUS</small><strong className="yellow">PAUSADA</strong></div></div></div>
            <div className="permissionBox"><div className="permissionTitle"><span>✦</span><div><strong>A IA poderá editar</strong><small>Somente após conexão e aprovação</small></div></div><div className="permissionGrid">{permissions[provider].map(item => <span key={item}>✓ {item}</span>)}</div></div><div className="guardrails"><h4>Guardrails ativos</h4>{["Nenhuma ação de pagamento", "Preview e diff antes de aplicar", "Ativação exige aprovação distinta", "Auditoria completa e reversível"].map(item => <div key={item}><span>✓</span>{item}</div>)}</div>
            {stage === "strategy" && <button className="primary compact" disabled={busy} onClick={approvePlan}>Validar e aprovar plano</button>}{stage === "approval" && <button className="primary compact" disabled={busy} onClick={executePlan}>Aplicar como campanha pausada</button>}{stage === "executed" && <div className="success"><b>✓ Criada em modo seguro</b><span>Gasto externo: R$ 0,00</span></div>}
          </aside>
        </div>
        <section className="integrationBar"><div><span className="gradientIcon">⌁</span><p><b>Conecte as contas para liberar leitura e edição</b><small>OAuth oficial, sem compartilhar senha ou código de autenticação.</small></p></div><button onClick={() => setActive("Integrações")}>Configurar integrações <span>→</span></button></section>
      </>}
    </section>{toast && <div className="toast"><span>✓</span>{toast}</div>}
  </main>;
}

function Integrations({ provider, setProvider, notify }: { provider: Provider; setProvider: (p: Provider) => void; notify: (m: string) => void }) {
  return <section className="integrationsPage"><div className="integrationHero"><span className="eyebrow">CONEXÕES OFICIAIS E SEGURAS</span><h2>Conecte as contas que a <em>ALNAPI</em> vai operar.</h2><p>Você autoriza o acesso diretamente no Google ou na Meta. A ALNAPI nunca recebe sua senha ou código 2FA.</p></div><div className="providerCards">
    <article className={provider === "google" ? "focus" : ""} onClick={() => setProvider("google")}><div className="providerTop"><span className="providerLogo google">G</span><div><small>GOOGLE</small><h3>Google Ads</h3></div><b>DESCONECTADO</b></div><p>Pesquisar, criar, pausar e editar campanhas, grupos, anúncios, assets, palavras-chave, negativas, públicos, conversões, lances e segmentações.</p><div className="scopeList">{permissions.google.map(x => <span key={x}>✓ {x}</span>)}</div><button onClick={() => notify("Configure GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET e Developer Token na Railway para conectar.")}>Conectar com Google <span>→</span></button></article>
    <article className={provider === "meta" ? "focus" : ""} onClick={() => setProvider("meta")}><div className="providerTop"><span className="providerLogo meta">∞</span><div><small>META</small><h3>Facebook & Instagram Ads</h3></div><b>DESCONECTADO</b></div><p>Ler, criar, pausar e editar campanhas, conjuntos, anúncios, criativos, públicos, posicionamentos, pixel, eventos e otimização.</p><div className="scopeList">{permissions.meta.map(x => <span key={x}>✓ {x}</span>)}</div><button onClick={() => notify("Configure META_APP_ID, META_APP_SECRET e a aprovação do App Review na Railway para conectar.")}>Conectar com Meta <span>→</span></button></article>
  </div><div className="moneyApproval"><div className="moneyGlow">R$</div><div><span>REGRA FINANCEIRA</span><h3>Dinheiro sempre sob seu controle</h3><p>A ALNAPI pode ler investimento, calcular projeções e sugerir orçamento. Antes de qualquer alteração, exibe o valor, o impacto e pergunta: <b>“O dinheiro já está disponível. Deseja aplicar?”</b></p></div><button onClick={() => notify("Regra financeira ativa: nenhuma alteração sem confirmação humana.")}>Ver fluxo de aprovação</button></div><div className="readiness"><span>!</span><div><b>O que falta para operar contas reais?</b><p>Credenciais dos aplicativos, Google Ads Developer Token, aprovação do Meta App Review, banco/vault e contas de teste. Até isso ser configurado, mutações reais permanecem desligadas.</p></div></div></section>;
}
