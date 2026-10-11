import type { ClubOut, SeasonJson } from "@cutline/sim";
import { delta, pct, shade } from "./format.ts";

export interface GridRow {
  club: string;
  pts: number;
  out: ClubOut;
  base: ClubOut;
}

const CUTS = new Set([8, 24]);

function expectedPos(o: ClubOut): number {
  return o.posDist.reduce((s, p, k) => s + p * (k + 1), 0);
}

function cell(p: number, k: number): string {
  const cut = CUTS.has(k + 1) ? " cut" : "";
  const a = shade(p);
  const title = `${k + 1}: ${pct(p)}%`;
  return `<span class="c${cut}" style="background:rgba(0,0,0,${a.toFixed(3)})" title="${title}"></span>`;
}

function esc(s: string): string {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
}

export function renderGrid(el: HTMLElement, season: SeasonJson, rows: GridRow[], showDelta: boolean): void {
  const sorted = [...rows].sort((a, b) => expectedPos(a.out) - expectedPos(b.out));
  const headCells = Array.from({ length: 36 }, (_, k) => {
    const n = k + 1;
    const label = [1, 8, 9, 24, 25, 36].includes(n) ? String(n) : "";
    return `<span class="c${CUTS.has(n) ? " cut" : ""}">${label}</span>`;
  }).join("");
  const num = (cls: string, v: number, b: number, first = false) =>
    `<span class="num ${cls}${first ? " first" : ""}">${pct(v)}</span>` +
    (showDelta ? `<span class="delta">${delta(v, b)}</span>` : "");
  const head =
    `<div class="row head"><span class="name">final position</span><span class="pts">pts</span>` +
    `<span class="cells">${headCells}</span>` +
    `<span class="num first">top 8</span>${showDelta ? '<span class="delta"></span>' : ""}` +
    `<span class="num">9–24</span>${showDelta ? '<span class="delta"></span>' : ""}` +
    `<span class="num">out</span>${showDelta ? '<span class="delta"></span>' : ""}` +
    `<span class="num">win</span></div>`;
  const body = sorted
    .map((r) => {
      const name = esc(season.clubs[r.club]?.name ?? r.club);
      return (
        `<div class="row" data-club="${r.club}"><span class="name" title="${name}">${name}</span>` +
        `<span class="pts">${r.pts}</span><span class="cells">${r.out.posDist.map(cell).join("")}</span>` +
        num("top8", r.out.top8, r.base.top8, true) +
        num("mid", r.out.mid, r.base.mid) +
        num("out", r.out.out, r.base.out) +
        `<span class="num win">${pct(r.out.win)}</span>${showDelta ? `<span class="delta">${delta(r.out.win, r.base.win)}</span>` : ""}</div>`
      );
    })
    .join("");
  el.innerHTML = `<div class="grid">${head}${body}</div>`;
}
