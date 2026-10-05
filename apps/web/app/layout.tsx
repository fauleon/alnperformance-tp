import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import "./globals.css";
import { siteName, siteUrl } from "@/lib/site";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: { default: "ALN Hub ia | Google Ads e TikTok Ads com IA", template: `%s | ${siteName}` },
  description: "Audite, planeje e opere Google Ads e TikTok Ads com inteligência artificial. Nada vai ao ar sem a sua aprovação.",
  applicationName: siteName,
  referrer: "strict-origin-when-cross-origin",
  formatDetection: { telephone: false },
  icons: {
    icon: [{ url: "/brand/favicon-32.png", sizes: "32x32", type: "image/png" }, { url: "/brand/favicon-64.png", sizes: "64x64", type: "image/png" }],
    apple: [{ url: "/brand/apple-touch-icon.png", sizes: "180x180" }],
  },
};

export const viewport: Viewport = { themeColor: "#07070c", colorScheme: "dark", width: "device-width", initialScale: 1 };

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  // Reading the request makes every page render per request, so proxy.ts can apply a fresh CSP nonce.
  await headers();
  return <html lang="pt-BR">
    <head>
      <link rel="preload" href="/fonts/sora.woff2" as="font" type="font/woff2" crossOrigin="anonymous"/>
      <link rel="preload" href="/fonts/manrope.woff2" as="font" type="font/woff2" crossOrigin="anonymous"/>
    </head>
    <body>{children}</body>
  </html>;
}
