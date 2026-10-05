import type { Metadata } from "next";
import Link from "next/link";
import { JsonLd, PageHero } from "@/components/ui";
import { pageGraph, pageMetadata } from "@/lib/seo";
import { contactEmail } from "@/lib/site";

const description = "Condições de uso do ALN Hub ia: acesso por convite, responsabilidades, aprovação humana, limites do serviço e foro.";
export const metadata: Metadata = pageMetadata({ title: "Termos de uso", description, path: "/termos" });

export default function TermsPage() {
  return <>
    <JsonLd data={pageGraph({ path: "/termos", name: "Termos de uso | ALN Hub ia", description, crumbs: [{ name: "Termos de uso", path: "/termos" }] })}/>
    <PageHero kicker="Termos de uso" title="Termos de uso" lead="As regras do uso do ALN Hub ia, em linguagem direta." crumbs={[{ name: "Termos de uso", href: "/termos" }]}>
      <p className="legal-meta">Última atualização: 5 de outubro de 2026.</p>
    </PageHero>
    <section className="section">
      <div className="container prose">
        <h2>1. O serviço</h2>
        <p>O ALN Hub ia, operado pela ALN Performance, ajuda a ler, auditar, planejar e gerenciar campanhas de Google Ads e TikTok Ads por meio das APIs oficiais dessas plataformas, com apoio de inteligência artificial e aprovação humana obrigatória para qualquer alteração.</p>

        <h2>2. Acesso</h2>
        <ul>
          <li>O acesso é concedido por convite da ALN Performance ou do proprietário de uma organização já cadastrada.</li>
          <li>Você é responsável por manter sua senha em sigilo e pelas ações feitas com o seu login.</li>
          <li>Só conecte contas de anúncio que você tem autorização para gerenciar.</li>
        </ul>

        <h2>3. Aprovação e responsabilidade pelas campanhas</h2>
        <ul>
          <li>Nenhuma alteração é aplicada sem aprovação de uma pessoa com papel de proprietário ou administrador.</li>
          <li>Sugestões da IA e da auditoria são recomendações. A decisão de aprovar, e seus efeitos, são do usuário que aprova.</li>
          <li>O investimento em mídia é cobrado diretamente pelas plataformas, conforme os contratos que você mantém com elas. O ALN Hub ia não processa pagamentos nem adiciona saldo.</li>
          <li>Você continua obrigado a seguir as políticas de publicidade do Google e do TikTok.</li>
        </ul>

        <h2>4. Uso proibido</h2>
        <p>É proibido usar o serviço para anúncios ilegais ou enganosos, para contornar políticas das plataformas, para acessar contas sem autorização, para tentar burlar as proteções do sistema ou para sobrecarregar a infraestrutura.</p>

        <h2>5. Disponibilidade</h2>
        <p>Trabalhamos para manter o serviço disponível, mas ele depende das APIs do Google e do TikTok, que podem mudar, limitar cotas ou ficar indisponíveis. Podemos pausar mutações (kill switch) a qualquer momento para proteger as contas.</p>

        <h2>6. Limitação de responsabilidade</h2>
        <p>Na máxima extensão permitida em lei, a ALN Performance não responde por resultados de campanhas, lucros cessantes ou danos indiretos decorrentes de decisões aprovadas pelo usuário ou de falhas das plataformas de anúncio.</p>

        <h2>7. Dados e privacidade</h2>
        <p>O tratamento de dados segue a <Link href="/privacidade">Política de Privacidade</Link> e a página <Link href="/seguranca">Segurança e uso de dados</Link>. Você pode desconectar suas contas e pedir a exclusão dos dados a qualquer momento.</p>

        <h2>8. Encerramento</h2>
        <p>Você pode encerrar o uso quando quiser. Podemos suspender acessos em caso de violação destes termos, risco de segurança ou pedido da plataforma de anúncios.</p>

        <h2>9. Lei e foro</h2>
        <p>Estes termos seguem a lei brasileira. Fica eleito o foro da Comarca de São Paulo/SP. Dúvidas: <a href={`mailto:${contactEmail}`}>{contactEmail}</a>.</p>
      </div>
    </section>
  </>;
}
