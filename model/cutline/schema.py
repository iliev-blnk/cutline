from __future__ import annotations

from dataclasses import asdict, dataclass, fields


class SchemaError(Exception):
    """A field the ingest relies on is missing from a source record."""

    def __init__(self, field: str, context: str = ""):
        super().__init__(f"missing field {field!r}" + (f" in {context}" if context else ""))
        self.field = field


@dataclass
class Match:
    match_id: str
    date: str  # YYYY-MM-DD (UTC)
    kickoff_utc: str  # ISO 8601, Z
    competition: str  # UCL | UEL | UECL | football-data division (E0, SP1, AUT, ...)
    season: int  # UEFA seasonYear convention: 2027 = 2026-27
    stage: str  # UEFA round type, or LEAGUE for domestic matches
    matchday: int | None
    home_id: str
    away_id: str
    home_name: str
    away_name: str
    home_country: str
    away_country: str
    status: str  # FINISHED | UPCOMING | LIVE | OTHER
    home_goals: int | None
    away_goals: int | None
    neutral: bool
    home_xg: float | None = None
    away_xg: float | None = None
    odds_h: float | None = None
    odds_d: float | None = None
    odds_a: float | None = None

    def row(self) -> dict:
        return asdict(self)


MATCH_COLUMNS = [f.name for f in fields(Match)]
