#!/usr/bin/env node
/**
 * Render dashboard PWA icons from scripts/icon.svg.
 * Requires: npm install --save-dev sharp (in dashboard/)
 *
 * Usage (from dashboard/):
 *   node scripts/gen-icons.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const svgPath = path.join(__dirname, "icon.svg");
const maskableSvgPath = path.join(__dirname, "icon-maskable.svg");
const publicDir = path.join(root, "public");

const PAPER = "#faf7f2";

const maskableSvg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <rect width="512" height="512" fill="${PAPER}"/>
  <text
    x="256"
    y="300"
    text-anchor="middle"
    font-family="Georgia, 'Source Serif 4', serif"
    font-size="160"
    font-weight="600"
    fill="#16120e"
  >TP</text>
</svg>
`;

async function main() {
  let sharp;
  try {
    sharp = (await import("sharp")).default;
  } catch {
    console.error("Missing sharp. Run: npm install --save-dev sharp");
    process.exit(1);
  }

  if (!fs.existsSync(svgPath)) {
    console.error(`Missing ${svgPath}`);
    process.exit(1);
  }

  fs.mkdirSync(publicDir, { recursive: true });
  fs.writeFileSync(maskableSvgPath, maskableSvg, "utf-8");

  const svg = fs.readFileSync(svgPath);
  const maskable = fs.readFileSync(maskableSvgPath);

  const outputs = [
    { file: "icon-192.png", input: svg, size: 192 },
    { file: "icon-512.png", input: svg, size: 512 },
    { file: "icon-maskable-512.png", input: maskable, size: 512 },
    { file: "apple-touch-icon.png", input: svg, size: 180 },
  ];

  for (const { file, input, size } of outputs) {
    const out = path.join(publicDir, file);
    await sharp(input)
      .resize(size, size)
      .flatten({ background: PAPER })
      .png()
      .toFile(out);
    console.log(`Wrote ${out}`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
