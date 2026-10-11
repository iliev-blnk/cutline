import { describe, expect, test } from "vitest";
import { Rng } from "../src/rng.ts";
import { buildCdf, matchProbs, sampleScore, scoreMatrix } from "../src/score.ts";

const pois = (k: number, l: number) => {
  let p = Math.exp(-l);
  for (let i = 1; i <= k; i++) p *= l / i;
  return p;
};

describe("score", () => {
  test("matrix sums to 1", () => {
    const m = scoreMatrix(1.7, 0.9, -0.05);
    expect(Math.abs(m.reduce((a, b) => a + b, 0) - 1)).toBeLessThan(1e-9);
  });

  test("rho 0 is the product of two Poissons (renormalised)", () => {
    const m = scoreMatrix(1.4, 1.1, 0);
    let z = 0;
    for (let x = 0; x <= 10; x++) for (let y = 0; y <= 10; y++) z += pois(x, 1.4) * pois(y, 1.1);
    expect(m[2 * 11 + 1]).toBeCloseTo((pois(2, 1.4) * pois(1, 1.1)) / z, 12);
  });

  test("sampling matches matchProbs within 3 standard errors", () => {
    const lh = 1.6, la = 1.0, rho = -0.08;
    const p = matchProbs(lh, la, rho);
    const cdf = buildCdf(scoreMatrix(lh, la, rho));
    const rng = new Rng(7);
    const n = 1_000_000;
    let h = 0, d = 0;
    for (let i = 0; i < n; i++) {
      const [x, y] = sampleScore(cdf, rng);
      if (x > y) h++;
      else if (x === y) d++;
    }
    for (const [obs, q] of [[h / n, p.h], [d / n, p.d]] as const) {
      expect(Math.abs(obs - q)).toBeLessThan(3 * Math.sqrt((q * (1 - q)) / n));
    }
    expect(p.h + p.d + p.a).toBeCloseTo(1, 12);
  });

  test("same seed gives the same sequence", () => {
    const a = new Rng(42), b = new Rng(42), c = new Rng(43);
    const sa = Array.from({ length: 5 }, () => a.next());
    const sb = Array.from({ length: 5 }, () => b.next());
    expect(sa).toEqual(sb);
    expect(sa).not.toEqual(Array.from({ length: 5 }, () => c.next()));
    expect(sa.every((v) => v >= 0 && v < 1)).toBe(true);
  });
});
