/// <reference lib="webworker" />
import { runSeason, type ModelJson, type Result, type SeasonJson } from "@cutline/sim";

let model: ModelJson | null = null;
let season: SeasonJson | null = null;

self.onmessage = (e: MessageEvent) => {
  const msg = e.data;
  if (msg.type === "init") {
    model = msg.model;
    season = msg.season;
    return;
  }
  if (msg.type === "run" && model && season) {
    const t = performance.now();
    const forced = new Map<string, Result>(msg.forced.map(([id, hg, ag]: [string, number, number]) => [id, { id, hg, ag }]));
    const out = runSeason({ model, season, forced, n: msg.n ?? 10_000, seed: msg.seed });
    (self as unknown as Worker).postMessage({ type: "done", out, ms: performance.now() - t, token: msg.token });
  }
};
