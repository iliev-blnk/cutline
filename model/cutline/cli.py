from __future__ import annotations

import argparse
import sys


def cmd_ingest(args: argparse.Namespace) -> int:
    from .matches import build_matches

    df = build_matches()
    fin = (df["status"] == "FINISHED").sum()
    print(f"matches: {len(df)} rows, {fin} finished")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="cutline")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ingest", help="download sources, write data/matches.csv.gz and data/season-<Y>.json")
    args = p.parse_args(argv)
    return {"ingest": cmd_ingest}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
