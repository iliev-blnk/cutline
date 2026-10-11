"""Hierarchical Dixon–Coles goals model.

log λ_home = μ_c + h_c + att_i − def_j,  log λ_away = μ_c + att_j − def_i
att_i = A_country(i) + a_i,  def_i = D_country(i) + d_i
c = the domestic league for league matches, EUR for UCL/UEL/UECL.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass
from datetime import datetime

import numpy as np
import pandas as pd
from scipy.optimize import minimize, minimize_scalar
from scipy.stats import poisson

from .fdata import COUNTRY_OF

EUROPEAN = {"UCL", "UEL", "UECL"}
EUR = "EUR"
MAX_GOALS = 10


class FitError(Exception):
    pass


@dataclass(frozen=True)
class Hyper:
    half_life: float = 365.0
    lambda_team: float = 1.0
    lambda_country: float = 0.1
    xg_blend: float = 0.0


DEFAULT = Hyper()
# Set from the 2023-24 tuning run (research/tune.csv) before the test seasons are scored; None = untuned.
TUNED: Hyper | None = Hyper(half_life=365.0, lambda_team=3.0, lambda_country=0.03, xg_blend=0.0)


def time_weights(age_days: np.ndarray, half_life: float) -> np.ndarray:
    return np.exp(-math.log(2) * age_days / half_life)


def dc_tau(x: int, y: int, lh: float, la: float, rho: float) -> float:
    if x == 0 and y == 0:
        return 1 - lh * la * rho
    if x == 0 and y == 1:
        return 1 + lh * rho
    if x == 1 and y == 0:
        return 1 + la * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


def score_matrix(lh: float, la: float, rho: float, max_goals: int = MAX_GOALS) -> np.ndarray:
    g = np.arange(max_goals + 1)
    m = np.outer(poisson.pmf(g, lh), poisson.pmf(g, la))
    for x in (0, 1):
        for y in (0, 1):
            m[x, y] *= dc_tau(x, y, lh, la, rho)
    return m / m.sum()


class Model:
    def __init__(self, clubs, countries, leagues, theta, rho, hyper, sd_att, sd_def, meta):
        self.clubs = clubs  # list of club ids
        self.ci = {c: i for i, c in enumerate(clubs)}
        self.countries, self.leagues = countries, leagues
        self.li = {l: i for i, l in enumerate(leagues)}
        C, K, L = len(clubs), len(countries), len(leagues)
        self.a, self.d = theta[:C], theta[C:2 * C]
        self.A, self.D = theta[2 * C:2 * C + K], theta[2 * C + K:2 * C + 2 * K]
        self.mu = theta[2 * C + 2 * K:2 * C + 2 * K + L]
        self.h_dom, self.h_eur = float(theta[-2]), float(theta[-1])
        self.rho, self.hyper = float(rho), hyper
        self.sd_att, self.sd_def = sd_att, sd_def
        self.meta = meta  # club_country (index), names, countries, cutoff, input_hash, n_matches

    def att(self, club: str) -> float:
        i = self.ci[club]
        return float(self.A[self.meta["club_country"][i]] + self.a[i])

    def defn(self, club: str) -> float:
        i = self.ci[club]
        return float(self.D[self.meta["club_country"][i]] + self.d[i])

    def club(self, club: str) -> dict:
        i = self.ci[club]
        return {"name": self.meta["names"].get(club, club), "country": self.countries[self.meta["club_country"][i]],
                "att": self.att(club), "def": self.defn(club),
                "sd_att": float(self.sd_att[i]), "sd_def": float(self.sd_def[i])}

    def rates(self, home: str, away: str, context: str, neutral: bool) -> tuple[float, float]:
        mu = self.mu[self.li[context]]
        h = 0.0 if neutral else (self.h_eur if context == EUR else self.h_dom)
        lh = math.exp(mu + h + self.att(home) - self.defn(away))
        la = math.exp(mu + self.att(away) - self.defn(home))
        return lh, la

    def probs(self, home: str, away: str, context: str, neutral: bool) -> tuple[float, float, float]:
        m = score_matrix(*self.rates(home, away, context, neutral), self.rho)
        return float(np.tril(m, -1).sum()), float(np.trace(m)), float(np.triu(m, 1).sum())

    def to_json(self) -> dict:
        return {
            "version": 1,
            "cutoff": self.meta["cutoff"],
            "input_hash": self.meta["input_hash"],
            "n_matches": self.meta["n_matches"],
            "hyper": asdict(self.hyper),
            "rho": self.rho,
            "mu_eur": float(self.mu[self.li[EUR]]),
            "h_eur": self.h_eur,
            "h_dom": self.h_dom,
            "clubs": {c: self.club(c) for c in self.clubs if not c.startswith("fd:")},
        }


def _prepare(df: pd.DataFrame, cutoff: datetime, hyper: Hyper, domestic: set[str]):
    cut = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    d = df[(df["status"] == "FINISHED") & (df["kickoff_utc"] < cut)
           & df["home_goals"].notna() & df["away_goals"].notna()]
    d = d[d["competition"].isin(domestic | EUROPEAN)].sort_values(["kickoff_utc", "match_id"])
    if len(d) == 0:
        raise FitError("no training matches before cutoff")
    h = hashlib.sha256()
    for r in d[["match_id", "home_id", "away_id", "home_goals", "away_goals"]].itertuples(index=False):
        h.update("|".join(map(str, r)).encode())
    return d, h.hexdigest()


def fit(df: pd.DataFrame, cutoff: datetime, hyper: Hyper = DEFAULT, domestic: set[str] | None = None) -> Model:
    domestic = set(COUNTRY_OF) if domestic is None else set(domestic)
    d, input_hash = _prepare(df, cutoff, hyper, domestic)

    clubs = sorted(set(d["home_id"]) | set(d["away_id"]))
    ci = {c: i for i, c in enumerate(clubs)}
    country = {}
    names = {}
    for side in ("home", "away"):
        for cid, cc, nm in zip(d[f"{side}_id"], d[f"{side}_country"], d[f"{side}_name"]):
            country.setdefault(cid, cc)
            names.setdefault(cid, nm)
    countries = sorted(set(country.values()))
    ki = {k: i for i, k in enumerate(countries)}
    leagues = sorted(set(d["competition"]) - EUROPEAN) + [EUR]
    li = {l: i for i, l in enumerate(leagues)}
    club_country = np.array([ki[country[c]] for c in clubs])
    C, K, L = len(clubs), len(countries), len(leagues)

    hi = d["home_id"].map(ci).to_numpy()
    ai = d["away_id"].map(ci).to_numpy()
    euro = d["competition"].isin(EUROPEAN).to_numpy()
    lg = np.array([li[EUR] if e else li[c] for e, c in zip(euro, d["competition"])])
    home_adv = ~d["neutral"].astype(bool).to_numpy()
    gh = d["home_goals"].to_numpy(float)
    ga = d["away_goals"].to_numpy(float)
    yh, ya = gh.copy(), ga.copy()
    if hyper.xg_blend > 0:
        xh, xa = d["home_xg"].to_numpy(float), d["away_xg"].to_numpy(float)
        ok = np.isfinite(xh) & np.isfinite(xa)
        b = hyper.xg_blend
        yh[ok] = (1 - b) * gh[ok] + b * xh[ok]
        ya[ok] = (1 - b) * ga[ok] + b * xa[ok]
    ko = pd.to_datetime(d["kickoff_utc"], utc=True)
    age = ((cutoff - ko).dt.total_seconds() / 86400).to_numpy()
    w = time_weights(age, hyper.half_life)
    c00, c01, c10, c11 = (gh == 0) & (ga == 0), (gh == 0) & (ga == 1), (gh == 1) & (ga == 0), (gh == 1) & (ga == 1)
    hk, ak = club_country[hi], club_country[ai]
    nP = 2 * C + 2 * K + L + 2
    o_A, o_D, o_mu, o_hd, o_he = 2 * C, 2 * C + K, 2 * C + 2 * K, nP - 2, nP - 1

    def unpack(th):
        a, dd = th[:C], th[C:2 * C]
        A, D = th[o_A:o_D], th[o_D:o_mu]
        mu = th[o_mu:o_hd]
        att, de = A[club_country] + a, D[club_country] + dd
        h = np.where(euro, th[o_he], th[o_hd]) * home_adv
        eta_h = mu[lg] + h + att[hi] - de[ai]
        eta_a = mu[lg] + att[ai] - de[hi]
        return a, dd, A, D, eta_h, eta_a

    def objective(th, rho):
        a, dd, A, D, eta_h, eta_a = unpack(th)
        lh, la = np.exp(eta_h), np.exp(eta_a)
        tau = np.ones_like(lh)
        tau[c00] = 1 - lh[c00] * la[c00] * rho
        tau[c01] = 1 + lh[c01] * rho
        tau[c10] = 1 + la[c10] * rho
        tau[c11] = 1 - rho
        if np.any(tau <= 0):
            return 1e300, np.zeros_like(th)
        nll = np.sum(w * (lh - yh * eta_h + la - ya * eta_a)) - np.sum(w * np.log(tau))
        nll += 0.5 * hyper.lambda_team * (a @ a + dd @ dd) + 0.5 * hyper.lambda_country * (A @ A + D @ D)
        # d nll / d eta
        rh, ra = w * (lh - yh), w * (la - ya)
        t00 = w[c00] * lh[c00] * la[c00] * rho / tau[c00]
        rh[c00] += t00
        ra[c00] += t00
        rh[c01] -= w[c01] * lh[c01] * rho / tau[c01]
        ra[c10] -= w[c10] * la[c10] * rho / tau[c10]
        g_att = np.bincount(hi, rh, C) + np.bincount(ai, ra, C)
        g_def = -np.bincount(ai, rh, C) - np.bincount(hi, ra, C)
        g = np.empty_like(th)
        g[:C] = g_att + hyper.lambda_team * a
        g[C:2 * C] = g_def + hyper.lambda_team * dd
        g[o_A:o_D] = np.bincount(club_country, g_att, K) + hyper.lambda_country * A
        g[o_D:o_mu] = np.bincount(club_country, g_def, K) + hyper.lambda_country * D
        g[o_mu:o_hd] = np.bincount(lg, rh + ra, L)
        g[o_hd] = np.sum(rh[~euro & home_adv])
        g[o_he] = np.sum(rh[euro & home_adv])
        return nll, g

    th = np.zeros(nP)
    th[o_mu:o_hd] = math.log(max(np.average((yh + ya) / 2, weights=w), 0.1))
    th[o_hd] = th[o_he] = 0.2
    rho = 0.0
    for _ in range(2):
        res = minimize(objective, th, args=(rho,), jac=True, method="L-BFGS-B",
                       options={"maxiter": 5000, "maxfun": 20000, "gtol": 1e-6})
        if not res.success and "ABNORMAL" not in str(res.message):
            raise FitError(f"optimizer failed: {res.message}")
        th = res.x
        r = minimize_scalar(lambda r_: objective(th, r_)[0], bounds=(-0.2, 0.2), method="bounded")
        rho = float(r.x)
    if not np.all(np.isfinite(th)) or not math.isfinite(rho):
        raise FitError("non-finite parameters")

    # Laplace approximation (diagonal) for each club's att and def
    _, _, _, _, eta_h, eta_a = unpack(th)
    lh, la = np.exp(eta_h), np.exp(eta_a)
    H_a = np.bincount(hi, w * lh, C) + np.bincount(ai, w * la, C)  # info on att_i
    H_d = np.bincount(ai, w * lh, C) + np.bincount(hi, w * la, C)  # info on def_i
    H_A = np.bincount(club_country, H_a, K) + hyper.lambda_country
    H_D = np.bincount(club_country, H_d, K) + hyper.lambda_country
    sd_att = np.sqrt(1 / (H_a + hyper.lambda_team) + 1 / H_A[club_country])
    sd_def = np.sqrt(1 / (H_d + hyper.lambda_team) + 1 / H_D[club_country])

    meta = {"club_country": club_country, "names": names, "cutoff": cutoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "input_hash": input_hash, "n_matches": int(len(d))}
    return Model(clubs, countries, leagues, th, rho, hyper, sd_att, sd_def, meta)
