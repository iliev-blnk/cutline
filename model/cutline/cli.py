from __future__ import annotations

import argparse
import sys


def cmd_ingest(args: argparse.Namespace) -> int:
    from .matches import build_matches

    df = build_matches()
    fin = (df["status"] == "FINISHED").sum()
    print(f"matches: {len(df)} rows, {fin} finished")
    return 0


def cmd_fit(args: argparse.Namespace) -> int:
    import json
    from datetime import datetime, timezone

    from .fit import Hyper, fit
    from .matches import load_matches

    cutoff = datetime.now(timezone.utc) if args.cutoff == "now" else datetime.fromisoformat(args.cutoff.replace("Z", "+00:00"))
    hyper = Hyper(args.half_life, args.lambda_team, args.lambda_country, args.xg_blend)
    m = fit(load_matches(), cutoff, hyper)
    out = m.to_json()
    with open(args.out, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"fit: {out['n_matches']} matches, rho={out['rho']:.3f}, h_eur={out['h_eur']:.3f}, h_dom={out['h_dom']:.3f} -> {args.out}")
    return 0


def cmd_export_fixtures(args: argparse.Namespace) -> int:
    import json
    from pathlib import Path

    from .matches import season_json
    from .uefa import normalize_uefa, uefa_matches, uefa_standings

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for year in (2025, 2026):
        season = season_json(normalize_uefa(uefa_matches(1, year), "UCL"), year)
        season["official"] = [str(i["team"]["id"]) for i in sorted(uefa_standings(year), key=lambda i: i["rank"])]
        (out_dir / f"ucl-{year}.json").write_text(json.dumps(season, indent=1, ensure_ascii=False))
        print(f"ucl-{year}.json: {len(season['fixtures'])} fixtures")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="cutline")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ingest", help="download sources, write data/matches.csv.gz and data/season-<Y>.json")
    f = sub.add_parser("fit", help="fit the goals model on matches before --cutoff")
    f.add_argument("--cutoff", default="now", help="ISO time (UTC) or 'now'")
    f.add_argument("--out", required=True)
    f.add_argument("--half-life", type=float, default=365.0)
    f.add_argument("--lambda-team", type=float, default=1.0)
    f.add_argument("--lambda-country", type=float, default=0.1)
    f.add_argument("--xg-blend", type=float, default=0.0)
    e = sub.add_parser("export-fixtures", help="write past league phases + official tables for the sim tests")
    e.add_argument("--out-dir", default="sim/test/fixtures")
    args = p.parse_args(argv)
    return {"ingest": cmd_ingest, "fit": cmd_fit, "export-fixtures": cmd_export_fixtures}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
