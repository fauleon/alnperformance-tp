import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ALNAPI | AI Ads Manager da ALN Performance",
  description: "Google Ads e Meta Ads operados por IA, com aprovação humana e controle financeiro.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="pt-BR"><body>{children}</body></html>;
}
