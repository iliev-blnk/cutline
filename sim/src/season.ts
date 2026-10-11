import { knockout } from "./knockout.ts";
import { Rng } from "./rng.ts";
import { MAX_GOALS, sampleDC, scoreMatrix } from "./score.ts";
import { drawStrengths, rates } from "./strength.ts";
import { leagueTable } from "./table.ts";
import type { ClubId, ModelJson, Result, SeasonJson } from "./types.ts";

export { drawStrengths } from "./strength.ts";

export interface ClubOut {
  posDist: number[];
  top8: number;
  mid: number;
  out: number;
  r16: number;
  qf: number;
  sf: number;
  final: number;
  win: number;
  expPts: number;
}

export interface FixtureOut {
  h: number;
  d: number;
  a: number;
  xgH: number;
  xgA: number;
}

export interface SeasonOut {
  n: number;
  seed: number;
  clubs: Record<ClubId, ClubOut>;
  fixtures: Record<string, FixtureOut>;
  randomTies: number;
}

export interface RunArgs {
  model: ModelJson;
  season: SeasonJson;
  forced: Map<string, Result>;
  n: number;
  seed: number;
}

const N = MAX_GOALS + 1;
/** Fixture H/D/A are averaged over this many strength draws (Monte Carlo error ~0.2%). */
export const PROB_DRAWS = 500;

export function runSeason({ model, season, forced, n, seed }: RunArgs): SeasonOut {
  const rng = new Rng(seed);
  const clubs = Object.keys(season.clubs);
  const base = new Map<string, Result>();
  for (const f of season.fixtures) if (f.status === "FINISHED" && f.hg !== null && f.ag !== null) base.set(f.id, { id: f.id, hg: f.hg, ag: f.ag });
  const open = season.fixtures.filter((f) => !base.has(f.id));
  const toSample = open.filter((f) => !forced.has(f.id));

  const pos = new Map(clubs.map((c) => [c, new Float64Array(36)]));
  const acc = new Map(clubs.map((c) => [c, { r16: 0, qf: 0, sf: 0, final: 0, win: 0, pts: 0 }]));
  const fx = new Map(open.map((f) => [f.id, { h: 0, d: 0, a: 0, xgH: 0, xgA: 0 }]));
  let randomTies = 0;
  const probDraws = Math.min(n, PROB_DRAWS);

  for (let i = 0; i < n; i++) {
    const s = drawStrengths(model, clubs, rng);
    const results = new Map(base);
    for (const [id, r] of forced) if (!base.has(id)) results.set(id, r);
    for (const f of open) {
      const [lh, la] = rates(model, s, f.home, f.away, false);
      if (i < probDraws) {
        const m = scoreMatrix(lh, la, model.rho);
        const o = fx.get(f.id)!;
        for (let x = 0; x < N; x++)
          for (let y = 0; y < N; y++) {
            const v = m[x * N + y];
            if (x > y) o.h += v;
            else if (x === y) o.d += v;
            else o.a += v;
          }
        o.xgH += lh;
        o.xgA += la;
      }
      if (!forced.has(f.id)) {
        const [hg, ag] = sampleDC(lh, la, model.rho, rng);
        results.set(f.id, { id: f.id, hg, ag });
      }
    }
    const t = leagueTable(season.fixtures, results, rng);
    randomTies += t.randomTies;
    const order = t.rows.map((r) => r.club);
    t.rows.forEach((r, k) => {
      pos.get(r.club)![k]++;
      acc.get(r.club)!.pts += r.pts;
    });
    const ko = knockout(order, model, s, rng);
    for (const c of ko.r16) acc.get(c)!.r16++;
    for (const c of ko.qf) acc.get(c)!.qf++;
    for (const c of ko.sf) acc.get(c)!.sf++;
    for (const c of ko.final) acc.get(c)!.final++;
    acc.get(ko.winner)!.win++;
  }

  const outClubs: Record<ClubId, ClubOut> = {};
  for (const c of clubs) {
    const counts = pos.get(c)!;
    const p = Array.from(counts, (v) => v / n);
    const a = acc.get(c)!;
    // sum integer counts first so certain outcomes are exactly 0 or 1
    const sum = (lo: number, hi: number) => counts.slice(lo, hi).reduce((x, y) => x + y, 0) / n;
    outClubs[c] = {
      posDist: p,
      top8: sum(0, 8),
      mid: sum(8, 24),
      out: sum(24, 36),
      r16: a.r16 / n,
      qf: a.qf / n,
      sf: a.sf / n,
      final: a.final / n,
      win: a.win / n,
      expPts: a.pts / n,
    };
  }
  const outFx: Record<string, FixtureOut> = {};
  for (const [id, o] of fx) outFx[id] = { h: o.h / probDraws, d: o.d / probDraws, a: o.a / probDraws, xgH: o.xgH / probDraws, xgA: o.xgA / probDraws };
  return { n, seed, clubs: outClubs, fixtures: outFx, randomTies };
}
