"""football-data.co.uk results + closing odds (+ xG where present)."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .http import fetch_bytes
from .schema import Match

TOP_URL = "https://www.football-data.co.uk/mmz4281/{code}/{div}.csv"
EXTRA_URL = "https://www.football-data.co.uk/new/{cc}.csv"
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "fd"

TOP_DIVS = {
    "E0": "ENG", "SP1": "ESP", "D1": "GER", "I1": "ITA", "F1": "FRA", "P1": "POR",
    "N1": "NED", "T1": "TUR", "B1": "BEL", "G1": "GRE", "SC0": "SCO",
}
EXTRA = {"AUT": "AUT", "DNK": "DEN", "NOR": "NOR", "POL": "POL", "ROU": "ROU", "SWE": "SWE", "SWZ": "SUI"}
COUNTRY_OF = {**TOP_DIVS, **EXTRA}
UK = ZoneInfo("Europe/London")  # football-data times are UK local time


def season_codes(first_end_year: int, last_end_year: int) -> list[tuple[str, int]]:
    """[('2122', 2022), ...]: football-data season code and UEFA-style seasonYear."""
    return [(f"{(y - 1) % 100:02d}{y % 100:02d}", y) for y in range(first_end_year, last_end_year + 1)]


def _num(v: str | None) -> float | None:
    if v is None or v.strip() == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _odds(row: dict, prefixes: tuple[str, ...]) -> tuple[float | None, float | None, float | None]:
    for p in prefixes:
        h, d, a = _num(row.get(p + "H")), _num(row.get(p + "D")), _num(row.get(p + "A"))
        if h and d and a:
            return h, d, a
    return None, None, None


def _when(d: str, t: str | None) -> tuple[str, str]:
    fmt = "%d/%m/%Y" if len(d.split("/")[-1]) == 4 else "%d/%m/%y"
    day = datetime.strptime(d, fmt)
    hh, mm = (t or "15:00").split(":")[:2]
    local = day.replace(hour=int(hh), minute=int(mm), tzinfo=UK)
    utc = local.astimezone(ZoneInfo("UTC"))
    return utc.strftime("%Y-%m-%d"), utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def _rows(raw: bytes) -> list[dict]:
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig", errors="replace"))))


def _match(comp: str, country: str, season: int, d: str, t: str | None, home: str, away: str,
           hg: str, ag: str, odds, hxg=None, axg=None) -> Match | None:
    if not home or not away or hg in (None, "") or ag in (None, ""):
        return None
    day, ko = _when(d, t)
    return Match(
        match_id=f"fd:{comp}:{day}:{home}:{away}", date=day, kickoff_utc=ko, competition=comp,
        season=season, stage="LEAGUE", matchday=None,
        home_id=f"fd:{comp}:{home}", away_id=f"fd:{comp}:{away}", home_name=home, away_name=away,
        home_country=country, away_country=country, status="FINISHED",
        home_goals=int(float(hg)), away_goals=int(float(ag)), neutral=False,
        home_xg=hxg, away_xg=axg, odds_h=odds[0], odds_d=odds[1], odds_a=odds[2],
    )


def parse_top_csv(raw: bytes, div: str, season: int) -> list[Match]:
    out = []
    for r in _rows(raw):
        if not r.get("Date"):
            continue
        odds = _odds(r, ("PSC", "AvgC", "PS", "Avg", "B365C", "B365"))
        m = _match(div, TOP_DIVS[div], season, r["Date"], r.get("Time"), r.get("HomeTeam", ""),
                   r.get("AwayTeam", ""), r.get("FTHG"), r.get("FTAG"), odds,
                   _num(r.get("HxG")), _num(r.get("AxG")))
        if m:
            out.append(m)
    return out


def parse_extra_csv(raw: bytes, cc: str, since: str = "2021-07-01") -> list[Match]:
    out = []
    for r in _rows(raw):
        if not r.get("Date"):
            continue
        s = r.get("Season", "")
        season = int(s.split("/")[-1]) if s else 0
        odds = _odds(r, ("PSC", "AvgC", "B365C"))
        m = _match(cc, EXTRA[cc], season, r["Date"], r.get("Time"), r.get("Home", ""),
                   r.get("Away", ""), r.get("HG"), r.get("AG"), odds)
        if m and m.date >= since:
            out.append(m)
    return out


def _cached(name: str, url: str, final: bool) -> bytes:
    path = RAW_DIR / name
    if final and path.exists():
        return path.read_bytes()
    raw = fetch_bytes(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def fd_matches(div: str, code: str, season: int, today: date) -> list[Match]:
    final = today > date(season, 7, 1)
    return parse_top_csv(_cached(f"{code}-{div}.csv", TOP_URL.format(code=code, div=div), final), div, season)


def fd_extra(cc: str, since: str = "2021-07-01") -> list[Match]:
    return parse_extra_csv(_cached(f"extra-{cc}.csv", EXTRA_URL.format(cc=cc), False), cc, since)
