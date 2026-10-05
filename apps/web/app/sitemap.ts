import type { MetadataRoute } from "next";
import { lastUpdated, siteUrl } from "@/lib/site";

const pages = ["", "/recursos", "/como-funciona", "/seguranca", "/contato", "/privacidade", "/termos"];

export default function sitemap(): MetadataRoute.Sitemap {
  return pages.map(path => ({
    url: `${siteUrl}${path || "/"}`,
    lastModified: lastUpdated,
    changeFrequency: "monthly",
    priority: path === "" ? 1 : path === "/privacidade" || path === "/termos" ? 0.3 : 0.7,
  }));
}
