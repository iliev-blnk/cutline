"""Map football-data club names to UEFA team ids, so a club is one node in the model."""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from .fdata import COUNTRY_OF
from .schema import Match

_DROP = {"fc", "cf", "afc", "sc", "sk", "fk", "ac", "as", "ss", "club", "de", "the", "1", "calcio"}
_SUBS = [("ø", "o"), ("ı", "i"), ("ß", "ss"), ("æ", "ae"), ("đ", "d"), ("ł", "l")]
_WORDS = {"munchen": "munich"}
THRESHOLD = 0.6


class UnmappedClubs(Exception):
    def __init__(self, clubs: list[tuple[str, str]]):
        super().__init__("unmapped clubs (add rows to data/team_map.csv): " + ", ".join(f"{c}:{n}" for c, n in clubs))
        self.clubs = clubs


def norm_name(s: str) -> str:
    s = s.lower()
    for a, b in _SUBS:
        s = s.replace(a, b)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    toks = [_WORDS.get(t, t) for t in re.split(r"[^a-z0-9]+", s) if t]
    return " ".join(t for t in toks if t not in _DROP)


def _similarity(a: str, b: str) -> float:
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def _overrides(path: Path) -> tuple[dict[tuple[str, str], str], set[tuple[str, str]]]:
    """(league, fd_name) -> uefa_id, and the set of (country, uefa_name) marked '-' (no domestic data)."""
    mapped, absent = {}, set()
    if path.exists():
        for r in csv.DictReader(path.open(encoding="utf-8")):
            if r["uefa_id"].strip() == "-":
                absent.add((r["fd_league"].strip(), r["fd_name"].strip()))
            else:
                mapped[(r["fd_league"].strip(), r["fd_name"].strip())] = r["uefa_id"].strip()
    return mapped, absent


def map_teams(fd: list[Match], uefa: list[Match], overrides: Path) -> dict[tuple[str, str], str]:
    mapped, absent = _overrides(overrides)
    # fd names per country (with their league)
    fd_by_country: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for m in fd:
        fd_by_country[COUNTRY_OF[m.competition]].add((m.competition, m.home_name))
        fd_by_country[COUNTRY_OF[m.competition]].add((m.competition, m.away_name))
    clubs: dict[str, tuple[str, str]] = {}
    for m in uefa:
        clubs[m.home_id] = (m.home_country, m.home_name)
        clubs[m.away_id] = (m.away_country, m.away_name)

    result = dict(mapped)
    taken_ids = set(mapped.values())
    unmapped = []
    claims: dict[tuple[str, str], list[str]] = defaultdict(list)
    for uid, (country, name) in sorted(clubs.items()):
        if uid in taken_ids or country not in fd_by_country or (country, name) in absent:
            continue
        n = norm_name(name)
        scored = sorted(((_similarity(n, norm_name(fn)), (lg, fn)) for lg, fn in fd_by_country[country]
                         if (lg, fn) not in mapped), reverse=True)
        exact = [k for s, k in scored if norm_name(k[1]) == n]
        if len(exact) == 1:
            claims[exact[0]].append(uid)
        elif scored and scored[0][0] >= THRESHOLD and (len(scored) == 1 or scored[1][0] < scored[0][0]):
            claims[scored[0][1]].append(uid)
        else:
            unmapped.append((country, name))
    for key, uids in claims.items():
        if len(uids) == 1:
            result[key] = uids[0]
        else:
            unmapped += [clubs[u] for u in uids]
    if unmapped:
        raise UnmappedClubs(sorted(unmapped))
    return result
