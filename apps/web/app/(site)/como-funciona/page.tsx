import type { Metadata } from "next";
import { ClosingCta, Eyebrow, JsonLd, PageHero } from "@/components/ui";
import { pageGraph, pageMetadata } from "@/lib/seo";
import { whatsapp } from "@/lib/site";

const description = "Conectar, auditar, propor, validar, aprovar e aplicar: o fluxo do ALN Hub ia para Google Ads e TikTok Ads, com campanhas criadas sempre pausadas.";
export const metadata: Metadata = pageMetadata({ title: "Como funciona", description, path: "/como-funciona" });

const steps = [
  ["01", "Conectar", "Você autoriza no Google ou no TikTok e escolhe a conta de anúncio. Sua senha nunca passa pelo Hub ia."],
  ["02", "Auditar", "A conta é lida e as regras da auditoria apontam o que corrigir, com nota de 0 a 100."],
  ["03", "Propor", "Você, o copiloto ou a própria auditoria cria uma proposta: campanha nova ou alteração."],
  ["04", "Validar e aprovar", "A política confere limites e destino; o Google confere a estrutura sem criar nada. Você aprova a versão exata."],
  ["05", "Aplicar e acompanhar", "A execução roda em fila, registra o antes e o depois e pode ser revertida com uma nova proposta."],
];

const faq = [
  ["O Hub ia ativa campanhas sozinho?", "Não. Campanhas novas são criadas pausadas. Ativar é uma aprovação separada, feita por uma pessoa com permissão."],
  ["E se o plano mudar depois que eu aprovei?", "A aprovação fica presa à versão e ao conteúdo exatos do plano. Qualquer edição gera uma nova versão e exige nova aprovação."],
  ["Posso mudar o orçamento pelo Hub ia?", "Pode, como proposta separada. Antes de aprovar você confirma: “O dinheiro já está disponível. Deseja aplicar?”. Cada cliente também tem um limite de orçamento diário."],
  ["O Hub ia mexe em cartão, cobrança ou saldo?", "Não. Pagamentos, meios de cobrança e adição de saldo não existem no sistema e continuam nas plataformas."],
  ["Dá para desfazer uma alteração?", "Sim. Cada execução guarda o estado anterior; o botão Reverter cria a proposta inversa, que passa pela aprovação como qualquer outra."],
  ["Quais plataformas são atendidas?", "Google Ads (Rede de Pesquisa) e TikTok Ads."],
  ["Preciso dar acesso de administrador à minha conta?", "Você autoriza pelo login oficial da plataforma e pode revogar a qualquer momento, no Hub ia (Desconectar) ou nas configurações da sua conta Google ou TikTok."],
];

export default function HowItWorksPage() {
  const faqNode = { "@type": "FAQPage", mainEntity: faq.map(([q, a]) => ({ "@type": "Question", name: q, acceptedAnswer: { "@type": "Answer", text: a } })) };
  const howTo = { "@type": "HowTo", name: "Como o ALN Hub ia opera uma campanha", step: steps.map(([, name, text], i) => ({ "@type": "HowToStep", position: i + 1, name, text })) };
  return <>
    <JsonLd data={pageGraph({ path: "/como-funciona", name: "Como funciona | ALN Hub ia", description, crumbs: [{ name: "Como funciona", path: "/como-funciona" }], extra: [howTo, faqNode] })}/>
    <PageHero kicker="Como funciona" title={<>Da autorização à execução — <span className="grad">nunca direto para o ar.</span></>} lead="Cada etapa crítica preserva o seu controle. A IA acelera; a decisão continua sendo sua." crumbs={[{ name: "Como funciona", href: "/como-funciona" }]}/>

    <section className="section">
      <div className="container">
        <Eyebrow num="01">O fluxo</Eyebrow>
        <h2 className="visually-hidden">Etapas</h2>
        <ol className="steps" aria-label="Etapas do fluxo">{steps.map(([n, title, text]) => <li key={n}><b>{n}</b><h3>{title}</h3><p>{text}</p></li>)}</ol>
      </div>
    </section>

    <section className="section section-paper">
      <div className="container split">
        <div><Eyebrow num="02">Proteções em cada etapa</Eyebrow><h2>Regras que não dependem de boa vontade.</h2></div>
        <ul className="check-list">
          <li>Kill switch global: com ele ligado, nenhuma alteração chega às plataformas.</li>
          <li>Limite de orçamento diário por cliente, definido pelo proprietário da conta.</li>
          <li>URLs de destino locais, privadas ou com senha são bloqueadas.</li>
          <li>Aprovação vinculada ao hash SHA-256 do conteúdo do plano.</li>
          <li>Chave de idempotência: o mesmo pedido nunca executa duas vezes.</li>
          <li>Orçamento e ativação são sempre propostas separadas.</li>
          <li>Papéis: proprietário, administrador e leitura.</li>
        </ul>
      </div>
    </section>

    <section className="section">
      <div className="container">
        <div className="section-head"><div><Eyebrow num="03">Perguntas frequentes</Eyebrow><h2>Antes de conectar.</h2></div></div>
        <div className="faq">{faq.map(([q, a]) => <details key={q}><summary>{q}</summary><p>{a}</p></details>)}</div>
      </div>
    </section>

    <ClosingCta title={<>Pronto para ver <span>na sua conta?</span></>} text="Fale com a ALN Performance para liberar o seu acesso e acompanhar a primeira auditoria." whatsappHref={whatsapp("Olá, vi como funciona o ALN Hub ia e quero acesso.")}/>
  </>;
}
