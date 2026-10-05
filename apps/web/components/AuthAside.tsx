import { BrandLink } from "@/components/ui";

export function AuthAside() {
  return <aside className="auth-side">
    <BrandLink/>
    <div>
      <h1>A IA propõe. <span className="grad">Você aprova.</span></h1>
      <p>Google Ads e TikTok Ads com auditoria automática, copiloto e histórico completo de cada decisão.</p>
    </div>
    <p className="auth-foot">Uma solução ALN Performance · Ecossistema ALN Digital</p>
  </aside>;
}
