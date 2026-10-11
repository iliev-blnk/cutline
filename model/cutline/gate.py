"""Decide whether a new snapshot may be taken: only between matchdays, and only when results changed."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

STALE_AFTER = timedelta(hours=48)


@dataclass
class GateDecision:
    ok: bool
    reason: str
    before_md: int | None = None
    notes: list[str] = field(default_factory=list)


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def gate(season: dict, last_snapshot: dict | None, now: datetime) -> GateDecision:
    fx = season["fixtures"]
    started = [f for f in fx if _t(f["kickoff"]) <= now]
    stale = [f for f in started if f["status"] != "FINISHED" and now - _t(f["kickoff"]) > STALE_AFTER]
    stale_ids = {f["id"] for f in stale}
    upcoming = [f["md"] for f in fx if f["status"] != "FINISHED" and f["id"] not in stale_ids]
    before_md = min(upcoming) if upcoming else None
    notes = [f"match {f['id']} (MD{f['md']}, kickoff {f['kickoff']}) not finished after 48 h; simulated as unplayed"
             for f in stale]
    if any(f["status"] == "LIVE" for f in fx):
        return GateDecision(False, "live", before_md, notes)
    if started:
        latest = max(f["md"] for f in started)
        pending = [f for f in fx if f["md"] == latest and f["status"] != "FINISHED" and f["id"] not in stale_ids]
        if pending:
            return GateDecision(False, "matchday in progress", before_md, notes)
    finished = {f["id"] for f in fx if f["status"] == "FINISHED"}
    if last_snapshot is not None and set(last_snapshot.get("finished", [])) == finished:
        return GateDecision(False, "unchanged", before_md, notes)
    return GateDecision(True, "ok", before_md, notes)


def list_snapshots(pred_dir) -> list:
    """Snapshot files in name (= date) order, without their .model.json / .elo.json companions."""
    import re
    from pathlib import Path

    return sorted(p for p in Path(pred_dir).glob("*.json") if re.fullmatch(r"\d{4}-\d{2}-\d{2}-before-MD\d+\.json", p.name))
