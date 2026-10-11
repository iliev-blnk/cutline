"""Optional Champions League match odds from the-odds-api.com (free tier; needs ODDS_API_KEY)."""

from __future__ import annotations

import csv
import statistics
from datetime import datetime, timedelta
from pathlib import Path

from .backtest import devig
from .http import fetch_json
from .teams import _similarity, norm_name

URL = "https://api.the-odds-api.com/v4/sports/soccer_uefa_champs_league/odds?regions=eu&markets=h2h&oddsFormat=decimal&apiKey={key}"
WINDOW = timedelta(hours=3)


def fetch_odds(api_key: str) -> list[dict]:
    return parse_odds(fetch_json(URL.format(key=api_key)))


def parse_odds(raw: list[dict]) -> list[dict]:
    """Median decimal price per outcome across bookmakers, then de-vigged probabilities."""
    out = []
    for e in raw:
        h, d, a = [], [], []
        for b in e.get("bookmakers", []):
            for m in b.get("markets", []):
                if m.get("key") != "h2h":
                    continue
                for o in m.get("outcomes", []):
                    (h if o["name"] == e["home_team"] else a if o["name"] == e["away_team"] else d).append(float(o["price"]))
        if not (h and d and a):
            continue
        hp, dp, ap = statistics.median(h), statistics.median(d), statistics.median(a)
        ph, pd_, pa = devig(hp, dp, ap)
        out.append({"home": e["home_team"], "away": e["away_team"], "commence": e["commence_time"],
                    "h_price": hp, "d_price": dp, "a_price": ap, "h": ph, "d": pd_, "a": pa})
    return out


def load_aliases(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return {norm_name(r["odds_name"]): norm_name(r["uefa_name"]) for r in csv.DictReader(path.open(encoding="utf-8"))}


def match_odds_to_fixtures(odds: list[dict], season: dict, aliases: dict[str, str] | None = None) -> dict[str, tuple[float, float, float]]:
    aliases = aliases or {}

    def n(s: str) -> str:
        k = norm_name(s)
        return aliases.get(k, k)

    t = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
    out = {}
    for o in odds:
        best, score = None, 0.0
        for f in season["fixtures"]:
            if f["status"] == "FINISHED" or abs(t(f["kickoff"]) - t(o["commence"])) > WINDOW:
                continue
            sh = _similarity(n(o["home"]), norm_name(season["clubs"][f["home"]]["name"]))
            sa = _similarity(n(o["away"]), norm_name(season["clubs"][f["away"]]["name"]))
            if min(sh, sa) >= 0.5 and sh + sa > score:
                best, score = f["id"], sh + sa
        if best:
            out[best] = (o["h"], o["d"], o["a"])
    return out
