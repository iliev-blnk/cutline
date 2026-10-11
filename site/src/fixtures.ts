import type { FixtureOut, Result, SeasonFixture, SeasonJson } from "@cutline/sim";
import { pct } from "./format.ts";

export interface FixtureView {
  season: SeasonJson;
  probs: Record<string, FixtureOut>;
  forced: Map<string, Result>;
  md: number;
  open: string | null; // fixture id whose picker is open
}

function esc(s: string): string {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
}

export function openMatchdays(season: SeasonJson): number[] {
  return [...new Set(season.fixtures.filter((f) => f.status !== "FINISHED").map((f) => f.md))].sort((a, b) => a - b);
}

function row(f: SeasonFixture, v: FixtureView): string {
  const name = (c: string) => esc(v.season.clubs[c]?.name ?? c);
  const p = v.probs[f.id];
  const fr = v.forced.get(f.id);
  const right = fr
    ? `<span class="score">${fr.hg}–${fr.ag}</span>`
    : `<span class="p">${pct(p.h)}</span><span class="p">${pct(p.d)}</span><span class="p">${pct(p.a)}</span>`;
  const picker =
    v.open === f.id
      ? `<div class="picker" data-for="${f.id}">` +
        `<button data-set="1-0">1–0</button><button data-set="1-1">1–1</button><button data-set="0-1">0–1</button>` +
        `<input type="number" min="0" max="10" value="${fr?.hg ?? 2}" aria-label="home goals" data-side="h">–` +
        `<input type="number" min="0" max="10" value="${fr?.ag ?? 1}" aria-label="away goals" data-side="a">` +
        `<button data-set="custom">set</button>${fr ? '<button data-set="clear">clear</button>' : ""}</div>`
      : "";
  return (
    `<div class="fixture${fr ? " forced" : ""}" data-id="${f.id}" data-home="${f.home}" data-away="${f.away}">` +
    `<span class="teams">${name(f.home)} – ${name(f.away)}</span>${right}</div>${picker}`
  );
}

export function renderFixtures(el: HTMLElement, v: FixtureView): void {
  const mds = openMatchdays(v.season);
  const tabs = mds
    .map((md) => `<button data-md="${md}" aria-pressed="${md === v.md}">MD${md}</button>`)
    .join("");
  const list = v.season.fixtures.filter((f) => f.md === v.md && f.status !== "FINISHED");
  const head = `<div class="fixture-head muted"><span class="teams">click a match to set its result</span><span class="p">H</span><span class="p">D</span><span class="p">A</span></div>`;
  el.querySelector(".tabs")!.innerHTML = tabs;
  el.querySelector(".list")!.innerHTML = head + list.map((f) => row(f, v)).join("");
}
