import { describe, expect, test } from "vitest";
import { runSeason } from "../src/season.ts";
import type { Result, SeasonJson } from "../src/types.ts";
import { loadSeason, rankedModel } from "./helpers.ts";

/** 2025-26 schedule with every match after MD1 un-played. */
function openSeason(): SeasonJson {
  const s = loadSeason(2026);
  return {
    ...s,
    fixtures: s.fixtures.map((f) => (f.md === 1 ? f : { ...f, status: "UPCOMING", hg: null, ag: null })),
  };
}
const season = openSeason();
const clubs = Object.keys(season.clubs);
const model = rankedModel(clubs, 0.1, 0.02);

describe("runSeason", () => {
  test("distributions are proper", () => {
    const out = runSeason({ model, season, forced: new Map(), n: 2000, seed: 11 });
    let win = 0;
    for (const c of clubs) {
      const o = out.clubs[c];
      expect(Math.abs(o.posDist.reduce((a, b) => a + b, 0) - 1)).toBeLessThan(1e-9);
      expect(o.posDist).toHaveLength(36);
      expect(o.top8 + o.mid + o.out).toBeCloseTo(1, 9);
      win += o.win;
    }
    expect(win).toBeCloseTo(1, 9);
    const sum = (k: "top8" | "mid" | "out") => clubs.reduce((a, c) => a + out.clubs[c][k], 0);
    expect(sum("top8")).toBeCloseTo(8, 6);
    expect(sum("mid")).toBeCloseTo(16, 6);
    expect(sum("out")).toBeCloseTo(12, 6);
    const fx = Object.values(out.fixtures);
    expect(fx).toHaveLength(126);
    for (const f of fx) expect(f.h + f.d + f.a).toBeCloseTo(1, 9);
  });

  test("forcing every remaining match of a club to 10-0 makes it certain top 8 with no NaN", () => {
    const club = clubs[35]; // weakest
    const forced = new Map<string, Result>();
    for (const f of season.fixtures) {
      if (f.status === "FINISHED") continue;
      if (f.home === club) forced.set(f.id, { id: f.id, hg: 10, ag: 0 });
      if (f.away === club) forced.set(f.id, { id: f.id, hg: 0, ag: 10 });
    }
    const out = runSeason({ model, season, forced, n: 2000, seed: 5 });
    expect(out.clubs[club].top8).toBe(1);
    expect(JSON.stringify(out)).not.toContain("null");
    for (const c of clubs) for (const v of Object.values(out.clubs[c]).flat()) expect(Number.isFinite(v)).toBe(true);
  });

  test("same seed gives identical output", () => {
    const a = runSeason({ model, season, forced: new Map(), n: 500, seed: 9 });
    const b = runSeason({ model, season, forced: new Map(), n: 500, seed: 9 });
    expect(a).toEqual(b);
  });

  test("10,000 seasons in under 1.5 s", () => {
    const t = performance.now();
    runSeason({ model, season, forced: new Map(), n: 10_000, seed: 1 });
    expect(performance.now() - t).toBeLessThan(1500);
  });
});
