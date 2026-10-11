import type { SeasonJson } from "@cutline/sim";
import { loadIndex } from "./data.ts";
import { day, pct } from "./format.ts";
import { outcome, rps } from "./metrics.ts";
import type { Snapshot } from "./types.ts";

const base = import.meta.env.BASE_URL + "data/";
const get = async <T>(p: string): Promise<T> => (await fetch(base + p)).json();
const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
const repo = "https://github.com/iliev-blnk/cutline/blob/main/predictions/2027/";

type Baseline = { fixtures: Record<string, { h: number; d: number; a: number }> };

async function start() {
  const index = await loadIndex();
  const season = await get<SeasonJson>("season.json");
  const snaps = await Promise.all(index.map((i) => get<Snapshot & { baseline?: Baseline }>("snapshots/" + i.file)));
  const odds = await Promise.all(
    index.map((i) => ((i as { odds?: boolean }).odds ? get<{ fixtures: Record<string, [number, number, number]> }>("snapshots/" + i.file.replace(/\.json$/, ".odds.json")) : null)),
  );
  const name = (c: string) => esc(season.clubs[c]?.name ?? c);
  const byId = new Map(season.fixtures.map((f) => [f.id, f]));

  const totals = { model: [] as number[], elo: [] as number[], market: [] as number[], modelVsMarket: [] as number[] };
  const blocks = snaps.map((s, k) => {
    const fx = season.fixtures.filter((f) => f.md === s.beforeMd);
    const rows = fx.map((f) => {
      const p = s.fixtures[f.id];
      const done = byId.get(f.id)!.status === "FINISHED";
      let score = "", r = "";
      if (done && p) {
        const o = outcome(f.hg!, f.ag!);
        const v = rps([p.h, p.d, p.a], o);
        totals.model.push(v);
        const b = s.baseline?.fixtures[f.id];
        if (b) totals.elo.push(rps([b.h, b.d, b.a], o));
        const mk = odds[k]?.fixtures[f.id];
        if (mk) {
          totals.market.push(rps(mk, o));
          totals.modelVsMarket.push(v);
        }
        score = `${f.hg}–${f.ag}`;
        r = v.toFixed(3);
      }
      return (
        `<div class="rfix fixture-head"><span class="teams">${name(f.home)} – ${name(f.away)}</span>` +
        `<span class="p">${p ? pct(p.h) : ""}</span><span class="p">${p ? pct(p.d) : ""}</span><span class="p">${p ? pct(p.a) : ""}</span>` +
        `<span class="p">${score}</span><span class="p">${r}</span></div>`
      );
    });
    return (
      `<div class="snapshot"><p><a href="${repo}${index[k].file}">${day(s.generatedAt)}</a>, before Matchday ${s.beforeMd}` +
      `${s.untuned ? " (untuned)" : ""}</p>` +
      `<div class="fixture-head muted"><span class="teams"></span><span class="p">H</span><span class="p">D</span><span class="p">A</span><span class="p">result</span><span class="p">RPS</span></div>` +
      rows.join("") +
      `</div>`
    );
  });
  const mean = (a: number[]) => (a.length ? (a.reduce((x, y) => x + y, 0) / a.length).toFixed(3) : "–");
  document.getElementById("summary")!.innerHTML =
    `<p>Matches scored: ${totals.model.length}. Mean RPS: model ${mean(totals.model)}` +
    (totals.elo.length ? `, Elo baseline ${mean(totals.elo)}` : "") +
    `.</p>` +
    (totals.market.length
      ? `<p>On the ${totals.market.length} matches with bookmaker odds: model ${mean(totals.modelVsMarket)}, market ${mean(totals.market)}.</p>`
      : `<p class="muted">No Champions League bookmaker odds recorded yet; the market comparison so far is the domestic backtest on the method page.</p>`);
  document.getElementById("snapshots")!.innerHTML = blocks.reverse().join("");
  drawClub(snaps, season);
}

function drawClub(snaps: Snapshot[], season: SeasonJson) {
  const el = document.getElementById("club")!;
  const clubs = Object.keys(season.clubs).sort((a, b) => season.clubs[a].name.localeCompare(season.clubs[b].name));
  el.innerHTML =
    `<p>P(top 8) over the season: <select aria-label="club">${clubs.map((c) => `<option value="${c}">${esc(season.clubs[c].name)}</option>`).join("")}</select></p><div class="line"></div>`;
  const sel = el.querySelector("select")!;
  const top = Object.keys(snaps.at(-1)!.clubs).sort((a, b) => snaps.at(-1)!.clubs[b].top8 - snaps.at(-1)!.clubs[a].top8)[0];
  sel.value = top;
  const draw = () => {
    const vals = snaps.map((s) => s.clubs[sel.value]?.top8 ?? 0);
    const W = 560, H = 120, step = W / 8;
    let d = "";
    vals.forEach((v, i) => {
      const x0 = (snaps[i].beforeMd! - 1) * step, x1 = x0 + step, y = H - v * H;
      d += `${i ? "L" : "M"}${x0},${y}H${x1}`;
    });
    const labels = Array.from({ length: 8 }, (_, i) => `<text x="${i * step + 2}" y="${H + 14}">MD${i + 1}</text>`).join("");
    el.querySelector(".line")!.innerHTML =
      `<svg viewBox="-30 -6 ${W + 40} ${H + 24}" width="100%" style="max-width:${W + 40}px" font-size="10" font-family="inherit">` +
      `<line x1="0" x2="${W}" y1="${H}" y2="${H}" stroke="#000" stroke-width="0.5"/><line x1="0" x2="${W}" y1="0" y2="0" stroke="#000" stroke-width="0.5" stroke-dasharray="2 3"/>` +
      `<text x="-28" y="4">100</text><text x="-14" y="${H + 3}">0</text>${labels}` +
      `<path d="${d}" fill="none" stroke="#000" stroke-width="1.5"/></svg>` +
      `<p class="muted">${vals.map((v, i) => `before MD${snaps[i].beforeMd}: ${pct(v)}%`).join(" · ")}</p>`;
  };
  sel.addEventListener("change", draw);
  draw();
}

start().catch((e) => (document.getElementById("summary")!.textContent = "could not load data: " + String(e)));
