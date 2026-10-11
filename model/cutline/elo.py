"""Elo baseline: World Football Elo updates + a Poisson goals regression on the rating difference."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize

START = 1500.0


def gd_multiplier(gd: int) -> float:
    gd = abs(gd)
    if gd <= 1:
        return 1.0
    if gd == 2:
        return 1.5
    return (11 + gd) / 8


def elo_history(df: pd.DataFrame, k: float = 20, home: float = 60) -> tuple[dict[str, float], np.ndarray]:
    """Run Elo over the finished matches of df in kickoff order.
    Returns final ratings and, per row of the sorted finished frame, the pre-match difference (home − away, with home advantage)."""
    d = df[(df["status"] == "FINISHED") & df["home_goals"].notna()].sort_values(["kickoff_utc", "match_id"])
    r: dict[str, float] = {}
    diffs = np.empty(len(d))
    for i, (h, a, hg, ag, neutral) in enumerate(
        zip(d["home_id"], d["away_id"], d["home_goals"], d["away_goals"], d["neutral"].astype(bool))
    ):
        rh, ra = r.get(h, START), r.get(a, START)
        dr = rh - ra + (0 if neutral else home)
        diffs[i] = dr
        e = 1 / (1 + 10 ** (-dr / 400))
        s = 1.0 if hg > ag else 0.5 if hg == ag else 0.0
        delta = k * gd_multiplier(int(hg - ag)) * (s - e)
        r[h], r[a] = rh + delta, ra - delta
    return r, diffs


@dataclass(frozen=True)
class EloGoals:
    c0: float
    c1: float
    ch: float

    def rates(self, diff_no_home: np.ndarray, home_adv: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        lh = np.exp(self.c0 + self.c1 * diff_no_home / 400 + self.ch * home_adv)
        la = np.exp(self.c0 - self.c1 * diff_no_home / 400)
        return lh, la

    def to_model_json(self, ratings: dict[str, float], clubs: dict[str, dict]) -> dict:
        """ModelJson the TS sim can run: att = def = c1·r/400 so att_h − def_a = c1·Δ/400."""
        out = {}
        for c, meta in clubs.items():
            v = self.c1 * ratings.get(c, START) / 400
            out[c] = {"name": meta.get("name", c), "country": meta.get("country", ""), "att": v, "def": v,
                      "sd_att": 0.0, "sd_def": 0.0}
        return {"version": 1, "cutoff": "", "input_hash": "elo", "hyper": {}, "rho": 0.0,
                "mu_eur": self.c0, "h_eur": self.ch, "clubs": out}


def fit_elo_goals(diffs: np.ndarray, hg: np.ndarray, ag: np.ndarray, home_adv: np.ndarray, home: float = 60) -> EloGoals:
    """Poisson regression log λ = c0 + c1·Δ/400 + ch·home on the pre-match rating difference Δ (home advantage removed)."""
    hm = home_adv.astype(float)
    x = (diffs - home * hm) / 400
    hg, ag = np.asarray(hg, float), np.asarray(ag, float)

    def nll(p):
        c0, c1, ch = p
        eh, ea = c0 + c1 * x + ch * hm, c0 - c1 * x
        lh, la = np.exp(eh), np.exp(ea)
        f = np.sum(lh - hg * eh) + np.sum(la - ag * ea)
        g0 = np.sum(lh - hg) + np.sum(la - ag)
        g1 = np.sum((lh - hg) * x) - np.sum((la - ag) * x)
        g2 = np.sum((lh - hg) * hm)
        return f, np.array([g0, g1, g2])

    res = minimize(nll, np.array([math.log(1.3), 0.5, 0.2]), jac=True, method="L-BFGS-B")
    return EloGoals(*map(float, res.x))
