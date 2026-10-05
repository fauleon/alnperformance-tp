"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Arrow, BrandLink } from "@/components/ui";
import { navLinks } from "@/lib/site";

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLElement>(null);

  const close = useCallback((restoreFocus = false) => {
    setOpen(false);
    if (restoreFocus) toggleRef.current?.focus();
  }, []);

  useEffect(() => { document.body.classList.toggle("menu-open", open); }, [open]);

  useEffect(() => {
    if (!open) return;
    menuRef.current?.querySelector<HTMLAnchorElement>("a")?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") { close(true); return; }
      if (event.key !== "Tab" || !menuRef.current || !toggleRef.current) return;
      const items = [toggleRef.current, ...menuRef.current.querySelectorAll<HTMLAnchorElement>("a")];
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
    const desktop = matchMedia("(min-width: 1021px)");
    const onResize = (event: MediaQueryListEvent) => { if (event.matches) close(); };
    document.addEventListener("keydown", onKey);
    desktop.addEventListener("change", onResize);
    return () => { document.removeEventListener("keydown", onKey); desktop.removeEventListener("change", onResize); };
  }, [open, close]);

  const current = (href: string) => (pathname === href ? "page" : undefined);

  return <header className="site-header" id="topo">
    <div className="container header-inner">
      <BrandLink priority/>
      <nav className="desktop-nav" aria-label="Navegação principal">
        {navLinks.map(link => <Link key={link.href} href={link.href} aria-current={current(link.href)}>{link.label}</Link>)}
      </nav>
      <div className="header-actions">
        <Link className="button button-ghost button-sm" href="/entrar">Entrar</Link>
        <Link className="button button-primary button-sm" href="/contato">Falar com a ALN <Arrow/></Link>
        <button ref={toggleRef} className="menu-toggle" type="button" aria-label={open ? "Fechar menu" : "Abrir menu"} aria-expanded={open} aria-controls="mobile-menu" onClick={() => setOpen(value => !value)}><span/><span/></button>
      </div>
    </div>
    <nav ref={menuRef} className="mobile-menu" id="mobile-menu" aria-label="Navegação móvel" hidden={!open}>
      {navLinks.map(link => <Link key={link.href} href={link.href} aria-current={current(link.href)} onClick={() => close()}>{link.label}<Arrow/></Link>)}
      <Link href="/entrar" onClick={() => close()}>Entrar no painel <Arrow/></Link>
      <Link className="button button-primary" href="/contato" onClick={() => close()}>Falar com a ALN <Arrow/></Link>
    </nav>
  </header>;
}
