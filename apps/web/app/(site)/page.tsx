import type { Metadata } from "next";
import Link from "next/link";
import { HeroArt } from "@/components/HeroArt";
import { Arrow, ClosingCta, Eyebrow, JsonLd } from "@/components/ui";
import { pageGraph, pageMetadata } from "@/lib/seo";
import { capabilities, ecosystem, whatsapp } from "@/lib/site";

const description = "Audite, planeje e opere Google Ads e TikTok Ads com inteligência artificial. Cada mudança mostra o antes e o depois e só vai ao ar com a sua aprovação.";
export const metadata: Metadata = pageMetadata({ title: "ALN Hub ia | Google Ads e TikTok Ads com IA", description, path: "/", absoluteTitle: true });

export default function Home() {
  return <>
    <JsonLd data={pageGraph({ path: "/", name: "ALN Hub ia", description })}/>

    <section className="hero">
      <div className="container hero-grid">
        <div>
          <Eyebrow>Uma solução ALN Performance · Ecossistema ALN Digital</Eyebrow>
          <h1>Sua mídia paga com IA. <em className="grad">Você no comando.</em></h1>
          <p className="hero-lead">O ALN Hub ia audita, planeja e opera suas campanhas de Google Ads e TikTok Ads com inteligência artificial. Ele propõe, mostra o impacto e espera a sua aprovação.</p>
          <div className="hero-actions">
            <Link className="button button-primary" href="/entrar">Entrar no painel <Arrow/></Link>
            <Link className="button button-ghost" href="/como-funciona">Ver como funciona</Link>
          </div>
        </div>
        <HeroArt/>
      </div>
      <div className="keyword-strip"><ul className="container"><li>Google Ads</li><li>TikTok Ads</li><li>Auditoria automática</li><li>Aprovação humana</li></ul></div>
    </section>

    <section className="section">
      <div className="container">
        <div className="section-head">
          <div><Eyebrow num="01">O que o Hub ia faz</Eyebrow><h2>Do diagnóstico à execução, <span className="muted">sem perder o controle.</span></h2></div>
          <p>Seis frentes, um fluxo só: a IA lê a conta, encontra o problema, prepara a correção e você decide.</p>
        </div>
        <ol className="cap-list">
          {capabilities.map(cap => <li key={cap.n}><Link href="/recursos">
            <span className="cap-n">{cap.n}</span><span className="cap-title">{cap.title}</span><span className="cap-type">{cap.type}</span><Arrow/>
          </Link></li>)}
        </ol>
        <div className="section-actions"><Link className="button button-ghost" href="/recursos">Ver todos os recursos <Arrow/></Link></div>
      </div>
    </section>

    <section className="section section-paper">
      <div className="container">
        <div className="section-head">
          <div><Eyebrow num="02">Como e por que confiar</Eyebrow><h2>A IA propõe. <span className="muted">Você aprova.</span></h2></div>
          <p>Toda alteração vira uma proposta com validação, aprovação vinculada ao conteúdo exato e histórico completo.</p>
        </div>
        <div className="duo">
          <Link className="duo-card" href="/como-funciona">
            <Eyebrow>Fluxo</Eyebrow>
            <h3>Como funciona</h3>
            <p>Conectar, auditar, propor, validar, aprovar e aplicar. Campanhas novas sempre nascem pausadas.</p>
            <span className="card-link">Conhecer o fluxo <Arrow/></span>
            <svg className="card-art" viewBox="0 0 200 200" aria-hidden="true"><circle cx="40" cy="160" r="12" fill="currentColor"/><circle cx="100" cy="100" r="12" fill="currentColor"/><circle cx="160" cy="40" r="12" fill="currentColor"/><path d="M40 160 100 100 160 40" stroke="currentColor" strokeWidth="4"/></svg>
          </Link>
          <Link className="duo-card" href="/seguranca">
            <Eyebrow>Controle</Eyebrow>
            <h3>Segurança e dados</h3>
            <p>Login oficial do Google e do TikTok, tokens cifrados, nenhuma senha ou cartão, e um botão que desliga tudo.</p>
            <span className="card-link">Ver as proteções <Arrow/></span>
            <svg className="card-art" viewBox="0 0 200 200" aria-hidden="true"><path d="M100 20 170 50v50c0 40-30 70-70 82-40-12-70-42-70-82V50z" fill="none" stroke="currentColor" strokeWidth="8"/></svg>
          </Link>
        </div>
      </div>
    </section>

    <section className="section">
      <div className="container">
        <div className="section-head">
          <div><Eyebrow num="03">Ecossistema ALN</Eyebrow><h2>Uma peça de um <span className="muted">ecossistema completo.</span></h2></div>
          <p>Estratégia, marca, tecnologia, infraestrutura, presença e mídia trabalhando juntas.</p>
        </div>
        <div className="eco-grid">
          {ecosystem.map(unit => <article key={unit.key} className={`eco-card${unit.url ? "" : " here"}`}>
            <div className="eco-top"><span>{unit.role}</span>{!unit.url && <span className="here-tag">VOCÊ ESTÁ AQUI</span>}</div>
            <h3>{unit.name}</h3>
            <p>{unit.text}</p>
            {unit.url
              ? <a className="eco-link" href={unit.url} target="_blank" rel="noopener noreferrer">Conhecer <Arrow/></a>
              : <Link className="eco-link" href="/recursos">Ver recursos <Arrow/></Link>}
          </article>)}
        </div>
      </div>
    </section>

    <ClosingCta title={<>Pare de adivinhar. <span>Comece a decidir.</span></>} text="Conecte sua conta e receba a auditoria completa em minutos. A ALN Performance acompanha a configuração com você." whatsappHref={whatsapp("Olá, quero conhecer o ALN Hub ia.")}/>
  </>;
}
