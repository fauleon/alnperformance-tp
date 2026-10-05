import type { Metadata } from "next";
import Link from "next/link";
import { Arrow, ClosingCta, Eyebrow, JsonLd, PageHero } from "@/components/ui";
import { pageGraph, pageMetadata } from "@/lib/seo";
import { capabilities, whatsapp } from "@/lib/site";

const description = "Auditoria automática, copiloto de IA, criação e edição segura de campanhas, relatórios e conversões para Google Ads e TikTok Ads.";
export const metadata: Metadata = pageMetadata({ title: "Recursos", description, path: "/recursos" });

const google = {
  read: ["Contas e hierarquia de MCC", "Campanhas, grupos e anúncios responsivos", "Palavras-chave, Índice de Qualidade e negativas", "Termos de pesquisa reais", "Extensões: sitelinks, frases de destaque e snippets", "Ações de conversão e conversões otimizadas", "Métricas por dia e por campanha", "Ideias de palavras-chave com volume de busca"],
  write: ["Criar campanha de Pesquisa completa, sempre pausada", "Ligar ou desligar Parceiros de Pesquisa e Display", "Adicionar e remover negativas", "Adicionar, pausar e remover palavras-chave", "Reescrever títulos e descrições do anúncio", "Trocar a estratégia de lance", "Mudar data de término e segmentação por presença", "Criar ação de conversão e entregar o código da tag", "Importar conversões offline pelo GCLID"],
};
const tiktok = {
  read: ["Anunciantes autorizados", "Campanhas, grupos de anúncios e anúncios", "Investimento, impressões, cliques e conversões por dia", "Pixel vinculado aos grupos de conversão"],
  write: ["Criar campanha e grupo de anúncios desativados", "Pausar e reativar campanhas e grupos", "Ajustar orçamento diário da campanha"],
};
const rules = [
  ["Crítico", "Lance por conversão sem nenhuma conversão; conversão principal sem registro."],
  ["Alto", "Pesquisa vazando para Display; campanha sem negativas; termos gastando sem converter; conversões otimizadas desligadas."],
  ["Médio", "Parceiros de Pesquisa ligados; Índice de Qualidade baixo com gasto; campanha ativa sem anúncio."],
  ["Baixo", "Correspondência ampla sem Smart Bidding; anúncio com força baixa; extensões repetidas ou contraditórias; localização por interesse; data de término."],
];

export default function ResourcesPage() {
  return <>
    <JsonLd data={pageGraph({ path: "/recursos", name: "Recursos | ALN Hub ia", description, crumbs: [{ name: "Recursos", path: "/recursos" }] })}/>
    <PageHero kicker="Recursos" title={<>Tudo o que a sua conta precisa, <span className="grad">em um só painel.</span></>} lead="Leitura completa das contas, auditoria explicável, copiloto de IA e edição com aprovação — para Google Ads e TikTok Ads." crumbs={[{ name: "Recursos", href: "/recursos" }]}/>

    <section className="section">
      <div className="container">
        <ol className="cap-list">
          {capabilities.map(cap => <li key={cap.n}><div className="row">
            <span className="cap-n">{cap.n}</span><span className="cap-title">{cap.title}</span><span className="cap-type">{cap.type}</span><span/>
            <p className="cap-text">{cap.text}</p>
          </div></li>)}
        </ol>
      </div>
    </section>

    <section className="section section-paper" id="google-ads">
      <div className="container split">
        <div><Eyebrow num="01">Google Ads</Eyebrow><h2>Rede de Pesquisa de ponta a ponta.</h2>
          <p className="page-lead">Via Google Ads API oficial, com login OAuth do Google. Campanhas novas usam só a Pesquisa do Google, segmentação por presença e começam pausadas.</p></div>
        <div className="grid-2">
          <div className="panel-card"><h3>Lê</h3><ul className="check-list">{google.read.map(item => <li key={item}>{item}</li>)}</ul></div>
          <div className="panel-card"><h3>Edita (com aprovação)</h3><ul className="check-list">{google.write.map(item => <li key={item}>{item}</li>)}</ul></div>
        </div>
      </div>
    </section>

    <section className="section" id="tiktok-ads">
      <div className="container split">
        <div><Eyebrow num="02">TikTok Ads</Eyebrow><h2>Desempenho e controle no TikTok.</h2>
          <p className="page-lead">Via TikTok for Business Marketing API, com autorização oficial do anunciante. Campanhas e grupos são criados desativados; criativos continuam no Gerenciador de Anúncios do TikTok.</p></div>
        <div className="grid-2">
          <div className="panel-card"><h3>Lê</h3><ul className="check-list">{tiktok.read.map(item => <li key={item}>{item}</li>)}</ul></div>
          <div className="panel-card"><h3>Edita (com aprovação)</h3><ul className="check-list">{tiktok.write.map(item => <li key={item}>{item}</li>)}</ul></div>
        </div>
      </div>
    </section>

    <section className="section section-paper" id="auditoria">
      <div className="container">
        <div className="section-head"><div><Eyebrow num="03">Auditoria automática</Eyebrow><h2>Regras fixas, explicadas uma a uma.</h2></div>
          <p>Sem caixa-preta: cada achado diz o que está errado, por que importa e como corrigir. Quando dá, já vem com a proposta pronta.</p></div>
        <div className="grid-2">{rules.map(([level, text]) => <div className="panel-card" key={level}><h3>{level}</h3><p className="muted">{text}</p></div>)}</div>
      </div>
    </section>

    <section className="section" id="copiloto">
      <div className="container split">
        <div><Eyebrow num="04">Copiloto de IA</Eyebrow><h2>Pergunte em português. <span className="muted">Receba a correção pronta.</span></h2></div>
        <div className="prose">
          <p>O copiloto conversa com base nos dados reais da conta: métricas, termos de pesquisa, palavras-chave, anúncios e o resultado da auditoria.</p>
          <ul className="check-list">
            <li>Explica por que uma campanha não converte e o que fazer primeiro.</li>
            <li>Sugere negativas, palavras-chave, títulos e descrições dentro dos limites do Google.</li>
            <li>Transforma a sugestão em uma proposta que passa pela política e pela sua aprovação.</li>
            <li>Nunca recebe senhas nem tokens, e não executa nada sozinho.</li>
          </ul>
        </div>
      </div>
    </section>

    <section className="section section-paper" id="imoveis">
      <div className="container split">
        <div><Eyebrow num="05">Modelo para imóveis</Eyebrow><h2>Da ficha do imóvel à campanha, sem contradição.</h2></div>
        <div className="prose">
          <p>Preencha condomínio, bairro, metragem, suítes, vagas e diferenciais. O Hub ia monta palavras de frase e exata, a lista de negativas do setor (aluguel, leilão, na planta…), títulos, descrições e frases de destaque — todos a partir da mesma ficha.</p>
          <p>Uma checagem compara os números em todos os textos: se um título disser 4 vagas e uma descrição disser 5, você é avisado antes de aprovar.</p>
          <Link className="text-link" href="/como-funciona">Ver o fluxo completo <Arrow/></Link>
        </div>
      </div>
    </section>

    <ClosingCta title={<>Veja a sua conta <span>com outros olhos.</span></>} text="Peça seu acesso e conecte o Google Ads ou o TikTok Ads. A primeira auditoria sai assim que a conta é lida." whatsappHref={whatsapp("Olá, quero acesso ao ALN Hub ia.")}/>
  </>;
}
