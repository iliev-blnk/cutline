import pytest

from cutline.schema import Match
from cutline.matches import SeasonInvalid, validate_season
from cutline.teams import UnmappedClubs, map_teams, norm_name


def m(home, away, comp, hc, ac, hid=None, aid=None, date="2025-01-01"):
    return Match(
        match_id=f"{comp}:{home}:{away}:{date}", date=date, kickoff_utc=date + "T18:00:00Z",
        competition=comp, season=2025, stage="LEAGUE", matchday=None,
        home_id=hid or f"fd:{comp}:{home}", away_id=aid or f"fd:{comp}:{away}",
        home_name=home, away_name=away, home_country=hc, away_country=ac,
        status="FINISHED", home_goals=1, away_goals=0, neutral=False,
    )


def test_norm_name():
    assert norm_name("Bodø/Glimt") == norm_name("Bodo/Glimt")
    assert norm_name("FC Bayern München") == norm_name("Bayern Munich")
    assert norm_name("İstanbul Başakşehir") == "istanbul basaksehir"


FD = [
    m("Arsenal", "Chelsea", "E0", "ENG", "ENG"),
    m("Man City", "Liverpool", "E0", "ENG", "ENG"),
    m("Bayern Munich", "Dortmund", "D1", "GER", "GER"),
]
UEFA = [
    m("Arsenal", "Bayern München", "UCL", "ENG", "GER", "52280", "50037"),
    m("Manchester City", "Qarabağ", "UCL", "ENG", "AZE", "52919", "60609"),
    m("Liverpool", "B. Dortmund", "UCL", "ENG", "GER", "7889", "52758"),
]


def test_map_exact_and_override(tmp_path):
    ov = tmp_path / "team_map.csv"
    ov.write_text("fd_league,fd_name,uefa_id\nE0,Man City,52919\nD1,Dortmund,52758\n")
    got = map_teams(FD, UEFA, ov)
    assert got[("E0", "Arsenal")] == "52280"
    assert got[("D1", "Bayern Munich")] == "50037"
    assert got[("E0", "Man City")] == "52919"
    assert got[("E0", "Liverpool")] == "7889"


def test_override_wins_over_automatic(tmp_path):
    ov = tmp_path / "team_map.csv"
    # automatic matching would pair UEFA 52280 with fd "Arsenal"; the override says it is "Chelsea"
    ov.write_text("fd_league,fd_name,uefa_id\nE0,Chelsea,52280\nE0,Man City,52919\nD1,Dortmund,52758\n")
    got = map_teams(FD, UEFA, ov)
    assert got[("E0", "Chelsea")] == "52280"
    assert ("E0", "Arsenal") not in got


def test_unmapped_raises(tmp_path):
    ov = tmp_path / "team_map.csv"
    ov.write_text("fd_league,fd_name,uefa_id\nD1,Dortmund,52758\n")
    with pytest.raises(UnmappedClubs) as e:
        map_teams(FD, UEFA, ov)
    assert ("ENG", "Manchester City") in e.value.clubs


def test_country_without_fd_is_not_required(tmp_path):
    ov = tmp_path / "team_map.csv"
    ov.write_text("fd_league,fd_name,uefa_id\nE0,Man City,52919\nD1,Dortmund,52758\n")
    got = map_teams(FD, UEFA, ov)  # Qarabağ (AZE) has no domestic data: fine
    assert "60609" not in got.values()


def test_dash_marks_club_absent_from_domestic_data(tmp_path):
    ov = tmp_path / "team_map.csv"
    ov.write_text("fd_league,fd_name,uefa_id\nENG,Manchester City,-\nD1,Dortmund,52758\n")
    got = map_teams(FD, UEFA, ov)  # no raise: Man City explicitly marked as absent
    assert "52919" not in got.values()


def _season(n_fix=144, bad_home=False):
    clubs = [str(i) for i in range(36)]
    fixtures = []
    # a valid round-robin-ish schedule: club i hosts i+1..i+4, visits i-1..i-4 (mod 36)
    for i in range(36):
        for k in range(1, 5):
            fixtures.append({"id": f"{i}-{k}", "md": k, "home": clubs[i], "away": clubs[(i + k) % 36]})
    if bad_home:
        f = fixtures[0]
        f["home"], f["away"] = f["away"], f["home"]
    return {"seasonYear": 2027, "clubs": {c: {} for c in clubs}, "fixtures": fixtures[:n_fix]}


def test_validate_season():
    validate_season(_season())
    with pytest.raises(SeasonInvalid):
        validate_season(_season(n_fix=143))
    with pytest.raises(SeasonInvalid):
        validate_season(_season(bad_home=True))
