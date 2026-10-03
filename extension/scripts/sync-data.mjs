import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, "..", "..", "data", "sponsors_latest.json");
const dest = resolve(here, "..", "src", "data", "sponsors.json");

if (!existsSync(src)) {
  console.error(`Missing ${src} - run \`uv run jf sync-sponsors\` in the repo root first.`);
  process.exit(1);
}

mkdirSync(dirname(dest), { recursive: true });
copyFileSync(src, dest);
console.log(`Copied sponsor snapshot: ${src} -> ${dest}`);
