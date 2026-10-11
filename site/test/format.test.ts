import { expect, test } from "vitest";
import { delta, pct, shade } from "../src/format.ts";

test("pct edges", () => {
  expect(pct(0)).toBe("0");
  expect(pct(1)).toBe("100");
  expect(pct(0.004)).toBe("<1");
  expect(pct(0.996)).toBe(">99");
  expect(pct(0.414)).toBe("41");
});

test("delta hides Monte Carlo noise below 2 points", () => {
  expect(delta(0.41, 0.4)).toBe("");
  expect(delta(0.42, 0.4)).toBe("+2");
  expect(delta(0.05, 0.14)).toBe("−9");
});

test("shade reaches full black at 25% and is blank below 0.5%", () => {
  expect(shade(0.004)).toBe(0);
  expect(shade(0.25)).toBe(1);
  expect(shade(0.6)).toBe(1);
  expect(shade(0.0625)).toBeCloseTo(0.5, 9);
});

test("phase label handles the end of the league phase", async () => {
  const { phaseLabel } = await import("../src/format.ts");
  expect(phaseLabel(2)).toBe("Before Matchday 2");
  expect(phaseLabel(null)).toBe("After the league phase");
});
