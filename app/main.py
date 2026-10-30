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
    find_records_missing_from_target,
    load_staging_batch,
    record_failed_batch,
    validate_target_for_migration,
)


def run_once(check=False):
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    legacy_dsn = os.getenv("LEGACY_DATABASE_URL")
    target_dsn = os.getenv("TARGET_DATABASE_URL")
    if not legacy_dsn or not target_dsn:
        print("LEGACY_DATABASE_URL and TARGET_DATABASE_URL must be set", file=sys.stderr)
        return 1
    try:
        with DatabaseConnections(legacy_dsn, target_dsn) as databases:
            try:
                records, user_types, outside_contract = extract_legacy_snapshot(databases.source)
                validate_target_for_migration(databases.target)
                missing_records = find_records_missing_from_target(databases.target, records)
            except ValueError as exc:
                print(f"Migration stopped: {exc}", file=sys.stderr)
                if not check:
                    batch_id = record_failed_batch(databases.target, exc)
                    print(f"Validation failure recorded in batch {batch_id}", file=sys.stderr)
                return 1
            counts = ", ".join(f"{key}={len(rows)}" for key, rows in records.items())
            excluded = sum(count for name, count in user_types.items() if name not in ("ADMINISTRADOR", "GERENTE"))
            print(f"Legacy snapshot: {counts}; other user roles excluded={excluded}")
            print("Outside destination RPA contract: " + ", ".join(
                f"{name}={count}" for name, count in outside_contract.items()
            ))
            new_counts = ", ".join(f"{key}={len(rows)}" for key, rows in missing_records.items())
            print(f"New records missing from destination: {new_counts}")
            if check:
                return 0
            if not any(missing_records.values()):
                print("No new records to migrate; skipping batch.")
                return 0
            batch_id, status, total, processed, failed = load_staging_batch(databases.target, missing_records)
        print(f"Batch {batch_id}: {status}; total={total}, processed={processed}, failed={failed}")
        if failed:
            print(f"Inspect staging.rpa_load_error for batch {batch_id}", file=sys.stderr)
            return 2
        return 0
    except (ValueError, psycopg.Error) as exc:
        print(f"Migration stopped: {exc}", file=sys.stderr)
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Migrate new Apollo registration data")
    parser.add_argument("--check", action="store_true", help="validate and count without writing")
    args = parser.parse_args(argv)
    return run_once(check=args.check)
