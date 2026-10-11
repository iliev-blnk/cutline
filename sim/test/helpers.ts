import { readFileSync } from "node:fs";
import type { ModelJson, SeasonJson } from "../src/types.ts";

export function loadSeason(year: number): SeasonJson {
  return JSON.parse(readFileSync(new URL(`./fixtures/ucl-${year}.json`, import.meta.url), "utf8"));
}

/** Strength strictly decreasing with the given order; sd 0. */
export function rankedModel(order: string[], sd = 0, spread = 0.03): ModelJson {
  const clubs: ModelJson["clubs"] = {};
  order.forEach((c, i) => {
    const s = 0.6 - spread * i;
    clubs[c] = { name: c, country: "X", att: s, def: s, sd_att: sd, sd_def: sd };
  });
  return { version: 1, cutoff: "", input_hash: "", hyper: {}, rho: -0.05, mu_eur: 0.1, h_eur: 0.3, clubs };
}
