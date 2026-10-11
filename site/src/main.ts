import { leagueTable, Rng, type ClubOut, type Result, type SeasonOut } from "@cutline/sim";
import { loadIndex, loadSnapshot } from "./data.ts";
import { renderFixtures, openMatchdays } from "./fixtures.ts";
import { day, phaseLabel } from "./format.ts";
import { renderGrid } from "./grid.ts";
import { decodeForced, encodeForced } from "./hash.ts";
import type { Loaded } from "./types.ts";

const $ = (id: string) => document.getElementById(id)!;

function points(L: Loaded, forced: Map<string, Result>): Map<string, number> {
  const results = new Map<string, Result>();
  for (const f of L.season.fixtures) if (f.status === "FINISHED" && f.hg !== null && f.ag !== null) results.set(f.id, { id: f.id, hg: f.hg, ag: f.ag });
  for (const [id, r] of forced) results.set(id, r);
  return new Map(leagueTable(L.season.fixtures, results, new Rng(0)).rows.map((r) => [r.club, r.pts]));
}

async function start() {
  const index = await loadIndex();
  const latest = index.at(-1)!;
  const L = await loadSnapshot(latest.file);
  const { snap, season } = L;
  const openIds = new Set(season.fixtures.filter((f) => f.status !== "FINISHED").map((f) => f.id));
  let forced = decodeForced(location.hash, openIds);
  let out: SeasonOut = snap;
  let token = 0;
  const mds = openMatchdays(season);
  const view = { season, probs: snap.fixtures, forced, md: mds[0] ?? 0, open: null as string | null };

  $("head").innerHTML =
    `<p>cutline — Champions League 2026-27, simulated ${snap.n.toLocaleString("en")} times.</p>` +
    `<p class="muted">${phaseLabel(snap.beforeMd)}, results to ${day(snap.modelCutoff)}. ` +
    `Each row is a club; each column a final league-phase position; darker = more likely. ` +
    `The lines are the cuts after 8th (round of 16) and 24th (play-off).</p>` +
    (snap.untuned ? `<p class="muted">This snapshot uses untuned default settings (the first one, published before the model was backtested).</p>` : "") +
    `<nav><a href="record.html">record</a><a href="method.html">method</a><a href="https://github.com/iliev-blnk/cutline">github</a></nav>`;

  const whatif = $("whatif");
  whatif.innerHTML = `<p>What if</p><div class="tabs"></div><div class="list"></div><p class="status muted"></p>`;
  const status = whatif.querySelector(".status") as HTMLElement;

  const draw = () => {
    const pts = points(L, forced);
    const rows = Object.keys(season.clubs).map((club) => ({
      club,
      pts: pts.get(club) ?? 0,
      out: out.clubs[club] as ClubOut,
      base: snap.clubs[club] as ClubOut,
    }));
    renderGrid($("grid"), season, rows, forced.size > 0);
    view.forced = forced;
    renderFixtures(whatif, view);
  };

  const worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
  worker.postMessage({ type: "init", model: L.model, season });
  worker.onmessage = (e) => {
    if (e.data.token !== token) return;
    out = e.data.out;
    const n = forced.size;
    status.innerHTML = `${n} result${n === 1 ? "" : "s"} set · ${(e.data.ms / 1000).toFixed(1)} s · <button class="linkish" data-reset>reset</button>`;
    draw();
  };

  const rerun = () => {
    history.replaceState(null, "", encodeForced(forced) || location.pathname);
    if (forced.size === 0) {
      out = snap;
      status.textContent = "";
      draw();
      return;
    }
    token++;
    status.textContent = "simulating…";
    worker.postMessage({ type: "run", forced: [...forced.values()].map((r) => [r.id, r.hg, r.ag]), seed: snap.seed, token });
  };

  whatif.addEventListener("click", (e) => {
    const t = e.target as HTMLElement;
    const md = t.closest("[data-md]") as HTMLElement | null;
    if (md) {
      view.md = Number(md.dataset.md);
      view.open = null;
      return draw();
    }
    if (t.closest("[data-reset]")) {
      forced = new Map();
      view.open = null;
      return rerun();
    }
    const set = t.closest("[data-set]") as HTMLElement | null;
    if (set) {
      const id = (set.closest(".picker") as HTMLElement).dataset.for!;
      const kind = set.dataset.set!;
      forced = new Map(forced);
      if (kind === "clear") forced.delete(id);
      else {
        let [hg, ag] = kind.split("-").map(Number);
        if (kind === "custom") {
          const v = (s: string) => Math.max(0, Math.min(10, Math.round(Number((whatif.querySelector(`.picker [data-side="${s}"]`) as HTMLInputElement).value) || 0)));
          [hg, ag] = [v("h"), v("a")];
        }
        forced.set(id, { id, hg, ag });
      }
      view.open = null;
      return rerun();
    }
    const fx = t.closest(".fixture[data-id]") as HTMLElement | null;
    if (fx) {
      view.open = view.open === fx.dataset.id ? null : fx.dataset.id!;
      draw();
    }
  });

  draw();
  if (forced.size) rerun();
}

start().catch((e) => {
  $("head").textContent = "cutline: could not load data (" + String(e) + ")";
});
