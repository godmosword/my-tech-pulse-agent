import type { MetadataRoute } from "next";

import { isPublicReadMode } from "@/lib/env-public-read";
import { siteOrigin } from "@/lib/site-url";

export default function robots(): MetadataRoute.Robots {
  const base = siteOrigin();
  if (!isPublicReadMode()) {
    return {
      rules: { userAgent: "*", disallow: "/" },
    };
  }
  return {
    rules: { userAgent: "*", allow: "/" },
    sitemap: `${base}/sitemap.xml`,
  };
}
