import type { MetadataRoute } from "next";

import { isPublicReadMode } from "@/lib/env-public-read";
import { listLatestItems } from "@/lib/firestore";
import { siteOrigin } from "@/lib/site-url";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = siteOrigin();
  const fallback: MetadataRoute.Sitemap = [
    { url: `${base}/`, lastModified: new Date(), changeFrequency: "daily" },
  ];

  if (!isPublicReadMode()) {
    return fallback;
  }

  try {
    const items = await listLatestItems({ limit: 200 });
    const entries: MetadataRoute.Sitemap = [
      {
        url: `${base}/`,
        lastModified: new Date(),
        changeFrequency: "hourly",
        priority: 1,
      },
      {
        url: `${base}/archive`,
        lastModified: new Date(),
        changeFrequency: "daily",
        priority: 0.8,
      },
      {
        url: `${base}/login`,
        lastModified: new Date(),
        changeFrequency: "monthly",
        priority: 0.2,
      },
    ];
    for (const item of items) {
      const iso = item.delivered_at_iso || item.published_at_iso;
      entries.push({
        url: `${base}/item/${encodeURIComponent(item.id)}`,
        lastModified: iso ? new Date(iso) : new Date(),
        changeFrequency: "weekly",
        priority: 0.6,
      });
    }
    return entries;
  } catch {
    return fallback;
  }
}
