"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useApp } from "@/components/app/AppContext";
import { Toast, customerId } from "@/components/app/ui";
import { Logo } from "@/components/ui";
import { PROVIDER_LABEL } from "@/lib/format";

const ICONS: Record<string, React.ReactNode> = {
  home: <><path d="m3 10 9-7 9 7"/><path d="M5 9v11h14V9M9 20v-6h6v6"/></>,
  spark: <><path d="m12 3 1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3Z"/><path d="m5 15 .8 2.2L8 18l-2.2.8L5 21l-.8-2.2L2 18l2.2-.8L5 15Z"/></>,
  campaign: <><path d="M4 6h16M4 12h10M4 18h7"/><circle cx="18" cy="15" r="3"/></>,
  metrics: <path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>,
  audit: <><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5M8 11l2 2 4-4"/></>,
  approve: <><rect x="3" y="3" width="18" height="18" rx="4"/><path d="m7 12 3 3 7-7"/></>,
  link: <><path d="M10 13a5 5 0 0 0 7.5.5l2-2a5 5 0 0 0-7-7l-1 1"/><path d="M14 11a5 5 0 0 0-7.5-.5l-2 2a5 5 0 0 0 7 7l1-1"/></>,
  history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></>,
  settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"/></>,
};

const NAV = [
  ["/app", "Visão geral", "home"], ["/app/copiloto", "Copiloto IA", "spark"], ["/app/campanhas", "Campanhas", "campaign"],
  ["/app/metricas", "Métricas", "metrics"], ["/app/auditoria", "Auditoria da conta", "audit"], ["/app/planos", "Planos e aprovações", "approve"],
  ["/app/integracoes", "Integrações", "link"], ["/app/historico", "Histórico", "history"], ["/app/configuracoes", "Configurações", "settings"],
] as const;

export function Shell({ children }: { children: React.ReactNode }) {
  const app = useApp();
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  useEffect(() => { setOpen(false); }, [pathname]);
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  async function logout() {
    try { await app.call("/v1/auth/logout", { method: "POST" }); } finally { router.replace("/entrar"); }
  }

  const active = (href: string) => (href === "/app" ? pathname === "/app" : pathname.startsWith(href));
  const live = app.system && !app.system.kill_switch;
  const initials = (app.me?.user.name ?? "?").split(" ").map(part => part[0]).slice(0, 2).join("").toUpperCase();

  return <div className="app-shell">
    <a className="skip-link" href="#conteudo">Pular para o conteúdo</a>
    {open && <div className="scrim" onClick={() => setOpen(false)} aria-hidden="true"/>}
    <aside className={`sidebar${open ? " open" : ""}`} id="app-sidebar" aria-label="Menu do painel">
      <Link className="brand" href="/app" aria-label="ALN Hub ia, visão geral"><Logo priority/></Link>
      {app.me && app.me.workspaces.length > 0 && <div className="ws-picker">
        <label htmlFor="ws">Cliente</label>
        <select id="ws" className="select" value={app.workspaceId ?? ""} onChange={event => { app.setWorkspaceId(event.target.value); router.push("/app"); }}>
          {app.me.workspaces.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}
        </select>
      </div>}
      <nav className="side-nav" aria-label="Seções">
        {NAV.map(([href, label, icon]) => <Link key={href} href={href} aria-current={active(href) ? "page" : undefined}>
          <svg viewBox="0 0 24 24" aria-hidden="true">{ICONS[icon]}</svg>{label}
        </Link>)}
      </nav>
      <div className="side-bottom">
        <div className={`mode-chip${live ? " live" : ""}`} title="Estado das alterações externas">
          <span aria-hidden="true">{live ? "●" : "✓"}</span>
          <div><b>{live ? "Alterações liberadas" : "Modo protegido"}</b><small>{live ? "Ainda exigem sua aprovação" : "Kill switch ligado: nada é aplicado"}</small></div>
        </div>
        <div className="user-row">
          <span className="avatar" aria-hidden="true">{initials}</span>
          <div><b>{app.me?.user.name ?? "…"}</b><small>{app.role === "owner" ? "Proprietário" : app.role === "admin" ? "Administrador" : "Leitura"}</small></div>
          <button type="button" onClick={logout}>Sair</button>
        </div>
      </div>
    </aside>
    <div className="app-main">
      <header className="topbar">
        <button className="menu-toggle" type="button" aria-label="Abrir menu" aria-expanded={open} aria-controls="app-sidebar" onClick={() => setOpen(true)}><span/><span/></button>
        {app.accounts.length > 0 && <label className="visually-hidden" htmlFor="account">Conta de anúncio</label>}
        {app.accounts.length > 0 && <select id="account" className="select" value={app.account?.id ?? ""} onChange={event => app.setAccountId(event.target.value)}>
          {app.accounts.map(a => <option key={a.id} value={a.id}>{PROVIDER_LABEL[a.provider]} · {a.name} ({customerId(a.external_id)}){a.is_test_account ? " · teste" : ""}</option>)}
        </select>}
        <label className="visually-hidden" htmlFor="days">Período</label>
        <select id="days" className="select" value={app.days} onChange={event => app.setDays(Number(event.target.value))}>
          {[7, 14, 30, 90].map(d => <option key={d} value={d}>Últimos {d} dias</option>)}
        </select>
        <span className="spacer"/>
        {app.system && !app.system.ai_enabled && <span className="badge" title="Configure OPENAI_API_KEY na API">IA em modo regras</span>}
      </header>
      <main className="app-content" id="conteudo">{children}</main>
    </div>
    <Toast toast={app.toast}/>
  </div>;
}
