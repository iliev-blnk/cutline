import numpy as np

from cutline.backtest import model_predict, month_starts
from cutline.fit import fit
from tests.test_fit import BIG, CUTOFF, synthetic


def test_model_predict_matches_scalar_probs():
    df, *_ = synthetic(n=1500)
    m = fit(df, CUTOFF, BIG, domestic={"L_AAA", "L_BBB", "L_CCC"})
    rows = df.iloc[:40]
    H, D, A, ok = model_predict(m, rows)
    assert ok.all()
    for i, r in enumerate(rows.itertuples()):
        ctx = "EUR" if r.competition == "UCL" else r.competition
        ph, pd_, pa = m.probs(r.home_id, r.away_id, ctx, neutral=False)
        assert abs(H[i] - ph) < 1e-9 and abs(D[i] - pd_) < 1e-9 and abs(A[i] - pa) < 1e-9


def test_unknown_club_is_not_ok():
    df, *_ = synthetic(n=800)
    m = fit(df, CUTOFF, BIG, domestic={"L_AAA", "L_BBB", "L_CCC"})
    rows = df.iloc[:3].copy()
    rows.loc[rows.index[0], "home_id"] = "nobody"
    *_, ok = model_predict(m, rows)
    assert ok.tolist() == [False, True, True]


def test_month_starts():
    ms = month_starts("2023-07-01", "2024-07-01")
    assert len(ms) == 12 and ms[-1].month == 6 and ms[0].year == 2023
