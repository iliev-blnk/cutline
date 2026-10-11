import type { Rng } from "./rng.ts";
import type { ClubId, Fixture, Result, TableRow } from "./types.ts";

const ORDER: (keyof TableRow)[] = ["pts", "gd", "gf", "awayGf", "w", "awayW", "oppPts", "oppGd", "oppGf"];

/** Negative when a ranks above b (UEFA league-phase criteria; disciplinary and coefficient not modelled). */
export function compareRows(a: TableRow, b: TableRow): number {
  for (const k of ORDER) {
    const diff = (b[k] as number) - (a[k] as number);
    if (diff !== 0) return diff;
  }
  return 0;
}

export function leagueTable(
  fixtures: Fixture[],
  results: Map<string, Result>,
  rng: Rng,
): { rows: TableRow[]; randomTies: number } {
  const rows = new Map<ClubId, TableRow>();
  const opponents = new Map<ClubId, ClubId[]>();
  const get = (c: ClubId) => {
    let r = rows.get(c);
    if (!r) {
      r = { club: c, played: 0, w: 0, d: 0, l: 0, gf: 0, ga: 0, gd: 0, pts: 0, awayGf: 0, awayW: 0, oppPts: 0, oppGd: 0, oppGf: 0 };
      rows.set(c, r);
      opponents.set(c, []);
    }
    return r;
  };
  for (const f of fixtures) {
    const h = get(f.home), a = get(f.away);
    opponents.get(f.home)!.push(f.away);
    opponents.get(f.away)!.push(f.home);
    const r = results.get(f.id);
    if (!r) continue;
    h.played++;
    a.played++;
    h.gf += r.hg;
    h.ga += r.ag;
    a.gf += r.ag;
    a.ga += r.hg;
    a.awayGf += r.ag;
    if (r.hg > r.ag) {
      h.w++;
      h.pts += 3;
      a.l++;
    } else if (r.hg < r.ag) {
      a.w++;
      a.awayW++;
      a.pts += 3;
      h.l++;
    } else {
      h.d++;
      a.d++;
      h.pts++;
      a.pts++;
    }
  }
  for (const r of rows.values()) r.gd = r.gf - r.ga;
  for (const r of rows.values()) {
    for (const o of opponents.get(r.club)!) {
      const or = rows.get(o)!;
      r.oppPts += or.pts;
      r.oppGd += or.gd;
      r.oppGf += or.gf;
    }
  }
  const list = [...rows.values()];
  const key = new Map(list.map((r) => [r.club, rng.next()]));
  list.sort((a, b) => compareRows(a, b) || key.get(a.club)! - key.get(b.club)!);
  let randomTies = 0;
  for (let i = 1; i < list.length; i++) if (compareRows(list[i - 1], list[i]) === 0) randomTies++;
  return { rows: list, randomTies };
}
