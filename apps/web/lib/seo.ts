import type { Metadata } from "next";
import { contactEmail, ecosystem, lastUpdated, phoneDisplay, siteName, siteUrl, social } from "@/lib/site";

const socialImage = { url: `${siteUrl}/opengraph-image`, width: 1200, height: 630, type: "image/png", alt: "ALN Hub ia — mídia paga com IA e aprovação humana" };

type PageMeta = { title: string; description: string; path: string; absoluteTitle?: boolean; index?: boolean };

/** Full per-page head: canonical, robots, Open Graph and Twitter Card. */
export function pageMetadata({ title, description, path, absoluteTitle = false, index = true }: PageMeta): Metadata {
  const fullTitle = absoluteTitle ? title : `${title} | ${siteName}`;
  const url = `${siteUrl}${path}`;
  return {
    title: absoluteTitle ? { absolute: title } : title,
    description,
    alternates: { canonical: url },
    robots: index
      ? { index: true, follow: true, "max-image-preview": "large", "max-snippet": -1, "max-video-preview": -1 }
      : { index: false, follow: false },
    openGraph: { type: "website", locale: "pt_BR", siteName, title: fullTitle, description, url, images: [socialImage] },
    twitter: { card: "summary_large_image", title: fullTitle, description, images: [socialImage.url] },
  };
}

const orgId = `${siteUrl}/#organization`;
const appId = `${siteUrl}/#app`;
const websiteId = `${siteUrl}/#website`;

const organization = {
  "@type": "Organization",
  "@id": orgId,
  name: "ALN Performance",
  url: "https://alnperformance.com.br/",
  logo: { "@type": "ImageObject", url: `${siteUrl}/brand/aln-logo-600.png`, width: 600, height: 600 },
  email: contactEmail,
  telephone: phoneDisplay,
  address: { "@type": "PostalAddress", addressLocality: "São Paulo", addressRegion: "SP", addressCountry: "BR" },
  sameAs: social.map(item => item.href),
  parentOrganization: { "@type": "Organization", name: "ALN Digital", url: "https://alndigital.com.br/" },
  brand: ecosystem.filter(unit => unit.url).map(unit => ({ "@type": "Organization", name: unit.name, url: unit.url })),
};

const application = {
  "@type": "SoftwareApplication",
  "@id": appId,
  name: siteName,
  applicationCategory: "BusinessApplication",
  operatingSystem: "Web",
  url: `${siteUrl}/`,
  inLanguage: "pt-BR",
  description: "Plataforma da ALN Performance para auditar, planejar e operar campanhas de Google Ads e TikTok Ads com inteligência artificial e aprovação humana.",
  provider: { "@id": orgId },
  featureList: ["Auditoria automática de contas", "Copiloto de IA", "Criação de campanhas de Pesquisa", "Edição com aprovação e reversão", "Relatórios de desempenho", "Conversões offline"],
};

const website = { "@type": "WebSite", "@id": websiteId, url: `${siteUrl}/`, name: siteName, inLanguage: "pt-BR", publisher: { "@id": orgId } };

type Crumb = { name: string; path: string };
type PageGraph = { path: string; name: string; description: string; type?: string; crumbs?: Crumb[]; extra?: object[] };

/** JSON-LD @graph for one page: organization, app, website, typed WebPage, breadcrumbs and page-specific nodes. */
export function pageGraph({ path, name, description, type = "WebPage", crumbs, extra = [] }: PageGraph) {
  const url = `${siteUrl}${path}`;
  const graph: object[] = [organization, application, website, {
    "@type": type, "@id": `${url}#webpage`, url, name, description, inLanguage: "pt-BR",
    isPartOf: { "@id": websiteId }, about: { "@id": appId }, publisher: { "@id": orgId }, dateModified: lastUpdated,
    ...(crumbs ? { breadcrumb: { "@id": `${url}#breadcrumb` } } : {}),
  }];
  if (crumbs) graph.push({
    "@type": "BreadcrumbList", "@id": `${url}#breadcrumb`,
    itemListElement: [{ name: "Início", path: "/" }, ...crumbs].map((crumb, index) => ({ "@type": "ListItem", position: index + 1, name: crumb.name, item: `${siteUrl}${crumb.path}` })),
  });
  return { "@context": "https://schema.org", "@graph": [...graph, ...extra] };
}
