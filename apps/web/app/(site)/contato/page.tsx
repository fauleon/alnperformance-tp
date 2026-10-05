import type { Metadata } from "next";
import { Arrow, JsonLd, PageHero } from "@/components/ui";
import { pageGraph, pageMetadata } from "@/lib/seo";
import { contactEmail, phoneDisplay, social, whatsapp } from "@/lib/site";

const description = "Fale com a ALN Performance para liberar seu acesso ao ALN Hub ia, tirar dúvidas ou pedir suporte.";
export const metadata: Metadata = pageMetadata({ title: "Contato", description, path: "/contato" });

export default function ContactPage() {
  return <>
    <JsonLd data={pageGraph({ path: "/contato", name: "Contato | ALN Hub ia", description, type: "ContactPage", crumbs: [{ name: "Contato", path: "/contato" }] })}/>
    <PageHero kicker="Contato" title={<>Vamos conversar sobre <span className="grad">a sua mídia.</span></>} lead="Acesso, demonstração ou suporte: escolha o canal. Respondemos em horário comercial." crumbs={[{ name: "Contato", href: "/contato" }]}/>
    <section className="section">
      <div className="container contact-grid">
        <a className="contact-card" href={whatsapp("Olá, quero falar sobre o ALN Hub ia.")} target="_blank" rel="noopener noreferrer">
          <span>WhatsApp</span><strong>{phoneDisplay}</strong><span className="text-link">Abrir conversa <Arrow/></span>
        </a>
        <a className="contact-card" href={`mailto:${contactEmail}?subject=ALN%20Hub%20ia`}>
          <span>E-mail</span><strong>{contactEmail}</strong><span className="text-link">Escrever <Arrow/></span>
        </a>
        <div className="contact-card">
          <span>Redes</span><strong>ALN Digital</strong>
          {social.map(item => <a key={item.href} className="text-link" href={item.href} target="_blank" rel="noopener noreferrer">{item.label} <Arrow/></a>)}
        </div>
      </div>
      <div className="container"><p className="legal-meta">São Paulo, Brasil · atendimento em todo o país. Suporte técnico e pedidos de dados pessoais também por {contactEmail}.</p></div>
    </section>
  </>;
}
