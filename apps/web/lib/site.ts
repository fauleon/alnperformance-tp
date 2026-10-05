export const siteUrl = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://app.alnperformance.com.br").replace(/\/$/, "");
export const siteName = "ALN Hub ia";
export const contactEmail = "contato@alndigital.com.br";
export const phoneDisplay = "+55 11 92006-3286";
export const lastUpdated = "2026-10-05";

const whatsappNumber = "5511920063286";
export const whatsapp = (text = "Olá, vim pelo site do ALN Hub ia.") =>
  `https://wa.me/${whatsappNumber}?text=${encodeURIComponent(text)}`;

export const navLinks = [
  { href: "/recursos", label: "Recursos" },
  { href: "/como-funciona", label: "Como funciona" },
  { href: "/seguranca", label: "Segurança" },
  { href: "/contato", label: "Contato" },
] as const;

export const social = [
  { href: "https://www.instagram.com/alndigitalep/", label: "Instagram" },
  { href: "https://www.linkedin.com/company/aln-digital/", label: "LinkedIn" },
] as const;

export type EcosystemUnit = {
  key: "digital" | "performance" | "branding" | "deploy" | "hub" | "hubia";
  name: string;
  short: string;
  role: string;
  text: string;
  url: string | null;
};

export const ecosystem: readonly EcosystemUnit[] = [
  { key: "digital", name: "ALN Digital", short: "Digital", role: "TECNOLOGIA", text: "Sites, sistemas, aplicativos e integrações.", url: "https://alndigital.com.br" },
  { key: "performance", name: "ALN Performance", short: "Performance", role: "AQUISIÇÃO", text: "Tráfego pago, mensuração e crescimento.", url: "https://alnperformance.com.br" },
  { key: "branding", name: "ALN Branding Studio", short: "Branding Studio", role: "IDENTIDADE", text: "O que torna sua marca única.", url: "https://alnbrandingstudio.com.br" },
  { key: "deploy", name: "ALN Deploy", short: "Deploy", role: "INFRAESTRUTURA", text: "Hospedagem gerenciada e continuidade para produtos digitais.", url: "https://alndeploy.com.br" },
  { key: "hub", name: "ALN Hub", short: "Hub", role: "PRESENÇA", text: "Link na bio com a cara da sua marca e métricas reais.", url: "https://hub-alndigital.com.br" },
  { key: "hubia", name: "ALN Hub ia", short: "Hub ia", role: "MÍDIA COM IA", text: "Google Ads e TikTok Ads com inteligência artificial e aprovação humana.", url: null },
];

export const capabilities = [
  { n: "01", title: "Auditoria da conta", type: "Google Ads · TikTok Ads", text: "Regras fixas e explicáveis encontram conversão quebrada, rede errada, termo que gasta sem vender e anúncio fraco — com nota de 0 a 100." },
  { n: "02", title: "Copiloto de IA", type: "Conversa com dados reais", text: "Pergunte em português sobre a sua conta. A IA lê métricas, termos e auditoria, explica e prepara a correção." },
  { n: "03", title: "Criação de campanhas", type: "Pesquisa · TikTok", text: "Do briefing ou da ficha do imóvel até a campanha completa: grupos, palavras, negativas, anúncios e extensões." },
  { n: "04", title: "Edição segura", type: "Proposta → aprovação → execução", text: "Redes, negativas, lances, anúncios, datas e status. Cada mudança mostra o antes e o depois e pode ser revertida." },
  { n: "05", title: "Métricas e relatórios", type: "Diário · por campanha", text: "Investimento, cliques, CTR, CPC, conversões e custo por conversão, com sincronização automática toda madrugada." },
  { n: "06", title: "Conversões", type: "Tag · offline", text: "Cria a ação de conversão, entrega o código da tag e importa lead qualificado pelo GCLID." },
] as const;
