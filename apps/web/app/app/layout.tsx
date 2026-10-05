import type { Metadata } from "next";
import { AppProvider } from "@/components/app/AppContext";
import { Shell } from "@/components/app/Shell";

export const metadata: Metadata = { title: { default: "Painel", template: "%s · Painel ALN Hub ia" }, robots: { index: false, follow: false } };

export default function PanelLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <AppProvider><Shell>{children}</Shell></AppProvider>;
}
