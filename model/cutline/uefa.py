"""UEFA's public match and standings JSON (match.uefa.com, standings.uefa.com)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from .http import fetch_json
from .schema import Match, SchemaError

MATCHES_URL = "https://match.uefa.com/v5/matches?competitionId={cid}&seasonYear={year}&limit=100&offset={offset}&order=ASC"
STANDINGS_URL = "https://standings.uefa.com/v1/standings?competitionId=1&seasonYear={year}"
COMPETITIONS = {1: "UCL", 14: "UEL", 2019: "UECL"}
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "uefa"

_STATUS = {"FINISHED": "FINISHED", "UPCOMING": "UPCOMING", "LIVE": "LIVE", "IN_PLAY": "LIVE"}


def _season_over(season_year: int, today: date) -> bool:
    # seasonYear Y runs to the final in late May/June of year Y
    return today > date(season_year, 7, 1)


def uefa_matches(competition_id: int, season_year: int, today: date | None = None) -> list[dict]:
    today = today or date.today()
    cache = RAW_DIR / f"{competition_id}-{season_year}.json"
    if _season_over(season_year, today) and cache.exists():
        return json.loads(cache.read_text())
    out: list[dict] = []
    offset = 0
    while True:
        page = fetch_json(MATCHES_URL.format(cid=competition_id, year=season_year, offset=offset))
        out += page
        offset += 100
        if len(page) < 100:
            break
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(out))
    return out


def uefa_standings(season_year: int) -> list[dict]:
    return fetch_json(STANDINGS_URL.format(year=season_year))[0]["items"]


def _get(rec: dict, *path: str) -> Any:
    cur: Any = rec
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            raise SchemaError(p, f"match {rec.get('id', '?')}")
        cur = cur[p]
    return cur


def normalize_uefa(raw: list[dict], competition: str) -> list[Match]:
    out = []
    for r in raw:
        status = _STATUS.get(_get(r, "status"), "OTHER")
        ko = _get(r, "kickOffTime")
        kickoff = ko["dateTime"] if "dateTime" in ko else _get(ko, "date") + "T00:00:00Z"
        stage = _get(r, "round", "metaData", "type")
        md = r.get("matchday", {}).get("name") if isinstance(r.get("matchday"), dict) else None
        matchday = int(md[2:]) if md and md.startswith("MD") and md[2:].isdigit() else None
        hg = ag = None
        if status == "FINISHED":
            hg = int(_get(r, "score", "regular", "home"))
            ag = int(_get(r, "score", "regular", "away"))
        home, away = _get(r, "homeTeam"), _get(r, "awayTeam")
        out.append(
            Match(
                match_id=f"uefa:{_get(r, 'id')}",
                date=kickoff[:10],
                kickoff_utc=kickoff,
                competition=competition,
                season=int(_get(r, "seasonYear")),
                stage=stage,
                matchday=matchday,
                home_id=str(_get(home, "id")),
                away_id=str(_get(away, "id")),
                home_name=_get(home, "internationalName"),
                away_name=_get(away, "internationalName"),
                home_country=_get(home, "countryCode"),
                away_country=_get(away, "countryCode"),
                status=status,
                home_goals=hg,
                away_goals=ag,
                neutral=stage == "FINAL",
            )
        )
    return out
