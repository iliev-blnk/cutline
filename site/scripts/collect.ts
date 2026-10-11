/** Copy the snapshots, their models and the season into public/data for the static build. */
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const root = new URL("../..", import.meta.url).pathname;
const year = 2027;
const pred = join(root, "predictions", String(year));
const out = join(root, "site", "public", "data");
mkdirSync(join(out, "snapshots"), { recursive: true });

const snaps = readdirSync(pred).filter((f) => /-before-MD\d+\.json$/.test(f) && !f.endsWith(".model.json")).sort();
if (!snaps.length) throw new Error(`no snapshots in ${pred}`);
const index = snaps.map((f) => {
  const s = JSON.parse(readFileSync(join(pred, f), "utf8"));
  copyFileSync(join(pred, f), join(out, "snapshots", f));
  copyFileSync(join(pred, f.replace(/\.json$/, ".model.json")), join(out, "snapshots", f.replace(/\.json$/, ".model.json")));
  const odds = join(pred, "odds", f);
  if (existsSync(odds)) copyFileSync(odds, join(out, "snapshots", f.replace(/\.json$/, ".odds.json")));
  return { file: f, generatedAt: s.generatedAt, beforeMd: s.beforeMd, untuned: s.untuned, odds: existsSync(odds) };
});
writeFileSync(join(out, "index.json"), JSON.stringify(index));
copyFileSync(join(root, "data", `season-${year}.json`), join(out, "season.json"));
console.log(`collect: ${snaps.length} snapshot(s), latest ${snaps.at(-1)}`);
