import math

import numpy as np
import pandas as pd

from cutline.backtest import GRID, GRID_EXT, devig, logloss3, rps3
from cutline.elo import elo_history, fit_elo_goals


def df_of(rows):
    base = dict(status="FINISHED", neutral=False, competition="E0", home_country="ENG", away_country="ENG")
    return pd.DataFrame([{**base, "match_id": f"m{i}", **r} for i, r in enumerate(rows)])


def test_elo_update():
    df = df_of([dict(kickoff_utc="2025-01-01T15:00:00Z", home_id="A", away_id="B", home_goals=1, away_goals=0)])
    ratings, _ = elo_history(df, k=20, home=60)
    expected = 1500 + 20 * (1 - 1 / (1 + 10 ** (-60 / 400)))
    assert math.isclose(ratings["A"], expected, abs_tol=1e-9)
    assert math.isclose(ratings["A"] + ratings["B"], 3000, abs_tol=1e-9)
    assert round(ratings["A"], 1) == 1508.3


def test_elo_goal_difference_multiplier():
    df = df_of([dict(kickoff_utc="2025-01-01T15:00:00Z", home_id="A", away_id="B", home_goals=3, away_goals=0)])
    ratings, _ = elo_history(df, k=20, home=60)
    assert math.isclose(ratings["A"] - 1500, 1.75 * 20 * (1 - 1 / (1 + 10 ** (-60 / 400))), abs_tol=1e-9)


def test_elo_goals_regression_recovers_slope():
    rng = np.random.default_rng(0)
    diffs = rng.normal(0, 150, 4000)
    lh = np.exp(0.1 + 0.25 + 0.6 * diffs / 400)
    la = np.exp(0.1 - 0.6 * diffs / 400)
    # elo_history's differences include the 60-point home advantage
    g = fit_elo_goals(diffs + 60, rng.poisson(lh), rng.poisson(la), np.ones(4000, bool))
    assert abs(g.c1 - 0.6) < 0.05 and abs(g.ch - 0.25) < 0.05


def test_rps3_values():
    assert rps3((1, 0, 0), 0) == 0
    assert rps3((0, 0, 1), 0) == 1
    assert math.isclose(rps3((1 / 3, 1 / 3, 1 / 3), 1), 1 / 9)
    assert math.isclose(logloss3((0.5, 0.25, 0.25), 0), math.log(2))


def test_devig_sums_to_one():
    p = devig(2.0, 3.4, 3.9)
    assert math.isclose(sum(p), 1.0)
    assert p[0] > p[1] > p[2]


def test_tune_grid_is_fixed():
    assert sorted({g.half_life for g in GRID}) == [90, 180, 365, 730]
    assert sorted({g.lambda_team for g in GRID}) == [0.3, 1, 3]
    assert sorted({g.lambda_country for g in GRID}) == [0.03, 0.1, 0.3]
    assert sorted({g.xg_blend for g in GRID}) == [0, 0.5]
    assert len(GRID) == 72


def test_grid_extension_is_lambda_team_edge_only():
    assert sorted({g.lambda_team for g in GRID_EXT}) == [10, 30]
    assert {g.xg_blend for g in GRID_EXT} == {0}
