import type { Result } from "@cutline/sim";

/** `#f=<id>:<hg>-<ag>,…` — forced results in the URL so a scenario can be shared. */
export function encodeForced(forced: Map<string, Result>): string {
  if (forced.size === 0) return "";
  return "#f=" + [...forced.values()].map((r) => `${r.id}:${r.hg}-${r.ag}`).join(",");
}

export function decodeForced(hash: string, validIds: Set<string>): Map<string, Result> {
  const out = new Map<string, Result>();
  const m = /^#?f=(.*)$/.exec(hash);
  if (!m) return out;
  for (const part of m[1].split(",")) {
    const p = /^(\d+):(\d{1,2})-(\d{1,2})$/.exec(part);
    if (!p || !validIds.has(p[1])) continue;
    out.set(p[1], { id: p[1], hg: Number(p[2]), ag: Number(p[3]) });
  }
  return out;
}
