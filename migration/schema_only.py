"""Derive an empty operational destination from the immutable supplied SQL."""

import argparse
import sys
from pathlib import Path


MARKER = "INSERT INTO staging.rpa_load_batch"


def schema_only(sql):
    if sql.count(MARKER) != 1 or not sql.lstrip().startswith("BEGIN;"):
        raise ValueError("the supplied destination SQL has an unexpected layout")
    head = sql.split(MARKER, 1)[0]
    if "CREATE OR REPLACE PROCEDURE staging.pr_sync_legacy" not in head:
        raise ValueError("destination SQL is missing the RPA synchronization procedure")
    return head.rstrip() + "\nCOMMIT;\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Print schema and reference rows without the demo load")
    parser.add_argument("sql_file", type=Path)
    parser.add_argument("output_file", type=Path)
    args = parser.parse_args(argv)
    try:
        output = schema_only(args.sql_file.read_text(encoding="utf-8-sig"))
        args.output_file.write_text(output, encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Cannot derive destination schema: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
