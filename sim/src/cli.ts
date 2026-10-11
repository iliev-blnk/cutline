import { readFileSync, writeFileSync } from "node:fs";
import { parseArgs } from "node:util";
import { runSeason } from "./season.ts";
import type { ModelJson, SeasonJson } from "./types.ts";

function snapshot(argv: string[]): void {
  const { values } = parseArgs({
    args: argv,
    options: {
      model: { type: "string" },
      season: { type: "string" },
      n: { type: "string", default: "10000" },
      seed: { type: "string" },
      out: { type: "string" },
      untuned: { type: "boolean", default: false },
      note: { type: "string", multiple: true, default: [] },
    },
  });
  if (!values.model || !values.season || !values.seed || !values.out) {
    throw new Error("usage: snapshot --model m.json --season s.json --seed N --out o.json [--n 10000] [--untuned] [--note ...]");
  }
  const model: ModelJson = JSON.parse(readFileSync(values.model, "utf8"));
  const season: SeasonJson = JSON.parse(readFileSync(values.season, "utf8"));
  const n = Number(values.n), seed = Number(values.seed);
  const finished = season.fixtures.filter((f) => f.status === "FINISHED").map((f) => f.id);
  const open = season.fixtures.filter((f) => f.status !== "FINISHED");
  const beforeMd = open.length ? Math.min(...open.map((f) => f.md)) : null;
  const t = performance.now();
  const out = runSeason({ model, season, forced: new Map(), n, seed });
  const snap = {
    generatedAt: new Date().toISOString(),
    seasonYear: season.seasonYear,
    beforeMd,
    modelCutoff: model.cutoff,
    inputHash: model.input_hash,
    hyper: model.hyper,
    untuned: values.untuned,
    notes: values.note,
    finished,
    ...out,
  };
  writeFileSync(values.out, JSON.stringify(snap));
  console.log(`snapshot before MD${beforeMd}: ${n} seasons in ${((performance.now() - t) / 1000).toFixed(1)} s -> ${values.out}`);
}

const [cmd, ...rest] = process.argv.slice(2);
if (cmd === "snapshot") snapshot(rest);
else {
  console.error("commands: snapshot");
  process.exit(2);
}
