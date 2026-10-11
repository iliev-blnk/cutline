import type { Rng } from "./rng.ts";
import type { ClubId, ModelJson } from "./types.ts";

export type Strengths = Map<ClubId, { att: number; def: number }>;

/** One season's club strengths: att/def ~ N(estimate, sd²). */
export function drawStrengths(model: ModelJson, clubs: ClubId[], rng: Rng): Strengths {
  const s: Strengths = new Map();
  for (const c of clubs) {
    const p = model.clubs[c];
    if (!p) throw new Error(`club ${c} missing from model`);
    s.set(c, { att: p.att + p.sd_att * rng.normal(), def: p.def + p.sd_def * rng.normal() });
  }
  return s;
}

export function rates(model: ModelJson, s: Strengths, home: ClubId, away: ClubId, neutral: boolean): [number, number] {
  const h = s.get(home)!, a = s.get(away)!;
  const adv = neutral ? 0 : model.h_eur;
  return [Math.exp(model.mu_eur + adv + h.att - a.def), Math.exp(model.mu_eur + a.att - h.def)];
}
