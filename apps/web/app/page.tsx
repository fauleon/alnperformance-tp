"use client";

import Image from "next/image";
import { useState } from "react";

type View = "Visão geral" | "Copiloto IA" | "Campanhas" | "Integrações" | "Aprovações" | "Métricas" | "Auditoria";
type Provider = "google" | "meta";

const nav: Array<[View, string]> = [["Visão geral", "⌂"], ["Copiloto IA", "✦"], ["Campanhas", "◫"], ["Integrações", "↗"], ["Aprovações", "✓"], ["Métricas", "⌁"], ["Auditoria", "≡"]];
const scopes = {
  google: ["Campanhas e grupos", "Anúncios e assets", "Palavras-chave e negativas", "Segmentações", "Lances e orçamento*", "Conversões e métricas"],
  meta: ["Campanhas e conjuntos", "Anúncios e criativos", "Públicos e posicionamentos", "Pixel e eventos", "Otimização e orçamento*", "Insights e métricas"],
};

function Arrow() { return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14m-5-5 5 5-5 5"/></svg>; }

export default function Home() {
  const [view, setView] = useState<View>("Visão geral");
  const [provider, setProvider] = useState<Provider>("google");
  const [company, setCompany] = useState("KubeGame Pro");
  const [offer, setOffer] = useState("Pacote completo de certificações por R$ 60");
  const [budget, setBudget] = useState("25");
  const [url, setUrl] = useState("https://kubegame.com.br");
  const [toast, setToast] = useState("");
  const [busy, setBusy] = useState(false);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const notify = (message: string) => { setToast(message); window.setTimeout(() => setToast(""), 4200); };

  async function generatePlan() {
    setBusy(true);
    try {
      const response = await fetch(`${apiUrl}/v1/plans`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ customer_id: "demo", name: `${company} | Search | ALNAPI`, final_url: url, daily_budget: { amount: budget, currency: "BRL" }, period: { start: "2026-08-15", end: "2026-08-31" }, geo_targets: ["Brasil"], language_targets: ["pt-BR"], conversion_goal_ids: ["purchase"], campaign_negatives: ["grátis", "pirata", "dump"], ad_groups: [{ name: "Oferta principal", keywords: ["curso kubernetes", "certificação cloud", "treinamento devops"], headlines: [company, "Prepare-se com prática", "Pacote completo"], descriptions: [offer, "Conheça a oferta e comece agora."] }] }) });
      if (!response.ok) throw new Error("Não foi possível gerar o plano agora.");
      notify("Estratégia criada. Revise tudo antes de aprovar.");
    } catch (error) { notify(error instanceof Error ? error.message : "Falha inesperada."); } finally { setBusy(false); }
  }

  return <main className="appShell">
    <aside className="sidebar">
      <button className="brand" onClick={() => setView("Visão geral")} aria-label="ALNAPI — início">
        <span className="brandCrop"><Image src="/aln-performance-logo.png" alt="ALN Performance" width={1280} height={1280} priority /></span>
        <span className="productName"><strong>ALNAPI</strong><small>ADS INTELLIGENCE</small></span>
      </button>
      <small className="navTitle">WORKSPACE</small>
      <nav>{nav.map(([label, icon]) => <button key={label} className={view === label ? "active" : ""} onClick={() => setView(label)}><i>{icon}</i><span>{label}</span>{label === "Aprovações" && <b>2</b>}</button>)}</nav>
      <div className="sideBottom"><div className="protected"><span>✓</span><div><b>Modo protegido</b><small>Aprovação humana ativa</small></div></div><div className="user"><i>FA</i><div><b>Felipe Auleon</b><small>Administrador</small></div><span>•••</span></div></div>
    </aside>

    <section className="mainContent">
      <header><div><small className="crumb">ALN PERFORMANCE <b>/</b> ALNAPI</small><h1>{view}</h1><p>Seu centro de comando para mídia paga, com inteligência e controle.</p></div><div className="headerTools"><span className="status"><i/> AMBIENTE PROTEGIDO</span><button aria-label="Notificações">◇</button><i className="avatar">FA</i></div></header>

      {view === "Integrações" ? <Integrations provider={provider} setProvider={setProvider} notify={notify}/> : <Dashboard provider={provider} setProvider={setProvider} company={company} setCompany={setCompany} offer={offer} setOffer={setOffer} budget={budget} setBudget={setBudget} url={url} setUrl={setUrl} busy={busy} generatePlan={generatePlan} openIntegrations={() => setView("Integrações")}/>}
    </section>
    {toast && <div className="toast" role="status"><b>✓</b>{toast}</div>}
  </main>;
}

type DashboardProps = { provider: Provider; setProvider: (v: Provider) => void; company: string; setCompany: (v: string) => void; offer: string; setOffer: (v: string) => void; budget: string; setBudget: (v: string) => void; url: string; setUrl: (v: string) => void; busy: boolean; generatePlan: () => void; openIntegrations: () => void };
function Dashboard(p: DashboardProps) {
  return <>
    <section className="hero"><div><span className="eyebrow"><i/> CENTRAL DE OPERAÇÃO INTELIGENTE</span><h2>Performance com contexto.<br/><em>Decisões com controle.</em></h2><p>Transforme briefing em campanhas prontas para revisão. A ALNAPI analisa, recomenda e prepara; você decide o que entra no ar.</p><div className="heroButtons"><button className="primary" onClick={() => document.getElementById("briefing")?.scrollIntoView({ behavior: "smooth" })}>Criar novo plano <Arrow/></button><button className="secondary" onClick={p.openIntegrations}>Conectar uma conta</button></div></div><div className="brandStage" aria-hidden="true"><div className="brandAura"/><div className="heroLogo"><Image src="/aln-performance-logo.png" alt="" width={1280} height={1280}/></div><span className="aiChip">ALN INTELLIGENCE <i>ONLINE</i></span><span className="dataChip">CONTROLE HUMANO <i>ATIVO</i></span></div></section>
    <section className="stats"><article><i className="cyan">↗</i><div><small>CONTAS CONECTADAS</small><b>0</b><span>Aguardando OAuth</span></div></article><article><i className="pink">✓</i><div><small>ALTERAÇÕES PENDENTES</small><b>2</b><span>Precisam da sua decisão</span></div></article><article><i className="purple">✦</i><div><small>AÇÕES DA IA</small><b>24</b><span>Nos últimos 7 dias</span></div></article></section>
    <div className="workGrid">
      <section className="panel" id="briefing"><div className="panelHead"><div><small>PLANO DE CAMPANHA</small><h3>Briefing inteligente</h3><p>Defina o essencial. A IA estrutura o restante.</p></div><b>RASCUNHO</b></div><div className="steps">{["Briefing", "Estratégia", "Validar", "Aprovar", "Aplicar"].map((x, i) => <span className={i === 0 ? "current" : ""} key={x}><i>{i + 1}</i><small>{x}</small></span>)}</div>
        <label>Empresa ou projeto<input value={p.company} onChange={e => p.setCompany(e.target.value)}/></label><label>Oferta principal<textarea value={p.offer} onChange={e => p.setOffer(e.target.value)}/></label><div className="two"><label>Orçamento diário<div className="money"><span>R$</span><input inputMode="decimal" value={p.budget} onChange={e => p.setBudget(e.target.value)}/></div></label><label>Canal<select value={p.provider} onChange={e => p.setProvider(e.target.value as Provider)}><option value="google">Google Ads</option><option value="meta">Meta Ads</option></select></label></div><label>Landing page<input type="url" value={p.url} onChange={e => p.setUrl(e.target.value)}/></label>
        <div className="moneyRule"><span>R$</span><div><b>Seu dinheiro, sua decisão</b><small>Nenhuma mudança financeira é aplicada sem sua confirmação.</small></div></div><button className="primary full" disabled={p.busy || p.provider === "meta"} onClick={p.generatePlan}>{p.provider === "meta" ? "Meta Ads — disponível em breve" : p.busy ? "Analisando briefing..." : "Gerar estratégia com IA"}<Arrow/></button>
      </section>
      <aside className="panel preview"><div className="panelHead"><div><small>PREVIEW EM TEMPO REAL</small><h3>Plano de execução</h3><p>Visualize antes de qualquer alteração.</p></div><b className="paused">PAUSADA</b></div><div className="tabs"><button className={p.provider === "google" ? "selected" : ""} onClick={() => p.setProvider("google")}><i className="google">G</i> Google Ads</button><button className={p.provider === "meta" ? "selected" : ""} onClick={() => p.setProvider("meta")}><i className="meta">∞</i> Meta Ads</button></div>
        <div className="campaign"><div><i className={p.provider === "google" ? "google" : "meta"}>{p.provider === "google" ? "G" : "∞"}</i><span><b>{p.company} | {p.provider === "google" ? "Search" : "Conversões"}</b><small>{p.provider === "google" ? "Rede de Pesquisa" : "Instagram + Facebook"}</small></span><button>•••</button></div><section><span><small>DIÁRIO</small><b>R$ {Number(p.budget || 0).toFixed(2).replace(".", ",")}</b></span><span><small>MENSAL EST.</small><b>R$ {(Number(p.budget || 0) * 30.4).toFixed(2).replace(".", ",")}</b></span><span><small>STATUS</small><b className="yellow">PAUSADA</b></span></section></div>
        <div className="scope"><h4>✦ Escopo da inteligência</h4><p>Só executa depois da sua aprovação</p><div>{scopes[p.provider].map(x => <span key={x}><i>✓</i>{x}</span>)}</div></div><div className="guards"><h4>Proteções desta operação</h4>{["Nenhuma ação de pagamento", "Comparação antes de aplicar", "Ativação exige aprovação separada", "Histórico completo e reversível"].map(x => <span key={x}><i>✓</i>{x}</span>)}</div>
      </aside>
    </div>
    <section className="connectBar"><div><i>↗</i><span><b>Suas contas ainda não estão conectadas</b><small>OAuth oficial, sem compartilhar senha ou código de autenticação.</small></span></div><button className="secondary" onClick={p.openIntegrations}>Configurar integrações <Arrow/></button></section>
  </>;
}

function Integrations({ provider, setProvider, notify }: { provider: Provider; setProvider: (v: Provider) => void; notify: (v: string) => void }) {
  return <section className="integrations"><div className="integrationIntro"><span className="eyebrow"><i/> CONEXÕES OFICIAIS E SEGURAS</span><h2>Uma ponte segura entre a<br/><em>estratégia e a execução.</em></h2><p>Autorize diretamente no Google ou na Meta. Sua senha e seu código de autenticação nunca passam pela ALNAPI.</p></div><div className="providerCards">
    {(["google", "meta"] as Provider[]).map(item => <article key={item} className={provider === item ? "focus" : ""} onClick={() => setProvider(item)}><div className="providerHead"><i className={item}>{item === "google" ? "G" : "∞"}</i><span><small>{item === "google" ? "GOOGLE" : "META"}</small><h3>{item === "google" ? "Google Ads" : "Facebook & Instagram"}</h3></span><b>{item === "google" ? "PRONTO PARA CONECTAR" : "EM BREVE"}</b></div><p>Leia, revise e gerencie toda a estrutura da conta com rastreabilidade e aprovação humana.</p><div className="scopeList">{scopes[item].map(x => <span key={x}><i>✓</i>{x}</span>)}</div><button className={item === "google" ? "primary full" : "secondary full"} onClick={e => { e.stopPropagation(); notify(item === "google" ? "O OAuth será ligado depois desta revisão visual." : "Meta Ads será configurado em uma próxima etapa."); }}>{item === "google" ? "Conectar com Google" : "Ver escopo planejado"}<Arrow/></button></article>)}
  </div><section className="finance"><i>R$</i><div><small>REGRA FINANCEIRA</small><h3>Dinheiro sempre sob seu controle</h3><p>A ALNAPI sugere orçamento, mostra o impacto e pergunta: <b>“O dinheiro já está disponível. Deseja aplicar?”</b></p></div><button className="secondary" onClick={() => notify("Proteção ativa: nenhuma mudança financeira sem confirmação.")}>Entender a proteção</button></section><div className="ready"><b>✓</b><span><strong>Ambiente protegido</strong><p>Credenciais Google configuradas. Mutações reais continuam desligadas até conexão, testes e aprovação explícita.</p></span></div></section>;
}
