import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ALN Hub ia",
    short_name: "Hub ia",
    description: "Google Ads e TikTok Ads com IA e aprovação humana.",
    start_url: "/app",
    display: "standalone",
    background_color: "#07070c",
    theme_color: "#07070c",
    lang: "pt-BR",
    icons: [
      { src: "/brand/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/brand/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/brand/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
