import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Tech Pulse · 科技脈搏",
    short_name: "科技脈搏",
    description: "科技、資本與矽：每日編輯精選與投資情報",
    start_url: "/",
    display: "standalone",
    background_color: "#faf7f2",
    theme_color: "#16120e",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      {
        src: "/icon-maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
