import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://alnapi-web-production.up.railway.app"),
  title: "ALNAPI | Gestão inteligente de mídia paga",
  description: "Central da ALN Performance para planejar, revisar e gerenciar Google Ads e Meta Ads com IA e aprovação humana.",
  applicationName: "ALNAPI",
  robots: { index: false, follow: false },
  openGraph: { title: "ALNAPI | Gestão inteligente de mídia paga", description: "Performance com contexto, inteligência e controle humano.", type: "website", locale: "pt_BR", siteName: "ALNAPI" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="pt-BR"><body>{children}</body></html>;
}
