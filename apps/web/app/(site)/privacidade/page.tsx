import type { Metadata } from "next";
import Link from "next/link";
import { JsonLd, PageHero } from "@/components/ui";
import { pageGraph, pageMetadata } from "@/lib/seo";
import { contactEmail } from "@/lib/site";

const description = "Como o ALN Hub ia coleta, usa, guarda e protege dados pessoais e dados das contas de anúncio, conforme a LGPD.";
export const metadata: Metadata = pageMetadata({ title: "Política de Privacidade", description, path: "/privacidade" });

export default function PrivacyPage() {
  return <>
    <JsonLd data={pageGraph({ path: "/privacidade", name: "Política de Privacidade | ALN Hub ia", description, crumbs: [{ name: "Privacidade", path: "/privacidade" }] })}/>
    <PageHero kicker="Privacidade · LGPD" title="Política de Privacidade" lead="Transparência sobre o que coletamos, por que e por quanto tempo." crumbs={[{ name: "Privacidade", href: "/privacidade" }]}>
      <p className="legal-meta">Última atualização: 5 de outubro de 2026.</p>
    </PageHero>
    <section className="section">
      <div className="container prose">
        <h2>1. Quem somos</h2>
        <p>O ALN Hub ia é uma plataforma da <strong>ALN Performance</strong>, unidade do ecossistema ALN Digital, com sede em São Paulo, Brasil. Para os dados de cadastro e uso da plataforma, somos a controladora. Para os dados das contas de anúncio dos clientes, atuamos em nome do cliente, que define as finalidades.</p>
        <p>Contato do encarregado (DPO) e canal para titulares: <a href={`mailto:${contactEmail}`}>{contactEmail}</a>.</p>

        <h2>2. Dados que tratamos</h2>
        <ul>
          <li><strong>Cadastro:</strong> nome, e-mail, papel na organização e senha (guardada apenas como hash scrypt, nunca em texto).</li>
          <li><strong>Dados das plataformas de anúncio</strong>, após a sua autorização OAuth: identificadores e nomes de contas, estrutura de campanhas, palavras-chave, anúncios, termos de pesquisa, conversões e métricas.</li>
          <li><strong>Tokens de acesso</strong> do Google e do TikTok, guardados cifrados.</li>
          <li><strong>Registros de segurança e auditoria:</strong> ações realizadas, data, responsável, endereço IP e navegador da sessão.</li>
          <li><strong>Conversões offline</strong> enviadas por você (GCLID, data e valor), repassadas ao Google Ads para medir resultados.</li>
        </ul>
        <p>Não coletamos senhas das plataformas, códigos de verificação, dados de cartão ou informações de cobrança.</p>

        <h2>3. Para que usamos</h2>
        <ul>
          <li>Prestar o serviço: ler as contas, auditar, gerar propostas, validar, executar e reportar as operações que você aprovar.</li>
          <li>Segurança: autenticação, prevenção de abuso, trilha de auditoria e investigação de incidentes.</li>
          <li>Suporte e comunicação sobre o serviço.</li>
          <li>Cumprimento de obrigações legais e regulatórias.</li>
        </ul>
        <p>Bases legais (LGPD, art. 7º): execução de contrato, legítimo interesse (segurança e melhoria do serviço) e cumprimento de obrigação legal.</p>

        <h2>4. Dados do Google (Uso Limitado)</h2>
        <p>O uso e a transferência, para qualquer outro aplicativo, de informações recebidas das APIs do Google seguem a <a href="https://developers.google.com/terms/api-services-user-data-policy" target="_blank" rel="noopener noreferrer">Política de Dados do Usuário dos Serviços de API do Google</a>, incluindo os requisitos de Uso Limitado. Não usamos dados do Google para publicidade, não os vendemos e não os usamos para treinar modelos de IA.</p>

        <h2>5. Com quem compartilhamos</h2>
        <ul>
          <li><strong>Google e TikTok:</strong> para executar as operações que você aprovou nas suas próprias contas.</li>
          <li><strong>Provedor de IA</strong> (quando o copiloto está ativo): métricas agregadas e estrutura das campanhas, sem tokens, senhas, e-mails ou dados de pagamento, sem armazenamento para treino.</li>
          <li><strong>Infraestrutura:</strong> provedores de hospedagem e banco de dados que operam sob contrato e confidencialidade.</li>
          <li><strong>Autoridades:</strong> quando houver obrigação legal ou ordem judicial.</li>
        </ul>
        <p>Alguns provedores ficam fora do Brasil; nesses casos a transferência internacional segue as salvaguardas da LGPD (art. 33).</p>

        <h2>6. Cookies</h2>
        <p>Usamos apenas um cookie essencial de sessão (HttpOnly) para manter você conectado ao painel. Não usamos cookies de publicidade nem de analytics de terceiros, por isso não há banner de consentimento.</p>

        <h2>7. Por quanto tempo guardamos</h2>
        <ul>
          <li>Tokens das plataformas: até você desconectar a conta — nesse momento são revogados e apagados.</li>
          <li>Cache de métricas: até 24 horas, renovado automaticamente.</li>
          <li>Propostas, aprovações e trilha de auditoria: enquanto a organização estiver ativa e por até 5 anos depois, para defesa em processos e prestação de contas.</li>
          <li>Sessões: até 7 dias ou até você sair.</li>
        </ul>

        <h2>8. Seus direitos</h2>
        <p>Você pode pedir confirmação, acesso, correção, anonimização, portabilidade, eliminação, informação sobre compartilhamento e revogação do consentimento, além de se opor a tratamentos. Escreva para <a href={`mailto:${contactEmail}`}>{contactEmail}</a>; respondemos em até 15 dias. Você também pode reclamar à ANPD.</p>

        <h2>9. Segurança</h2>
        <p>Criptografia em trânsito (HTTPS/HSTS) e dos tokens em repouso, isolamento por organização, controle de acesso por papel, limite de tentativas, logs sem dados sensíveis e revisão de cada alteração por uma pessoa. Detalhes em <Link href="/seguranca">Segurança e uso de dados</Link>.</p>

        <h2>10. Mudanças</h2>
        <p>Podemos atualizar esta política. A data no topo mostra a versão em vigor; mudanças relevantes são avisadas no painel.</p>
      </div>
    </section>
  </>;
}
