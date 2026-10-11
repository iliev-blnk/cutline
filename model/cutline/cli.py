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


def cmd_snapshot(args: argparse.Namespace) -> int:
    import json
    import os
    import subprocess
    from datetime import datetime, timezone
    from pathlib import Path

    from .elo import elo_model_json
    from .fit import DEFAULT, TUNED, fit
    from .gate import gate, list_snapshots, snapshot_stem
    from .matches import CURRENT, DATA, load_matches

    root = DATA.parent
    pred = root / "predictions" / str(CURRENT)
    pred.mkdir(parents=True, exist_ok=True)
    season_path = DATA / f"season-{CURRENT}.json"
    season = json.loads(season_path.read_text())
    snaps = list_snapshots(pred)
    last = json.loads(snaps[-1].read_text()) if snaps else None
    now = datetime.now(timezone.utc)
    d = gate(season, last, now)
    if not d.ok and not args.force:
        print(f"skip: {d.reason}")
        return 0
    hyper = TUNED or DEFAULT
    df = load_matches()
    model = fit(df, now, hyper)
    stem = snapshot_stem(now, d.before_md)
    model_path = pred / f"{stem}.model.json"
    out_path = pred / f"{stem}.json"
    model_path.write_text(json.dumps(model.to_json(), indent=1, ensure_ascii=False))
    elo_path = pred / f"{stem}.elo.json"
    elo_path.write_text(json.dumps(elo_model_json(df, now, season["clubs"]), indent=1, ensure_ascii=False))
    cmd = ["pnpm", "--dir", str(root / "sim"), "exec", "tsx", "src/cli.ts", "snapshot",
           "--model", str(model_path), "--season", str(season_path), "--seed", f"{now:%Y%m%d}",
           "--n", str(args.n), "--out", str(out_path), "--elo-model", str(elo_path)]
    if TUNED is None:
        cmd += ["--untuned", "--note", "default hyperparameters, not yet tuned"]
    for n in d.notes + (["forced: " + d.reason] if not d.ok else []):
        cmd += ["--note", n]
    subprocess.run(cmd, check=True)
    print(f"created {out_path.relative_to(root)}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"created={out_path.relative_to(root)}\n")
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    import os

    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(v, "1")
    from . import backtest
    from .fit import TUNED

    if args.stage == "tune":
        best = backtest.tune(args.processes)
        print(f"best: {best} (research/tune.csv)")
        return 0
    if TUNED is None:
        print("refusing to test: pin TUNED in cutline/fit.py first")
        return 1
    out = backtest.test(TUNED, args.processes)
    print(f"test written: research/test.json ({out['match_level']['ucl']['n']} UCL matches)")
    return 0


def cmd_odds(args: argparse.Namespace) -> int:
    import json
    import os

    from .gate import list_snapshots
    from .matches import CURRENT, DATA
    from .odds import fetch_odds, load_aliases, match_odds_to_fixtures

    key = os.environ.get("ODDS_API_KEY", "")
    if not key:
        print("skip: no ODDS_API_KEY")
        return 0
    pred = DATA.parent / "predictions" / str(CURRENT)
    snap_path = list_snapshots(pred)[-1]
    snap = json.loads(snap_path.read_text())
    season = json.loads((DATA / f"season-{CURRENT}.json").read_text())
    got = match_odds_to_fixtures(fetch_odds(key), season, load_aliases(DATA / "odds_aliases.csv"))
    want = [f["id"] for f in season["fixtures"] if f["md"] == snap["beforeMd"]]
    odds = {i: got[i] for i in want if i in got}
    (pred / "odds").mkdir(exist_ok=True)
    out = pred / "odds" / snap_path.name
    out.write_text(json.dumps({"snapshot": snap_path.name, "fetched": len(got), "fixtures": odds}, indent=1))
    print(f"odds: {len(odds)}/{len(want)} MD{snap['beforeMd']} fixtures matched -> {out.relative_to(DATA.parent)}")
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
    sn = sub.add_parser("snapshot", help="gate, fit and simulate; write predictions/<Y>/<date>-before-MD<n>.json")
    sn.add_argument("--force", action="store_true")
    sn.add_argument("--n", type=int, default=10000)
    b = sub.add_parser("backtest", help="tune on 2023-24, or test once on 2024-25 + 2025-26")
    b.add_argument("stage", choices=["tune", "test"])
    b.add_argument("--processes", type=int, default=8)
    sub.add_parser("odds", help="store market odds for the latest snapshot's matchday (needs ODDS_API_KEY)")
    args = p.parse_args(argv)
    return {"odds": cmd_odds, "backtest": cmd_backtest, "ingest": cmd_ingest, "fit": cmd_fit, "export-fixtures": cmd_export_fixtures,
            "snapshot": cmd_snapshot}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
