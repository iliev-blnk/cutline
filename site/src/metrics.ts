/** Ranked probability score for a home/draw/away forecast; 0 is perfect, 1 is the worst. */
export function rps(p: [number, number, number], outcome: 0 | 1 | 2): number {
  const o = [0, 0, 0];
  o[outcome] = 1;
  const c1 = p[0] - o[0];
  const c2 = p[0] + p[1] - (o[0] + o[1]);
  return (c1 * c1 + c2 * c2) / 2;
}

export function outcome(hg: number, ag: number): 0 | 1 | 2 {
  return hg > ag ? 0 : hg === ag ? 1 : 2;
}
