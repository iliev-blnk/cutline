"""Backtest: tune on 2023-24, test once on 2024-25 and 2025-26 (match level + league-phase outcomes)."""

from __future__ import annotations

import json
import math
import subprocess
import tempfile
from dataclasses import asdict, replace
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import poisson

from .elo import elo_history, fit_elo_goals
from .fdata import COUNTRY_OF
from .fit import EUR, EUROPEAN, Hyper, Model, fit
from .matches import DATA, load_matches

ROOT = DATA.parent
RESEARCH = ROOT / "research"
GRID = [Hyper(h, lt, lc, xb) for h in (90, 180, 365, 730) for lt in (0.3, 1, 3) for lc in (0.03, 0.1, 0.3) for xb in (0, 0.5)]
# The first tune put lambda_team at the grid edge (3); extended on the tuning season only.
# xG exists only from 2026-07 in football-data.co.uk, so the xG blend cannot be tuned or tested on past seasons.
GRID_EXT = [Hyper(h, lt, lc, 0.0) for h in (180, 365, 730) for lt in (10, 30) for lc in (0.03, 0.1, 0.3)]
TUNE = ("2023-07-01", "2024-07-01")
TEST = ("2024-07-01", "2026-07-01")
DOMESTIC = set(COUNTRY_OF)
G = np.arange(11)


# ---------- scores ----------

def rps3(p, outcome: int) -> float:
    o = [0.0, 0.0, 0.0]
    o[outcome] = 1.0
    c1 = p[0] - o[0]
    c2 = p[0] + p[1] - o[0] - o[1]
    return (c1 * c1 + c2 * c2) / 2


def logloss3(p, outcome: int) -> float:
    return -math.log(max(p[outcome], 1e-12))


def devig(oh: float, od: float, oa: float) -> tuple[float, float, float]:
    inv = np.array([1 / oh, 1 / od, 1 / oa])
    p = inv / inv.sum()
    return float(p[0]), float(p[1]), float(p[2])


def rps_vec(ph, pd_, outcome) -> np.ndarray:
    o0 = (outcome == 0).astype(float)
    o1 = (outcome <= 1).astype(float)
    return ((ph - o0) ** 2 + (ph + pd_ - o1) ** 2) / 2


# ---------- vectorized predictions ----------

def probs_from_rates(lh: np.ndarray, la: np.ndarray, rho: float):
    ph_ = poisson.pmf(G[None, :], lh[:, None])
    pa_ = poisson.pmf(G[None, :], la[:, None])
    m = ph_[:, :, None] * pa_[:, None, :]
    m[:, 0, 0] *= 1 - lh * la * rho
    m[:, 0, 1] *= 1 + lh * rho
    m[:, 1, 0] *= 1 + la * rho
    m[:, 1, 1] *= 1 - rho
    m = np.clip(m, 0, None)
    m /= m.sum(axis=(1, 2), keepdims=True)
    low = np.tril(np.ones((11, 11), bool), -1)
    H = m[:, low].sum(axis=1)
    D = np.trace(m, axis1=1, axis2=2)
    return H, D, 1 - H - D


def model_predict(m: Model, rows: pd.DataFrame):
    cc = m.meta["club_country"]
    att = m.A[cc] + m.a
    de = m.D[cc] + m.d
    hi = rows["home_id"].map(m.ci)
    ai = rows["away_id"].map(m.ci)
    euro = rows["competition"].isin(EUROPEAN).to_numpy()
    li = np.where(euro, m.li[EUR], rows["competition"].map(m.li).fillna(-1).to_numpy()).astype(int)
    ok = hi.notna().to_numpy() & ai.notna().to_numpy() & (li >= 0)
    hi = hi.fillna(0).astype(int).to_numpy()
    ai = ai.fillna(0).astype(int).to_numpy()
    mu = m.mu[np.where(li >= 0, li, 0)]
    h = np.where(euro, m.h_eur, m.h_dom) * (~rows["neutral"].astype(bool).to_numpy())
    lh = np.exp(mu + h + att[hi] - de[ai])
    la = np.exp(mu + att[ai] - de[hi])
    H, D, A = probs_from_rates(lh, la, m.rho)
    return H, D, A, ok


def outcomes(rows: pd.DataFrame) -> np.ndarray:
    hg, ag = rows["home_goals"].to_numpy(), rows["away_goals"].to_numpy()
    return np.where(hg > ag, 0, np.where(hg == ag, 1, 2))


def month_starts(start: str, end: str) -> list[datetime]:
    out, d = [], datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    stop = datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
    while d < stop:
        out.append(d)
        d = d.replace(year=d.year + (d.month == 12), month=d.month % 12 + 1)
    return out


def _iso(d: datetime) -> str:
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def month_rows(df: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
    r = df[(df["kickoff_utc"] >= _iso(start)) & (df["kickoff_utc"] < _iso(end)) & (df["status"] == "FINISHED")
           & df["home_goals"].notna() & df["competition"].isin(DOMESTIC | EUROPEAN)]
    return r


# ---------- tuning ----------

_DF: pd.DataFrame | None = None


def _init():
    global _DF
    _DF = load_matches()


def _tune_job(args):
    hyper, start, end = args
    m = fit(_DF, start, hyper)
    rows = month_rows(_DF, start, end)
    H, D, A, ok = model_predict(m, rows)
    o = outcomes(rows)
    return asdict(hyper), float(rps_vec(H[ok], D[ok], o[ok]).sum()), int(ok.sum())


def tune(processes: int = 8, grid: list[Hyper] | None = None) -> Hyper:
    grid = [h for h in GRID if h.xg_blend == 0] + GRID_EXT if grid is None else grid
    months = month_starts(*TUNE) + [datetime.fromisoformat(TUNE[1]).replace(tzinfo=timezone.utc)]
    jobs = [(h, months[i], months[i + 1]) for h in grid for i in range(len(months) - 1)]
    with Pool(processes, initializer=_init) as pool:
        res = pool.map(_tune_job, jobs, chunksize=4)
    agg: dict[tuple, list[float]] = {}
    for h, s, n in res:
        k = tuple(h.values())
        a = agg.setdefault(k, [0.0, 0])
        a[0] += s
        a[1] += n
    rows = [dict(zip(asdict(GRID[0]).keys(), k), rps=v[0] / v[1], n=v[1]) for k, v in agg.items()]
    t = pd.DataFrame(rows).sort_values("rps")
    RESEARCH.mkdir(exist_ok=True)
    t.to_csv(RESEARCH / "tune.csv", index=False)
    best = t.iloc[0]
    return Hyper(float(best.half_life), float(best.lambda_team), float(best.lambda_country), float(best.xg_blend))


# ---------- test: match level ----------

def _base_rates(df: pd.DataFrame, cutoff: datetime) -> dict[str, tuple[float, float, float]]:
    d = df[(df["kickoff_utc"] < _iso(cutoff)) & (df["kickoff_utc"] >= _iso(cutoff.replace(year=cutoff.year - 3)))
           & (df["status"] == "FINISHED") & df["home_goals"].notna()]
    ctx = np.where(d["competition"].isin(EUROPEAN), EUR, d["competition"])
    o = outcomes(d)
    out = {}
    for c in np.unique(ctx):
        oc = o[ctx == c]
        out[c] = tuple(float((oc == k).mean()) for k in range(3))
    return out


def _test_job(args):
    hypers, start, end = args
    df = _DF
    rows = month_rows(df, start, end)
    o = outcomes(rows)
    rec = pd.DataFrame({"match_id": rows["match_id"].to_numpy(), "competition": rows["competition"].to_numpy(),
                        "outcome": o})
    for name, h in hypers.items():
        H, D, A, ok = model_predict(fit(df, start, h), rows)
        rec[f"{name}_h"], rec[f"{name}_d"], rec[f"{name}_ok"] = H, D, ok
    # Elo, re-run from scratch on everything before the month
    past = df[df["kickoff_utc"] < _iso(start)]
    ratings, diffs = elo_history(past)
    fin = past[(past["status"] == "FINISHED") & past["home_goals"].notna()].sort_values(["kickoff_utc", "match_id"])
    recent = (fin["kickoff_utc"] >= _iso(start.replace(year=start.year - 2))).to_numpy()
    home_adv = ~fin["neutral"].astype(bool).to_numpy()
    eg = fit_elo_goals(diffs[recent], fin["home_goals"].to_numpy()[recent], fin["away_goals"].to_numpy()[recent],
                       home_adv[recent])
    rh = rows["home_id"].map(ratings)
    ra = rows["away_id"].map(ratings)
    eok = rh.notna().to_numpy() & ra.notna().to_numpy()
    lh, la = eg.rates((rh.fillna(1500) - ra.fillna(1500)).to_numpy(), (~rows["neutral"].astype(bool)).to_numpy())
    eh, ed, _ = probs_from_rates(lh, la, 0.0)
    rec["elo_h"], rec["elo_d"], rec["elo_ok"] = eh, ed, eok
    br = _base_rates(df, start)
    ctx = np.where(rows["competition"].isin(EUROPEAN), EUR, rows["competition"])
    rec["base_h"] = [br.get(c, (np.nan,) * 3)[0] for c in ctx]
    rec["base_d"] = [br.get(c, (np.nan,) * 3)[1] for c in ctx]
    rec["base_ok"] = rec["base_h"].notna()
    oh, od, oa = (rows[c].to_numpy(float) for c in ("odds_h", "odds_d", "odds_a"))
    mok = np.isfinite(oh) & np.isfinite(od) & np.isfinite(oa) & (oh > 1) & (od > 1) & (oa > 1)
    inv = np.stack([1 / np.where(mok, oh, 2), 1 / np.where(mok, od, 2), 1 / np.where(mok, oa, 2)])
    p = inv / inv.sum(axis=0)
    rec["market_h"], rec["market_d"], rec["market_ok"] = p[0], p[1], mok
    return rec


def _score(rec: pd.DataFrame, names: list[str]) -> dict:
    ok = np.logical_and.reduce([rec[f"{n}_ok"].to_numpy(bool) for n in names])
    r = rec[ok]
    out = {"n": int(ok.sum())}
    o = r["outcome"].to_numpy()
    for n in names:
        h, d = r[f"{n}_h"].to_numpy(), r[f"{n}_d"].to_numpy()
        a = 1 - h - d
        p = np.choose(o, [h, d, a])
        out[n] = {"rps": float(rps_vec(h, d, o).mean()), "logloss": float(-np.log(np.clip(p, 1e-12, None)).mean())}
    return out


def match_level(hyper: Hyper, processes: int = 8) -> dict:
    hypers = {"model": hyper}
    months = month_starts(*TEST) + [datetime.fromisoformat(TEST[1]).replace(tzinfo=timezone.utc)]
    jobs = [(hypers, months[i], months[i + 1]) for i in range(len(months) - 1)]
    with Pool(processes, initializer=_init) as pool:
        recs = pool.map(_test_job, jobs)
    rec = pd.concat(recs, ignore_index=True)
    rec.to_csv(RESEARCH / "test_matches.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    groups = {
        "ucl": rec["competition"] == "UCL",
        "uefa_all": rec["competition"].isin(EUROPEAN),
        "domestic": rec["competition"].isin(DOMESTIC),
    }
    out = {}
    for g, mask in groups.items():
        sub = rec[mask.to_numpy()]
        out[g] = _score(sub, ["model", "elo", "base"])
    out["domestic_with_odds"] = _score(rec[groups["domestic"].to_numpy()], ["model", "elo", "base", "market"])
    out["hyper"] = asdict(hyper)
    return out


# ---------- test: league-phase outcomes ----------

def run_sim(model_json: dict, season: dict, seed: int, n: int = 10_000) -> dict:
    with tempfile.TemporaryDirectory() as t:
        mp, sp, op = Path(t, "m.json"), Path(t, "s.json"), Path(t, "o.json")
        mp.write_text(json.dumps(model_json))
        sp.write_text(json.dumps(season))
        subprocess.run(["pnpm", "--dir", str(ROOT / "sim"), "exec", "tsx", "src/cli.ts", "snapshot", "--model", str(mp),
                        "--season", str(sp), "--seed", str(seed), "--n", str(n), "--out", str(op)],
                       check=True, capture_output=True)
        return json.loads(op.read_text())


def _actual(year: int, season_file: dict) -> dict[str, dict[str, int]]:
    from .uefa import uefa_matches

    raw = uefa_matches(1, year)
    qf = {str(t["id"]) for m in raw if m["round"]["metaData"]["type"] == "QUARTER_FINALS" for t in (m["homeTeam"], m["awayTeam"])}
    final = next(m for m in raw if m["round"]["metaData"]["type"] == "FINAL")
    winner = str(final["winner"]["match"]["team"]["id"])
    rank = {c: i + 1 for i, c in enumerate(season_file["official"])}
    return {c: {"top8": int(rank[c] <= 8), "top24": int(rank[c] <= 24), "qf": int(c in qf), "win": int(c == winner)}
            for c in rank}


def outcome_level(hyper: Hyper) -> dict:
    df = load_matches()
    events = ["top8", "top24", "qf", "win"]
    pooled = []
    briers: dict[str, dict[str, list[float]]] = {m: {e: [] for e in events} for m in ("model", "elo", "equal")}
    for year in (2025, 2026):
        sf = json.loads((ROOT / "sim" / "test" / "fixtures" / f"ucl-{year}.json").read_text())
        actual = _actual(year, sf)
        for md in range(1, 9):
            cutoff_iso = min(f["kickoff"] for f in sf["fixtures"] if f["md"] == md)
            cutoff = datetime.fromisoformat(cutoff_iso.replace("Z", "+00:00"))
            season = {"seasonYear": year, "clubs": sf["clubs"], "fixtures": [
                {**f, "status": "FINISHED"} if f["md"] < md else {**f, "status": "UPCOMING", "hg": None, "ag": None}
                for f in sf["fixtures"]]}
            mj = fit(df, cutoff, hyper).to_json()
            past = df[df["kickoff_utc"] < cutoff_iso]
            ratings, diffs = elo_history(past)
            fin = past[(past["status"] == "FINISHED") & past["home_goals"].notna()].sort_values(["kickoff_utc", "match_id"])
            recent = (fin["kickoff_utc"] >= _iso(cutoff.replace(year=cutoff.year - 2))).to_numpy()
            eg = fit_elo_goals(diffs[recent], fin["home_goals"].to_numpy()[recent], fin["away_goals"].to_numpy()[recent],
                               (~fin["neutral"].astype(bool)).to_numpy()[recent])
            ej = eg.to_model_json(ratings, sf["clubs"])
            eq = {**mj, "clubs": {c: {**mj["clubs"][c], "att": 0.0, "def": 0.0, "sd_att": 0.0, "sd_def": 0.0} for c in sf["clubs"]}}
            for name, js in (("model", mj), ("elo", ej), ("equal", eq)):
                out = run_sim(js, season, seed=year * 100 + md)
                for c, y in actual.items():
                    o = out["clubs"][c]
                    p = {"top8": o["top8"], "top24": o["top8"] + o["mid"], "qf": o["qf"], "win": o["win"]}
                    for e in events:
                        briers[name][e].append((p[e] - y[e]) ** 2)
                        if name == "model":
                            pooled.append((e, p[e], y[e]))
            print(f"outcome backtest {year} before MD{md} done", flush=True)
    res = {m: {e: float(np.mean(v)) for e, v in d.items()} for m, d in briers.items()}
    bins = []
    for lo in np.arange(0, 1, 0.1):
        pts = [(p, y) for _, p, y in pooled if lo <= p < lo + 0.1 or (lo >= 0.9 and p == 1.0)]
        if pts:
            bins.append({"lo": float(lo), "n": len(pts), "mean_p": float(np.mean([p for p, _ in pts])),
                         "observed": float(np.mean([y for _, y in pts]))})
    res["reliability"] = bins
    return res


def reliability_svg(bins: list[dict]) -> str:
    W = 320
    pts = "".join(f'<circle cx="{40 + b["mean_p"] * W:.1f}" cy="{20 + (1 - b["observed"]) * W:.1f}" r="{2 + math.sqrt(b["n"]) / 6:.1f}" fill="#000"/>'
                  f'<text x="{46 + b["mean_p"] * W:.1f}" y="{16 + (1 - b["observed"]) * W:.1f}" font-size="9">{b["n"]}</text>' for b in bins)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W + 60}" height="{W + 60}" font-family="monospace" font-size="10">'
            f'<rect width="100%" height="100%" fill="#fff"/>'
            f'<line x1="40" y1="{20 + W}" x2="{40 + W}" y2="20" stroke="#999" stroke-dasharray="3 3"/>'
            f'<rect x="40" y="20" width="{W}" height="{W}" fill="none" stroke="#000"/>'
            f'<text x="40" y="{W + 38}">predicted probability (bin mean)</text>'
            f'<text x="2" y="14">observed</text><text x="30" y="{W + 24}">0</text><text x="{W + 34}" y="{W + 24}">1</text>'
            f"{pts}</svg>")


def test(hyper: Hyper, processes: int = 8) -> dict:
    RESEARCH.mkdir(exist_ok=True)
    out = {"hyper": asdict(hyper), "match_level": match_level(hyper, processes), "outcome_level": outcome_level(hyper)}
    (RESEARCH / "test.json").write_text(json.dumps(out, indent=1))
    (RESEARCH / "figures").mkdir(exist_ok=True)
    (RESEARCH / "figures" / "reliability.svg").write_text(reliability_svg(out["outcome_level"]["reliability"]))
    return out
