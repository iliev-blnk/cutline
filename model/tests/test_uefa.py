import copy
import json
from pathlib import Path

import pytest

from cutline.schema import SchemaError
from cutline.uefa import normalize_uefa

SAMPLE = json.loads((Path(__file__).parent / "fixtures" / "uefa_sample.json").read_text())
FINISHED, UPCOMING, FINAL = SAMPLE


def test_normalize_finished():
    (m,) = normalize_uefa([FINISHED], "UCL")
    assert m.status == "FINISHED"
    assert (m.home_goals, m.away_goals) == (2, 3)
    assert m.stage == "GROUP_STANDINGS"
    assert m.matchday == 1
    assert m.home_country == "BEL"
    assert m.competition == "UCL"
    assert m.season == 2027
    assert m.date == "2026-09-08"


def test_normalize_upcoming():
    (m,) = normalize_uefa([UPCOMING], "UCL")
    assert m.status == "UPCOMING"
    assert m.home_goals is None and m.away_goals is None


def test_final_is_neutral():
    ms = normalize_uefa([FINISHED, UPCOMING, FINAL], "UCL")
    assert [m.neutral for m in ms] == [False, False, True]
    # 90-minute score, not the penalty shoot-out
    assert (ms[2].home_goals, ms[2].away_goals) == (1, 1)


def test_missing_field_raises():
    broken = copy.deepcopy(FINISHED)
    del broken["kickOffTime"]
    with pytest.raises(SchemaError) as e:
        normalize_uefa([broken], "UCL")
    assert e.value.field == "kickOffTime"


def test_ids_are_uefa_ids():
    (m,) = normalize_uefa([FINISHED], "UCL")
    assert m.home_id == "50043"
    assert m.away_id == "52683"


def test_kickoff_falls_back_to_date_for_cancelled():
    rec = copy.deepcopy(UPCOMING)
    rec["status"] = "CANCELED"
    rec["kickOffTime"] = {"date": "2022-03-17"}
    (m,) = normalize_uefa([rec], "UEL")
    assert m.kickoff_utc == "2022-03-17T00:00:00Z"
    assert m.status == "OTHER"
