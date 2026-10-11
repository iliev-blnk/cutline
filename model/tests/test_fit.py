from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from cutline.fit import Hyper, fit, time_weights

CUTOFF = datetime(2026, 1, 1, tzinfo=timezone.utc)


def synthetic(seed=1, n=3000, euro_only_country=False):
    rng = np.random.default_rng(seed)
    countries = ["AAA", "BBB", "CCC"] + (["ZZZ"] if euro_only_country else [])
    clubs = {c: [f"{c}{i}" for i in range(6)] for c in countries}
    A = {c: rng.normal(0, 0.3) for c in countries}
    D = {c: rng.normal(0, 0.3) for c in countries}
    att = {k: A[c] + rng.normal(0, 0.3) for c in countries for k in clubs[c]}
    dfn = {k: D[c] + rng.normal(0, 0.3) for c in countries for k in clubs[c]}
    country_of = {k: c for c in countries for k in clubs[c]}
    mu = {"L_AAA": 0.2, "L_BBB": 0.1, "L_CCC": 0.3}
    mu_eur, h_dom, h_eur = 0.1, 0.25, 0.3
    rows = []
    domestic = [c for c in countries if c != "ZZZ"]
    for i in range(n):
        euro = rng.random() < 0.3 or False
        if euro:
            h, a = rng.choice(sorted(att), 2, replace=False)
            while country_of[h] == country_of[a]:
                h, a = rng.choice(sorted(att), 2, replace=False)
            comp, m, hh = "UCL", mu_eur, h_eur
        else:
            c = domestic[rng.integers(len(domestic))]
            h, a = rng.choice(clubs[c], 2, replace=False)
            comp, m, hh = f"L_{c}", mu[f"L_{c}"], h_dom
        lh = np.exp(m + hh + att[h] - dfn[a])
        la = np.exp(m + att[a] - dfn[h])
        ko = CUTOFF - timedelta(days=int(rng.integers(1, 300)))
        rows.append(dict(
            match_id=f"m{i}", kickoff_utc=ko.strftime("%Y-%m-%dT%H:%M:%SZ"), competition=comp,
            home_id=h, away_id=a, home_name=h, away_name=a,
            home_country=country_of[h], away_country=country_of[a], status="FINISHED",
            home_goals=rng.poisson(lh), away_goals=rng.poisson(la), neutral=False,
            home_xg=np.nan, away_xg=np.nan,
        ))
    return pd.DataFrame(rows), att, dfn, h_dom


BIG = Hyper(half_life=10_000, lambda_team=1.0, lambda_country=0.1)


def test_recovers_synthetic():
    df, att, dfn, h_dom = synthetic()
    m = fit(df, CUTOFF, BIG, domestic={"L_AAA", "L_BBB", "L_CCC"})
    ids = sorted(att)
    fa = np.array([m.att(i) for i in ids])
    fd = np.array([m.defn(i) for i in ids])
    assert np.corrcoef(fa, [att[i] for i in ids])[0, 1] > 0.9
    assert np.corrcoef(fd, [dfn[i] for i in ids])[0, 1] > 0.9
    assert abs(m.h_dom - h_dom) < 0.05


def test_probs_sum_to_one():
    df, *_ = synthetic(n=800)
    m = fit(df, CUTOFF, BIG, domestic={"L_AAA", "L_BBB", "L_CCC"})
    ph, pd_, pa = m.probs("AAA0", "BBB1", "EUR", neutral=False)
    assert abs(ph + pd_ + pa - 1) < 1e-9
    assert min(ph, pd_, pa) > 0


def test_time_decay():
    w = time_weights(np.array([0.0, 300.0]), half_life=30)
    assert w[1] / w[0] < 0.001


def test_country_without_domestic():
    df, *_ = synthetic(n=3000, euro_only_country=True)
    m = fit(df, CUTOFF, BIG, domestic={"L_AAA", "L_BBB", "L_CCC"})
    z = [m.club(f"ZZZ{i}") for i in range(6)]
    others = [m.club(f"{c}{i}") for c in ("AAA", "BBB", "CCC") for i in range(6)]
    assert all(np.isfinite(c["att"]) and np.isfinite(c["def"]) for c in z)
    assert min(c["sd_att"] for c in z) > np.median([c["sd_att"] for c in others])


def test_cutoff_excludes_future():
    df, *_ = synthetic(n=1500)
    m1 = fit(df, CUTOFF, BIG, domestic={"L_AAA", "L_BBB", "L_CCC"})
    future = df.iloc[:200].copy()
    future["kickoff_utc"] = (CUTOFF + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    future["home_goals"] = 9
    future["match_id"] = future["match_id"] + "f"
    m2 = fit(pd.concat([df, future]), CUTOFF, BIG, domestic={"L_AAA", "L_BBB", "L_CCC"})
    assert m1.att("AAA0") == m2.att("AAA0")
    assert m1.to_json()["input_hash"] == m2.to_json()["input_hash"]
