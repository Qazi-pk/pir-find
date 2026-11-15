"""Command line: pir-find data.csv --target y [--json] [--check "formula"] [--describe]"""
import argparse
import json
import sys

from . import __version__
from .core import check_formula, describe_table, find_formula, load_table


def _text(r):
    if "law_found" in r:
        head = f"{r['target']} = {r['formula']}" if r["law_found"] else \
            f"No simple law found. Fallback model: {r['target']} = {r['fallback_model']}"
        lines = [head, f"found by: {r['found_by']}", f"R2 on held-out rows: {r['r2_heldout_rows']:.4f}",
                 f"rows used: {r['rows_used']}  (dropped: {r['rows_dropped_missing']})   "
                 f"time: {r['fit_seconds']} s   PIR {r['pir_engine']}"]
        lines += [f"warning: {w}" for w in r["warnings"]] + ["", r["note"]]
        return "\n".join(lines)
    if "r2" in r:
        lines = [f"formula: {r['formula']}", f"rows checked: {r['rows_checked']}  undefined: {r['rows_undefined']}",
                 f"R2: {r['r2']}   max abs error: {r['max_abs_error']}"]
        lines += [f"warning: {w}" for w in r["warnings"]] + ["", r["note"]]
        return "\n".join(lines)
    lines = [f"rows: {r['rows']}  complete numeric rows: {r['complete_numeric_rows']}"]
    lines += [f"  {c['name']}: " + (f"{c['min']:.6g} .. {c['max']:.6g}" if c["numeric"] else "not numeric")
              for c in r["columns"]]
    lines += [f"problem: {p}" for p in r["problems"]]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pir-find", description="Find a closed-form formula in a CSV with PIR.")
    ap.add_argument("csv")
    ap.add_argument("--target", help="column to explain (every other column is an input)")
    ap.add_argument("--describe", action="store_true", help="describe the table and stop")
    ap.add_argument("--check", metavar="FORMULA", help="evaluate a candidate formula instead of fitting")
    ap.add_argument("--timeout", type=int, default=300, help="seconds before giving up (default 300)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--version", action="version", version=f"pir-find {__version__}")
    a = ap.parse_args(argv)
    try:
        df = load_table(a.csv)
        if a.describe:
            r = describe_table(df)
        else:
            if not a.target:
                ap.error("--target is required (use --describe to list the columns)")
            r = check_formula(df, a.target, a.check) if a.check else find_formula(df, a.target, a.seed, a.timeout)
    except (ValueError, TimeoutError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps(r, indent=2) if a.json else _text(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
