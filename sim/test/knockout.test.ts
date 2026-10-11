import { describe, expect, test } from "vitest";
import { knockout } from "../src/knockout.ts";
import { Rng } from "../src/rng.ts";
import { drawStrengths } from "../src/season.ts";
import { rankedModel } from "./helpers.ts";

const order = Array.from({ length: 36 }, (_, i) => `c${i + 1}`); // c1 = rank 1
const rank = (c: string) => Number(c.slice(1));

describe("knockout structure (10,000 brackets)", () => {
  const model = rankedModel(order);
  const rng = new Rng(3);
  const runs = Array.from({ length: 10_000 }, () => knockout(order, model, drawStrengths(model, order, rng), rng));

  test("ranks 25-36 never reach the round of 16; 1-8 always do", () => {
    for (const r of runs) {
      expect(r.r16.some((c) => rank(c) >= 25)).toBe(false);
      for (let k = 1; k <= 8; k++) expect(r.r16).toContain(`c${k}`);
      expect(r.r16).toHaveLength(16);
    }
  });

  test("ranks 1-8 never appear in a play-off tie", () => {
    for (const r of runs) for (const [a, b] of r.playoffs) expect(rank(a) > 8 && rank(b) > 8).toBe(true);
  });

  test("seeds 1 and 2 never meet before the final", () => {
    for (const r of runs) {
      const early = [...r.ties.r16, ...r.ties.qf, ...r.ties.sf];
      expect(early.some(([a, b]) => new Set([a, b]).has("c1") && new Set([a, b]).has("c2"))).toBe(false);
    }
  });

  test("seeds 1 and 3 meet only in the semi-final or final", () => {
    for (const r of runs) {
      const early = [...r.ties.r16, ...r.ties.qf];
      expect(early.some(([a, b]) => new Set([a, b]).has("c1") && new Set([a, b]).has("c3"))).toBe(false);
    }
  });

  test("the R16 opponent of seed 1 comes from ranks 15-18", () => {
    for (const r of runs) {
      const [a, b] = r.ties.r16.find(([x, y]) => x === "c1" || y === "c1")!;
      const opp = a === "c1" ? b : a;
      expect([15, 16, 17, 18]).toContain(rank(opp));
    }
  });

  test("progression sizes", () => {
    for (const r of runs) {
      expect(r.qf).toHaveLength(8);
      expect(r.sf).toHaveLength(4);
      expect(r.final).toHaveLength(2);
      expect(r.final).toContain(r.winner);
    }
  });
});
