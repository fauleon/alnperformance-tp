import Link from "next/link";
import type { ReactNode } from "react";

export function Arrow({ className = "icon-arrow" }: { className?: string }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 19 19 5M5 5h14v14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}

/** Same lockup as the ALN Hub (gradient mark + "ALN Hub"), with a small "ia". */
export function Logo({ priority = false }: { priority?: boolean }) {
  return <>
    <span className="brand-mark" aria-hidden="true">
      <img src="/brand/aln-mark-72.webp" srcSet="/brand/aln-mark-72.webp 72w, /brand/aln-mark-108.webp 108w, /brand/aln-mark-144.webp 144w" sizes="38px" width={72} height={72} alt="" loading={priority ? "eager" : "lazy"} decoding="async"/>
    </span>
    <span className="brand-word">ALN <b>Hub</b><small>ia</small></span>
  </>;
}

export function BrandLink({ priority = false }: { priority?: boolean }) {
  return <Link className="brand" href="/" aria-label="ALN Hub ia, início"><Logo priority={priority}/></Link>;
}

/** JSON-LD is data, not executable script, so the CSP does not need to allow it. */
export function JsonLd({ data }: { data: object }) {
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data).replace(/</g, "\\u003c") }}/>;
}

export function Eyebrow({ num, children }: { num?: string; children: ReactNode }) {
  return <p className="eyebrow">{num ? <><span className="num">{num}</span> /</> : <span className="status-dot"/>} {children}</p>;
}

export function PageHero({ kicker, title, lead, crumbs, children }: { kicker: string; title: ReactNode; lead?: ReactNode; crumbs?: { name: string; href: string }[]; children?: ReactNode }) {
  return <section className="page-hero">
    <div className="container">
      {crumbs && <nav className="breadcrumbs" aria-label="Você está em"><Link href="/">Início</Link>{crumbs.map(c => <span key={c.href}>/ <Link href={c.href} aria-current="page">{c.name}</Link></span>)}</nav>}
      <Eyebrow>{kicker}</Eyebrow>
      <h1>{title}</h1>
      {lead && <p className="page-lead">{lead}</p>}
      {children}
    </div>
  </section>;
}

export function ClosingCta({ title, text, whatsappHref }: { title: ReactNode; text: string; whatsappHref: string }) {
  return <section className="closing" aria-labelledby="closing-title">
    <div className="container closing-grid">
      <div><p className="eyebrow">Pronto para começar?</p><h2 id="closing-title">{title}</h2></div>
      <div>
        <p>{text}</p>
        <div className="closing-buttons">
          <Link className="button button-dark" href="/entrar">Entrar no painel <Arrow/></Link>
          <a className="button button-ghost-dark" href={whatsappHref} target="_blank" rel="noopener noreferrer">Falar pelo WhatsApp <Arrow/></a>
        </div>
        <small>Acesso por convite da ALN Performance. Nenhuma alteração vai ao ar sem a sua aprovação.</small>
      </div>
      <svg className="closing-watermark" viewBox="0 0 400 260" aria-hidden="true"><path d="M8 240 C 120 236, 210 200, 262 140 S 350 40, 392 12" fill="none" stroke="currentColor" strokeWidth="3"/><circle cx="140" cy="226" r="9" fill="currentColor"/><circle cx="262" cy="140" r="9" fill="currentColor"/><circle cx="352" cy="44" r="9" fill="currentColor"/></svg>
    </div>
  </section>;
}
