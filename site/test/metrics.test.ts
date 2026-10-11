import { expect, test } from "vitest";
import { outcome, rps } from "../src/metrics.ts";

test("ranked probability score", () => {
  expect(rps([1, 0, 0], 0)).toBe(0);
  expect(rps([0, 0, 1], 0)).toBe(1);
  expect(rps([1 / 3, 1 / 3, 1 / 3], 1)).toBeCloseTo(1 / 9, 9);
});

test("outcome index", () => {
  expect(outcome(2, 1)).toBe(0);
  expect(outcome(1, 1)).toBe(1);
  expect(outcome(0, 3)).toBe(2);
});
