import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ALN Performance | AI Ads Manager",
  description: "Planejamento e governança de mídia paga com IA e aprovação humana.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="pt-BR"><body>{children}</body></html>;
}

