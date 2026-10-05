import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { ImageResponse } from "next/og";

export const alt = "ALN Hub ia — mídia paga com IA e aprovação humana";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OpengraphImage() {
  const [sora, manrope, mark] = await Promise.all([
    readFile(join(process.cwd(), "assets/Sora-Bold.ttf")),
    readFile(join(process.cwd(), "assets/Manrope-Medium.ttf")),
    readFile(join(process.cwd(), "public/brand/icon-192.png")),
  ]);
  const markSrc = `data:image/png;base64,${mark.toString("base64")}`;
  return new ImageResponse(
    <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between", padding: 72, background: "#07070c", backgroundImage: "radial-gradient(circle at 85% 20%, rgba(118,85,246,.35), transparent 45%), radial-gradient(circle at 15% 90%, rgba(218,250,115,.18), transparent 45%)", color: "#f4f4f8", fontFamily: "Manrope" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
        <img src={markSrc} width={84} height={84} alt="" style={{ borderRadius: 24 }}/>
        <div style={{ display: "flex", alignItems: "flex-start", fontFamily: "Sora", fontSize: 46, letterSpacing: -1.5 }}>
          <span>ALN&nbsp;</span><span style={{ color: "#dafa73" }}>Hub</span><span style={{ fontSize: 26, color: "#a18bff", marginLeft: 6 }}>ia</span>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column" }}>
        <div style={{ fontFamily: "Sora", fontSize: 76, lineHeight: 1.04, letterSpacing: -3, display: "flex", flexDirection: "column" }}>
          <span>Sua mídia paga com IA.</span><span style={{ color: "#dafa73" }}>Você no comando.</span>
        </div>
        <div style={{ marginTop: 28, fontSize: 28, color: "#a9a9bd" }}>Google Ads e TikTok Ads · auditoria, copiloto e aprovação humana</div>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 22, color: "#8b8ba3" }}>
        <span>Uma solução ALN Performance · Ecossistema ALN Digital</span>
      </div>
    </div>,
    { ...size, fonts: [{ name: "Sora", data: sora, weight: 700, style: "normal" }, { name: "Manrope", data: manrope, weight: 500, style: "normal" }] },
  );
}
