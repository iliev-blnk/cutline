from pathlib import Path

from cutline.fdata import parse_extra_csv, parse_top_csv

FIX = Path(__file__).parent / "fixtures"


def test_fd_parse_e0():
    ms = parse_top_csv((FIX / "E0_sample.csv").read_bytes(), "E0", 2027)
    assert len(ms) == 5
    m = ms[0]
    assert m.competition == "E0"
    assert m.home_country == "ENG" and m.away_country == "ENG"
    assert m.home_id == "fd:E0:Arsenal"
    assert (m.home_goals, m.away_goals) == (3, 0)
    assert m.status == "FINISHED" and m.stage == "LEAGUE" and not m.neutral
    # no Pinnacle closing columns in this file: market-average closing is used
    assert m.odds_h == 1.2
    assert isinstance(m.home_xg, float) and m.home_xg == 1.88
    assert m.date == "2026-08-21" and m.kickoff_utc.startswith("2026-08-21T")


def test_fd_extra_prefers_pinnacle_closing():
    ms = parse_extra_csv((FIX / "AUT_sample.csv").read_bytes(), "AUT", since="2000-01-01")
    m = ms[0]
    assert m.home_name == "Sturm Graz" and m.competition == "AUT"
    assert (m.odds_h, m.odds_d, m.odds_a) == (3.26, 3.34, 2.4)
    assert m.home_xg is None


def test_fd_extra_filters_date():
    ms = parse_extra_csv((FIX / "AUT_sample.csv").read_bytes(), "AUT", since="2021-07-01")
    assert len(ms) == 3
    assert all(m.date >= "2021-07-01" for m in ms)
    assert ms[0].season == 2027
