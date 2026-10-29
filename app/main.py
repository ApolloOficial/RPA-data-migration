"""Ponto de entrada para validar ou executar a migração Apollo."""

import argparse
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from .database import DatabaseConnections
from .migration import (
    extract_legacy_snapshot,
    load_staging_batch,
    record_failed_batch,
    validate_target_for_migration,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Migrate legacy Apollo registration data")
    parser.add_argument("--check", action="store_true", help="validate and count without writing")
    args = parser.parse_args(argv)
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    legacy_dsn = os.getenv("LEGACY_DATABASE_URL")
    target_dsn = os.getenv("TARGET_DATABASE_URL")
    if not legacy_dsn or not target_dsn:
        parser.error("LEGACY_DATABASE_URL and TARGET_DATABASE_URL must be set")
    try:
        with DatabaseConnections(legacy_dsn, target_dsn) as databases:
            try:
                records, user_types, outside_contract = extract_legacy_snapshot(databases.source)
                validate_target_for_migration(databases.target)
            except ValueError as exc:
                print(f"Migration stopped: {exc}", file=sys.stderr)
                if not args.check:
                    batch_id = record_failed_batch(databases.target, exc)
                    print(f"Validation failure recorded in batch {batch_id}", file=sys.stderr)
                return 1
            counts = ", ".join(f"{key}={len(rows)}" for key, rows in records.items())
            excluded = sum(count for name, count in user_types.items() if name not in ("ADMINISTRADOR", "GERENTE"))
            print(f"Legacy snapshot: {counts}; other user roles excluded={excluded}")
            print("Outside destination RPA contract: " + ", ".join(
                f"{name}={count}" for name, count in outside_contract.items()
            ))
            if args.check:
                return 0
            batch_id, status, total, processed, failed = load_staging_batch(databases.target, records)
        print(f"Batch {batch_id}: {status}; total={total}, processed={processed}, failed={failed}")
        if failed:
            print(f"Inspect staging.rpa_load_error for batch {batch_id}", file=sys.stderr)
            return 2
        return 0
    except (ValueError, psycopg.Error) as exc:
        print(f"Migration stopped: {exc}", file=sys.stderr)
        return 1
