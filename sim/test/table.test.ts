import { readFileSync } from "node:fs";
import { describe, expect, test } from "vitest";
import { Rng } from "../src/rng.ts";
import { compareRows, leagueTable } from "../src/table.ts";
import type { Fixture, Result, TableRow } from "../src/types.ts";

const row = (club: string, o: Partial<TableRow> = {}): TableRow => ({
  club, played: 8, w: 4, d: 2, l: 2, gf: 12, ga: 8, gd: 4, pts: 14,
  awayGf: 5, awayW: 2, oppPts: 80, oppGd: 0, oppGf: 90, ...o,
});

describe("compareRows: each criterion decides when all above it are equal", () => {
  const cases: [string, Partial<TableRow>][] = [
    ["pts", { pts: 15 }],
    ["gd", { gd: 5 }],
    ["gf", { gf: 13 }],
    ["awayGf", { awayGf: 6 }],
    ["w", { w: 5 }],
    ["awayW", { awayW: 3 }],
    ["oppPts", { oppPts: 81 }],
    ["oppGd", { oppGd: 1 }],
    ["oppGf", { oppGf: 91 }],
  ];
  for (const [name, better] of cases) {
    test(name, () => {
      expect(compareRows(row("A", better), row("B"))).toBeLessThan(0);
      expect(compareRows(row("B"), row("A", better))).toBeGreaterThan(0);
    });
  }
  test("fully equal rows compare 0", () => {
    expect(compareRows(row("A"), row("B"))).toBe(0);
  });
});

type SeasonFile = {
  fixtures: (Fixture & { hg: number; ag: number })[];
  official: string[];
};

for (const year of [2025, 2026]) {
  test(`reproduces the official ${year - 1}-${String(year).slice(2)} league-phase table`, () => {
    const s: SeasonFile = JSON.parse(readFileSync(new URL(`./fixtures/ucl-${year}.json`, import.meta.url), "utf8"));
    const results = new Map<string, Result>(s.fixtures.map((f) => [f.id, { id: f.id, hg: f.hg, ag: f.ag }]));
    const { rows, randomTies } = leagueTable(s.fixtures, results, new Rng(1));
    expect(rows.map((r) => r.club)).toEqual(s.official);
    expect(randomTies).toBe(0);
  });
}
