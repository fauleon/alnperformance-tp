import type { Metadata } from "next";
import Link from "next/link";
import { Arrow, Eyebrow, JsonLd, PageHero } from "@/components/ui";
import { pageGraph, pageMetadata } from "@/lib/seo";
import { contactEmail } from "@/lib/site";

const description = "Como o ALN Hub ia acessa, usa e protege dados do Google Ads e do TikTok Ads: OAuth oficial, tokens cifrados, aprovação humana e revogação.";
export const metadata: Metadata = pageMetadata({ title: "Segurança e uso de dados", description, path: "/seguranca" });

export default function SecurityPage() {
  return <>
    <JsonLd data={pageGraph({ path: "/seguranca", name: "Segurança e uso de dados | ALN Hub ia", description, crumbs: [{ name: "Segurança", path: "/seguranca" }] })}/>
    <PageHero kicker="Segurança e uso de dados" title={<>Credenciais protegidas. <span className="grad">Operações rastreáveis.</span></>} lead="O ALN Hub ia é uma plataforma de gestão de campanhas desenvolvida e operada pela ALN Performance. Esta página explica o que acessamos, para quê e como protegemos." crumbs={[{ name: "Segurança", href: "/seguranca" }]}/>

    <section className="section">
      <div className="container split">
        <div>
          <Eyebrow num="01">Dados da conta Google Ads</Eyebrow>
          <h2>O acesso é limitado ao fluxo autorizado.</h2>
          <p className="page-lead">Usamos a Google Ads API com o escopo <code className="code-inline">https://www.googleapis.com/auth/adwords</code>, somente depois que uma pessoa autorizada conclui o login OAuth 2.0 do Google.</p>
          <ul className="check-list">
            <li>Identificadores e nomes das contas acessíveis e da hierarquia de MCC</li>
            <li>Estrutura, status, orçamento, redes e lances das campanhas</li>
            <li>Grupos, palavras-chave, negativas, anúncios e extensões</li>
            <li>Termos de pesquisa, ações de conversão e métricas de desempenho</li>
          </ul>
        </div>
        <div className="panel-card">
          <Eyebrow>Fluxo de dados</Eyebrow>
          <ol className="flow"><li>Pessoa autorizada</li><li>Login OAuth do Google ou TikTok</li><li>API oficial da plataforma</li><li>Proposta, validação e aprovação</li></ol>
          <p className="muted">Nunca pedimos nem armazenamos a senha da sua conta Google ou TikTok, nem códigos de verificação em duas etapas.</p>
        </div>
      </div>
    </section>

    <section className="section section-paper">
      <div className="container">
        <div className="section-head"><div><Eyebrow num="02">Uso limitado</Eyebrow><h2>Os dados servem só para operar as suas campanhas.</h2></div></div>
        <div className="prose">
          <p>O uso e a transferência, para qualquer outro aplicativo, de informações recebidas das APIs do Google seguem a <a href="https://developers.google.com/terms/api-services-user-data-policy" target="_blank" rel="noopener noreferrer">Política de Dados do Usuário dos Serviços de API do Google</a>, incluindo os requisitos de Uso Limitado.</p>
          <ul>
            <li>Os dados das plataformas são usados apenas para planejar, validar, executar e reportar as operações de campanha que você pediu.</li>
            <li>Não vendemos dados, não usamos para publicidade própria e não os transferimos a terceiros, exceto quando necessário para prestar o serviço, cumprir a lei ou com o seu consentimento.</li>
            <li>Quando o copiloto de IA está ativo, enviamos ao provedor de IA apenas métricas agregadas e a estrutura das campanhas — nunca tokens, senhas, e-mails ou dados de cartão. Esses dados não são usados para treinar modelos.</li>
            <li>Pessoas da ALN só acessam os dados de uma conta para dar suporte a pedido do cliente, por segurança ou por obrigação legal.</li>
          </ul>
        </div>
      </div>
    </section>

    <section className="section">
      <div className="container">
        <div className="section-head"><div><Eyebrow num="03">Como protegemos</Eyebrow><h2>Camadas, não promessas.</h2></div></div>
        <div className="grid-3">
          <div className="panel-card"><h3>Tokens cifrados</h3><p className="muted">Tokens OAuth são guardados cifrados (Fernet, com rotação de chave) e nunca aparecem na interface, nos logs ou na auditoria.</p></div>
          <div className="panel-card"><h3>Isolamento por cliente</h3><p className="muted">Cada organização e cliente só enxerga os próprios dados. O acesso vem do login, nunca de um parâmetro enviado pelo navegador.</p></div>
          <div className="panel-card"><h3>Aprovação humana</h3><p className="muted">Nenhuma alteração é aplicada sem aprovação de uma pessoa com permissão. Ativação e orçamento têm aprovação própria.</p></div>
          <div className="panel-card"><h3>Kill switch</h3><p className="muted">Um interruptor global bloqueia toda mutação externa — validação, aprovação e execução — sem desligar a leitura.</p></div>
          <div className="panel-card"><h3>Trilha de auditoria</h3><p className="muted">Conexões, propostas, validações, aprovações e execuções ficam registradas com data, responsável e resultado.</p></div>
          <div className="panel-card"><h3>Sessões e transporte</h3><p className="muted">HTTPS com HSTS, cookie de sessão HttpOnly, proteção contra CSRF, limite de tentativas e política de conteúdo restrita (CSP).</p></div>
        </div>
      </div>
    </section>

    <section className="section section-paper">
      <div className="container split">
        <div><Eyebrow num="04">Fora do escopo</Eyebrow><h2>Limites claros por escolha.</h2><p className="page-lead">Cobrança e saldo continuam nas interfaces oficiais de faturamento das plataformas.</p></div>
        <div className="panel-card"><h3>O ALN Hub ia não:</h3><ul className="check-list x-list">
          <li>Automatiza cartões ou meios de pagamento</li><li>Altera configurações de faturamento</li><li>Processa cobranças ou adiciona saldo</li>
          <li>Coleta senhas ou códigos de verificação</li><li>Ativa campanhas sem revisão humana</li></ul></div>
      </div>
    </section>

    <section className="section">
      <div className="container split">
        <div><Eyebrow num="05">Revogar acesso e excluir dados</Eyebrow><h2>Você sai quando quiser.</h2></div>
        <div className="prose">
          <p>Em <strong>Integrações → Desconectar</strong>, revogamos o token na plataforma e apagamos as credenciais do nosso banco na hora. Você também pode remover o acesso em <a href="https://myaccount.google.com/permissions" target="_blank" rel="noopener noreferrer">myaccount.google.com/permissions</a> ou nas configurações do TikTok for Business.</p>
          <p>Para excluir todos os dados da sua organização, escreva para <a href={`mailto:${contactEmail}`}>{contactEmail}</a>. Detalhes de retenção na <Link href="/privacidade">Política de Privacidade</Link>.</p>
          <p>Encontrou uma vulnerabilidade? Veja <a href="/.well-known/security.txt">security.txt</a>.</p>
          <Link className="text-link" href="/termos">Termos de uso <Arrow/></Link>
        </div>
      </div>
    </section>
  </>;
}
