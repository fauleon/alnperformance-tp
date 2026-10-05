import type { Metadata } from "next";
import Link from "next/link";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";
import { Arrow } from "@/components/ui";

export const metadata: Metadata = { title: "Página não encontrada", robots: { index: false, follow: false } };

export default function NotFound() {
  return <>
    <SiteHeader/>
    <main id="conteudo" className="not-found">
      <div className="container">
        <p className="code" aria-hidden="true">404</p>
        <h1>Esta página não existe.</h1>
        <p className="page-lead">O endereço pode ter mudado. Volte para o início ou entre no painel.</p>
        <div className="hero-actions"><Link className="button button-primary" href="/">Ir para o início <Arrow/></Link><Link className="button button-ghost" href="/entrar">Entrar no painel</Link></div>
      </div>
    </main>
    <SiteFooter/>
  </>;
}
