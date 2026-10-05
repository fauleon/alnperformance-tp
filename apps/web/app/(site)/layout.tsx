import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";

export default function SiteLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <>
    <a className="skip-link" href="#conteudo">Pular para o conteúdo</a>
    <SiteHeader/>
    <main id="conteudo">{children}</main>
    <SiteFooter/>
  </>;
}
