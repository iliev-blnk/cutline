/** Probability as a whole percent; "<1" / ">99" only when it is not certain. */
export function pct(p: number): string {
  if (p === 0) return "0";
  if (p === 1) return "100";
  if (p < 0.005) return "<1";
  if (p >= 0.995) return ">99";
  return String(Math.round(p * 100));
}

export function delta(now: number, base: number): string {
  const d = Math.round((now - base) * 100);
  // two runs with different forced results drift by ±1 point from sampling alone
  if (Math.abs(d) < 2) return "";
  return d > 0 ? `+${d}` : `−${-d}`;
}

export function day(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

/** Cell darkness: √(p / 0.25), capped at 1; blank below 0.5%. */
export function shade(p: number): number {
  if (p < 0.005) return 0;
  return Math.min(1, Math.sqrt(p / 0.25));
}
