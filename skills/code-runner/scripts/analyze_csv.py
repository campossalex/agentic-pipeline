"""Summarize a CSV with the standard library only.

Usage: python analyze_csv.py data.csv [--group-by COLUMN] [--metric COLUMN]
Prints row count, numeric column stats, and optional grouped totals as Markdown.
"""
import argparse
import csv
import statistics
from collections import defaultdict


def as_float(value: str):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--group-by")
    parser.add_argument("--metric")
    args = parser.parse_args()

    with open(args.path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        print("No rows.")
        return
    columns = list(rows[0].keys())
    print(f"## {args.path}\n\nRows: {len(rows)}  \nColumns: {', '.join(columns)}\n")

    print("| column | min | max | mean | sum |\n|---|---|---|---|---|")
    for col in columns:
        values = [v for v in (as_float(r[col]) for r in rows) if v is not None]
        if len(values) == len(rows):
            print(f"| {col} | {min(values):,.2f} | {max(values):,.2f} | "
                  f"{statistics.mean(values):,.2f} | {sum(values):,.2f} |")

    if args.group_by and args.metric:
        totals: dict[str, float] = defaultdict(float)
        for r in rows:
            totals[r[args.group_by]] += as_float(r[args.metric]) or 0.0
        grand = sum(totals.values()) or 1.0
        print(f"\n### {args.metric} by {args.group_by}\n\n| {args.group_by} | {args.metric} | share |\n|---|---|---|")
        for key, total in sorted(totals.items(), key=lambda kv: -kv[1]):
            print(f"| {key} | {total:,.2f} | {total / grand:.1%} |")


if __name__ == "__main__":
    main()
