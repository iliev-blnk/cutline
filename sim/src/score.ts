/** Dixon–Coles score distribution, 0..MAX goals per side, row-major: index = home * (MAX + 1) + away. */
import type { Rng } from "./rng.ts";

export const MAX_GOALS = 10;
const N = MAX_GOALS + 1;

function poissonPmf(l: number): Float64Array {
  const p = new Float64Array(N);
  p[0] = Math.exp(-l);
  for (let k = 1; k < N; k++) p[k] = (p[k - 1] * l) / k;
  return p;
}

export function scoreMatrix(lh: number, la: number, rho: number, max = MAX_GOALS): Float64Array {
  if (max !== MAX_GOALS) throw new Error("only MAX_GOALS is supported");
  const ph = poissonPmf(lh), pa = poissonPmf(la);
  const m = new Float64Array(N * N);
  let z = 0;
  for (let x = 0; x < N; x++)
    for (let y = 0; y < N; y++) {
      let v = ph[x] * pa[y];
      if (x === 0 && y === 0) v *= 1 - lh * la * rho;
      else if (x === 0 && y === 1) v *= 1 + lh * rho;
      else if (x === 1 && y === 0) v *= 1 + la * rho;
      else if (x === 1 && y === 1) v *= 1 - rho;
      if (v < 0) v = 0;
      m[x * N + y] = v;
      z += v;
    }
  for (let i = 0; i < m.length; i++) m[i] /= z;
  return m;
}

export function matchProbs(lh: number, la: number, rho: number): { h: number; d: number; a: number } {
  const m = scoreMatrix(lh, la, rho);
  let h = 0, d = 0, a = 0;
  for (let x = 0; x < N; x++)
    for (let y = 0; y < N; y++) {
      const v = m[x * N + y];
      if (x > y) h += v;
      else if (x === y) d += v;
      else a += v;
    }
  return { h, d, a };
}

export function buildCdf(matrix: Float64Array): Float64Array {
  const c = new Float64Array(matrix.length);
  let s = 0;
  for (let i = 0; i < matrix.length; i++) {
    s += matrix[i];
    c[i] = s;
  }
  c[c.length - 1] = 1;
  return c;
}

export function sampleScore(cdf: Float64Array, rng: Rng): [number, number] {
  const u = rng.next();
  let i = 0;
  while (cdf[i] <= u) i++;
  return [(i / N) | 0, i % N];
}
