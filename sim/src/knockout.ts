/**
 * Knockout phase from the final league-phase order (verified against the 2024-25 and 2025-26 brackets):
 * - play-off: 9/10 v 23/24, 11/12 v 21/22, 13/14 v 19/20, 15/16 v 17/18 (pairing within the pairs drawn);
 *   the seeded club (9-16) hosts the second leg
 * - R16: 1/2 v winners of the 15/16-17/18 ties, 3/4 v 13/14-19/20, 5/6 v 11/12-21/22, 7/8 v 9/10-23/24;
 *   the top-8 club hosts the second leg
 * - each seed pair is split across the two halves; in each half the QFs are (1/2 tie v 7/8 tie) and
 *   (3/4 tie v 5/6 tie); QF/SF leg order drawn; neutral final
 */
import type { Rng } from "./rng.ts";
import { sampleDC } from "./score.ts";
import { rates, type Strengths } from "./strength.ts";
import type { ClubId, ModelJson } from "./types.ts";

export type Pair = [ClubId, ClubId];

export interface KoResult {
  playoffs: Pair[];
  ties: { r16: Pair[]; qf: Pair[]; sf: Pair[] };
  r16: ClubId[];
  qf: ClubId[];
  sf: ClubId[];
  final: Pair;
  winner: ClubId;
}

const ET = 30 / 90;

function play(model: ModelJson, s: Strengths, home: ClubId, away: ClubId, neutral: boolean, rng: Rng, scale = 1): [number, number] {
  const [lh, la] = rates(model, s, home, away, neutral);
  return sampleDC(lh * scale, la * scale, model.rho, rng);
}

/** Two legs, `second` hosts leg 2 (and extra time). Returns the winner. */
function tie(model: ModelJson, s: Strengths, first: ClubId, second: ClubId, rng: Rng): ClubId {
  const [a1, b1] = play(model, s, first, second, false, rng); // first hosts leg 1
  const [b2, a2] = play(model, s, second, first, false, rng);
  let aggFirst = a1 + a2, aggSecond = b1 + b2;
  if (aggFirst === aggSecond) {
    const [e2, e1] = play(model, s, second, first, false, rng, ET);
    aggFirst += e1;
    aggSecond += e2;
  }
  if (aggFirst !== aggSecond) return aggFirst > aggSecond ? first : second;
  return rng.next() < 0.5 ? first : second;
}

function single(model: ModelJson, s: Strengths, a: ClubId, b: ClubId, rng: Rng): ClubId {
  let [x, y] = play(model, s, a, b, true, rng);
  if (x === y) {
    const [ex, ey] = play(model, s, a, b, true, rng, ET);
    x += ex;
    y += ey;
  }
  if (x !== y) return x > y ? a : b;
  return rng.next() < 0.5 ? a : b;
}

const flip = <T>(p: [T, T], rng: Rng): [T, T] => (rng.next() < 0.5 ? p : [p[1], p[0]]);

export function knockout(order: ClubId[], model: ModelJson, s: Strengths, rng: Rng): KoResult {
  const at = (rank: number) => order[rank - 1];
  // play-off: group g pairs seeds (9+2g, 10+2g) with (23-2g, 24-2g)
  const playoffs: Pair[] = [];
  const poWinners: Pair[] = []; // per group: two winners
  for (let g = 0; g < 4; g++) {
    const seeded: Pair = [at(9 + 2 * g), at(10 + 2 * g)];
    const unseeded = flip<ClubId>([at(23 - 2 * g), at(24 - 2 * g)], rng);
    const w: ClubId[] = [];
    for (let i = 0; i < 2; i++) {
      playoffs.push([unseeded[i], seeded[i]]);
      w.push(tie(model, s, unseeded[i], seeded[i], rng));
    }
    poWinners.push([w[0], w[1]]);
  }
  // R16: seed pair p (1/2, 3/4, 5/6, 7/8) meets the winners of play-off group 3-p
  const r16ties: Pair[][] = []; // per seed pair: two ties [unseeded, seeded]
  for (let p = 0; p < 4; p++) {
    const seeds: Pair = [at(1 + 2 * p), at(2 + 2 * p)];
    const opp = flip(poWinners[3 - p], rng);
    r16ties.push([
      [opp[0], seeds[0]],
      [opp[1], seeds[1]],
    ]);
  }
  // halves: each seed pair's two ties go to different halves
  const halves: Pair[][] = [[], []];
  for (let p = 0; p < 4; p++) {
    const [t0, t1] = flip(r16ties[p] as [Pair, Pair], rng);
    halves[0].push(t0);
    halves[1].push(t1);
  }
  const ties = { r16: [] as Pair[], qf: [] as Pair[], sf: [] as Pair[] };
  const r16 = order.slice(0, 8).concat(poWinners.flat());
  const qf: ClubId[] = [], sf: ClubId[] = [];
  const finalists: ClubId[] = [];
  for (const half of halves) {
    const w = half.map((t) => {
      ties.r16.push(t);
      return tie(model, s, t[0], t[1], rng);
    }); // index = seed pair 0..3
    qf.push(...w);
    const qfPairs: Pair[] = [flip<ClubId>([w[0], w[3]], rng), flip<ClubId>([w[1], w[2]], rng)];
    const qfW = qfPairs.map((p) => {
      ties.qf.push(p);
      return tie(model, s, p[0], p[1], rng);
    });
    sf.push(...qfW);
    const sfPair = flip<ClubId>([qfW[0], qfW[1]], rng);
    ties.sf.push(sfPair);
    finalists.push(tie(model, s, sfPair[0], sfPair[1], rng));
  }
  const final: Pair = [finalists[0], finalists[1]];
  return { playoffs, ties, r16, qf, sf, final, winner: single(model, s, final[0], final[1], rng) };
}
