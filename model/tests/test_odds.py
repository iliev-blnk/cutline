import json
import math
from pathlib import Path

from cutline.odds import match_odds_to_fixtures, parse_odds

FIX = Path(__file__).parent / "fixtures"
SEASON = {
    "clubs": {"1": {"name": "Lens"}, "2": {"name": "Sporting CP"}, "3": {"name": "Arsenal"}, "4": {"name": "Lille"}},
    "fixtures": [
        {"id": "f1", "md": 2, "home": "1", "away": "2", "kickoff": "2026-10-13T16:45:00Z", "status": "UPCOMING"},
        {"id": "f2", "md": 2, "home": "3", "away": "4", "kickoff": "2026-10-13T19:00:00Z", "status": "UPCOMING"},
    ],
}


def test_saved_response_maps_to_fixtures():
    odds = parse_odds(json.loads((FIX / "odds_sample.json").read_text()))
    got = match_odds_to_fixtures(odds, SEASON, aliases={"sporting lisbon": "sporting cp"})
    assert set(got) == {"f1", "f2"}
    for h, d, a in got.values():
        assert math.isclose(h + d + a, 1.0)
    assert got["f2"][0] > 0.7


def test_median_across_bookmakers():
    odds = parse_odds(json.loads((FIX / "odds_sample.json").read_text()))
    e1 = next(o for o in odds if o["home"] == "RC Lens")
    assert math.isclose(e1["h_price"], 2.55)
