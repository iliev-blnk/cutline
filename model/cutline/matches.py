"""Build the normalized match table (data/matches.csv.gz) and this season's league phase (season-<Y>.json)."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd

from .fdata import EXTRA, TOP_DIVS, fd_extra, fd_matches, season_codes
from .schema import MATCH_COLUMNS, Match
from .teams import map_teams
from .uefa import COMPETITIONS, normalize_uefa, uefa_matches

DATA = Path(__file__).resolve().parents[2] / "data"
FIRST_SEASON = 2022  # 2021-22
CURRENT = 2027  # 2026-27
SINCE = "2021-07-01"


class SeasonInvalid(Exception):
    pass


def validate_season(season: dict) -> None:
    fx = season["fixtures"]
    if len(fx) != 144:
        raise SeasonInvalid(f"expected 144 league-phase fixtures, got {len(fx)}")
    home, away = Counter(f["home"] for f in fx), Counter(f["away"] for f in fx)
    clubs = set(home) | set(away)
    if len(clubs) != 36:
        raise SeasonInvalid(f"expected 36 clubs, got {len(clubs)}")
    bad = [c for c in clubs if home[c] != 4 or away[c] != 4]
    if bad:
        raise SeasonInvalid(f"clubs without 4 home + 4 away matches: {sorted(bad)}")


def season_json(ucl: list[Match], season_year: int) -> dict:
    league = [m for m in ucl if m.season == season_year and m.stage == "GROUP_STANDINGS"]
    clubs = {}
    for m in league:
        clubs[m.home_id] = {"name": m.home_name, "country": m.home_country}
        clubs[m.away_id] = {"name": m.away_name, "country": m.away_country}
    fixtures = [
        {"id": m.match_id.removeprefix("uefa:"), "md": m.matchday, "home": m.home_id, "away": m.away_id,
         "kickoff": m.kickoff_utc, "status": m.status, "hg": m.home_goals, "ag": m.away_goals}
        for m in sorted(league, key=lambda m: (m.kickoff_utc, m.match_id))
    ]
    out = {"seasonYear": season_year, "clubs": clubs, "fixtures": fixtures}
    validate_season(out)
    return out


def build_matches(today: date | None = None, data_dir: Path = DATA) -> pd.DataFrame:
    today = today or date.today()
    uefa: list[Match] = []
    for cid, comp in COMPETITIONS.items():
        for y in range(FIRST_SEASON, CURRENT + 1):
            uefa += normalize_uefa(uefa_matches(cid, y, today), comp)
    fd: list[Match] = []
    for div in TOP_DIVS:
        for code, y in season_codes(FIRST_SEASON, CURRENT):
            fd += fd_matches(div, code, y, today)
    for cc in EXTRA:
        fd += fd_extra(cc, SINCE)

    mapping = map_teams(fd, uefa, data_dir / "team_map.csv")
    for m in fd:
        m.home_id = mapping.get((m.competition, m.home_name), m.home_id)
        m.away_id = mapping.get((m.competition, m.away_name), m.away_id)

    df = pd.DataFrame([m.row() for m in uefa + fd], columns=MATCH_COLUMNS)
    df = df[df["date"] >= SINCE].sort_values(["kickoff_utc", "match_id"]).reset_index(drop=True)
    df.to_csv(data_dir / "matches.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})

    season = season_json([m for m in uefa if m.competition == "UCL"], CURRENT)
    (data_dir / f"season-{CURRENT}.json").write_text(json.dumps(season, indent=1, ensure_ascii=False))
    return df


def load_matches(data_dir: Path = DATA) -> pd.DataFrame:
    return pd.read_csv(data_dir / "matches.csv.gz", dtype={"home_id": str, "away_id": str, "match_id": str})
