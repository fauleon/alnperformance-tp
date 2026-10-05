import Link from "next/link";
import { Arrow, BrandLink } from "@/components/ui";
import { contactEmail, ecosystem, phoneDisplay, social, whatsapp } from "@/lib/site";

export function SiteFooter() {
  return <footer className="site-footer">
    <div className="container footer-grid">
      <div className="footer-intro">
        <BrandLink/>
        <p>Google Ads e TikTok Ads com inteligência artificial, regras claras e você no comando de cada decisão.</p>
        <a className="footer-email" href={`mailto:${contactEmail}`}>{contactEmail}</a>
        <br/>
        <Link className="privacy-seal" href="/privacidade">Privacidade e proteção de dados · LGPD</Link>
      </div>
      <nav className="footer-column" aria-label="Navegue">
        <h2>Navegue</h2>
        <Link href="/recursos">Recursos</Link>
        <Link href="/como-funciona">Como funciona</Link>
        <Link href="/seguranca">Segurança e dados</Link>
        <Link href="/contato">Contato</Link>
        <Link href="/entrar">Entrar no painel</Link>
        <a href="https://alndigital.com.br/blog">Blog ALN</a>
      </nav>
      <nav className="footer-column" aria-label="Plataformas">
        <h2>Plataformas</h2>
        <Link href="/recursos#google-ads">Google Ads</Link>
        <Link href="/recursos#tiktok-ads">TikTok Ads</Link>
        <Link href="/recursos#auditoria">Auditoria automática</Link>
        <Link href="/recursos#copiloto">Copiloto de IA</Link>
        <Link href="/recursos#imoveis">Modelo para imóveis</Link>
      </nav>
      <nav className="footer-column" aria-label="Ecossistema ALN">
        <h2>Ecossistema ALN</h2>
        {ecosystem.map(unit => unit.url
          ? <a key={unit.key} href={unit.url} target="_blank" rel="noopener noreferrer">{unit.short} <Arrow/></a>
          : <Link key={unit.key} href="/">{unit.short} <span className="small-status">Você está aqui</span></Link>)}
      </nav>
      <div className="footer-column">
        <h2>Vamos nos conectar</h2>
        <a href={whatsapp()} target="_blank" rel="noopener noreferrer">WhatsApp {phoneDisplay} <Arrow/></a>
        {social.map(item => <a key={item.href} href={item.href} target="_blank" rel="noopener noreferrer">{item.label} <Arrow/></a>)}
        <p>São Paulo, Brasil. <br/>Atendimento em todo o país.</p>
      </div>
    </div>
    <div className="container footer-bottom">
      <div className="footer-legal">
        <span>© 2026 ALN Hub ia. Todos os direitos reservados.</span>
        <span>Uma solução <a href="https://alnperformance.com.br" target="_blank" rel="noopener noreferrer">ALN Performance</a> no ecossistema <a href="https://alndigital.com.br" target="_blank" rel="noopener noreferrer">ALN Digital</a>.</span>
      </div>
      <nav className="footer-links" aria-label="Institucional">
        <Link href="/privacidade">Privacidade</Link>
        <Link href="/termos">Termos de uso</Link>
        <a href="#topo">Voltar ao topo ↑</a>
      </nav>
    </div>
  </footer>;
}
