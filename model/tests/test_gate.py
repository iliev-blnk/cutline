from datetime import datetime, timedelta, timezone

from cutline.gate import gate

NOW = datetime(2026, 10, 16, 5, 0, tzinfo=timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def season(md2_finished=18, md2_kickoff=NOW - timedelta(days=2), live=False, wed_unstarted=False):
    """MD1 finished long ago; MD2 at md2_kickoff (the first md2_finished of its 18 finished); MD3 next week."""
    fx = []
    for i in range(18):
        fx.append({"id": f"a{i}", "md": 1, "kickoff": iso(NOW - timedelta(days=30)), "status": "FINISHED"})
    for i in range(18):
        ko = md2_kickoff
        if wed_unstarted and i >= 9:
            ko = NOW + timedelta(hours=12)
        status = "FINISHED" if i < md2_finished else ("UPCOMING" if ko > NOW else "OTHER")
        if live and i == 17:
            status = "LIVE"
        fx.append({"id": f"b{i}", "md": 2, "kickoff": iso(ko), "status": status})
    for i in range(18):
        fx.append({"id": f"c{i}", "md": 3, "kickoff": iso(NOW + timedelta(days=5)), "status": "UPCOMING"})
    return {"seasonYear": 2027, "fixtures": fx}


def finished(s):
    return [f["id"] for f in s["fixtures"] if f["status"] == "FINISHED"]


def test_unchanged_results_skips():
    s = season()
    d = gate(s, {"finished": finished(s)}, NOW)
    assert not d.ok and d.reason == "unchanged"


def test_live_match_blocks():
    d = gate(season(md2_finished=17, live=True, md2_kickoff=NOW - timedelta(hours=1)), None, NOW)
    assert not d.ok and d.reason == "live"


def test_partial_matchday_blocks():
    d = gate(season(md2_finished=9, md2_kickoff=NOW - timedelta(hours=10)), None, NOW)
    assert not d.ok and d.reason == "matchday in progress"


def test_half_played_matchday_with_unstarted_rest_blocks():
    d = gate(season(md2_finished=9, md2_kickoff=NOW - timedelta(hours=10), wed_unstarted=True), None, NOW)
    assert not d.ok and d.reason == "matchday in progress"


def test_stale_unfinished_does_not_block():
    d = gate(season(md2_finished=17, md2_kickoff=NOW - timedelta(hours=72)), None, NOW)
    assert d.ok
    assert any("b17" in n for n in d.notes)


def test_before_md():
    d = gate(season(), {"finished": [f"a{i}" for i in range(18)]}, NOW)
    assert d.ok and d.before_md == 3


def test_list_snapshots_ignores_model_and_elo_files(tmp_path):
    from cutline.gate import list_snapshots

    for n in ("2026-10-12-before-MD2.json", "2026-10-12-before-MD2.model.json", "2026-10-19-before-MD3.elo.json",
              "2026-10-19-before-MD3.json", "notes.json"):
        (tmp_path / n).write_text("{}")
    assert [p.name for p in list_snapshots(tmp_path)] == ["2026-10-12-before-MD2.json", "2026-10-19-before-MD3.json"]


def test_blocked_decision_still_reports_next_matchday():
    s = season()
    d = gate(s, {"finished": finished(s)}, NOW)
    assert not d.ok and d.before_md == 3


def test_snapshot_stem_after_league_phase():
    from cutline.gate import snapshot_stem

    assert snapshot_stem(NOW, 3) == "2026-10-16-before-MD3"
    assert snapshot_stem(NOW, None) == "2026-10-16-knockouts"


def test_knockout_snapshot_is_listed_so_gate_sees_it(tmp_path):
    from cutline.gate import list_snapshots

    for n in ("2027-01-26-before-MD8.json", "2027-01-28-knockouts.json", "2027-01-28-knockouts.model.json"):
        (tmp_path / n).write_text("{}")
    assert [p.name for p in list_snapshots(tmp_path)][-1] == "2027-01-28-knockouts.json"
    assert len(list_snapshots(tmp_path)) == 2
