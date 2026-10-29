import unittest
from contextlib import redirect_stderr
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from app.database import DatabaseConnections
from app.main import main
from app.migration import (
    extract_legacy_snapshot,
    load_staging_batch,
    normalize_legacy_row,
    record_failed_batch,
    validate_target_for_migration,
)


class MappingTests(unittest.TestCase):
    def test_mixed_case_legacy_role_is_included(self):
        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def execute(self, query):
                self.query = query

            def fetchall(self):
                if "WHERE upper(btrim(t.nome)) = 'ADMINISTRADOR'" in self.query:
                    return [{"source_id": 1, "full_name": "Ana", "email": "ana@example.org",
                             "cpf": "12345678901", "status": "Ativo"}]
                if "GROUP BY t.nome" in self.query:
                    return [{"nome": "Administrador", "total": 1}]
                return []

        class Source:
            def cursor(self, **_):
                return Cursor()

        records, user_types, _ = extract_legacy_snapshot(Source())
        self.assertEqual(len(records["administrator"]), 1)
        self.assertEqual(user_types, {"ADMINISTRADOR": 1})

    def test_empty_legacy_snapshot_is_rejected(self):
        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def execute(self, *_):
                pass

            def fetchall(self):
                return []

        class Source:
            def cursor(self, **_):
                return Cursor()

        with self.assertRaisesRegex(ValueError, "no records"):
            extract_legacy_snapshot(Source())

    def test_manager_with_unknown_unit_is_left_for_procedure(self):
        manager = {
            "source_id": 1, "full_name": "Carlos Menezes", "email": "carlos@example.org",
            "cpf": "12345678901", "password_hash": "$2b$10$" + "a" * 53,
            "company_unit_source_id": 1, "registered_by_source_id": None,
            "status": "Ativo",
        }

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def execute(self, query):
                self.query = query

            def fetchall(self):
                if "= 'ADMINISTRADOR'" in self.query or "FROM empresa e" in self.query or "FROM filial f" in self.query:
                    return []
                if "= 'GERENTE'" in self.query:
                    return [manager]
                if "GROUP BY t.nome" in self.query:
                    return [{"nome": "GERENTE", "total": 1}]
                if "SELECT 'contrato' AS name" in self.query:
                    return [{"name": "contrato", "total": 0}, {"name": "inversor", "total": 0},
                            {"name": "string", "total": 0}, {"name": "painel", "total": 0},
                            {"name": "manutencao", "total": 0}]
                return []

        class Source:
            def cursor(self, **_):
                return Cursor()

        records, _, _ = extract_legacy_snapshot(Source())
        self.assertEqual(len(records["manager"]), 1)
        self.assertEqual(records["manager"][0]["company_unit_source_id"], 1)

    def test_manager_is_normalized_without_rehashing_password(self):
        password = "$2b$10$" + "a" * 53
        row = normalize_legacy_row("manager", {
            "source_id": 7, "full_name": "Ana", "email": " ANA@EXAMPLE.ORG ",
            "cpf": "123.456.789-01", "password_hash": password,
            "company_unit_source_id": 3, "registered_by_source_id": 1,
            "status": "Inativo",
        })
        self.assertEqual(row["email"], "ana@example.org")
        self.assertEqual(row["cpf"], "12345678901")
        self.assertEqual(row["password_hash"], password)
        self.assertEqual(row["user_type"], "GERENTE")
        self.assertFalse(row["is_active"])

    def test_manager_without_legacy_registrar_is_not_rejected_by_rpa(self):
        row = normalize_legacy_row("manager", {
            "source_id": 7, "full_name": "Carlos", "email": "carlos@example.org",
            "cpf": "12345678901", "password_hash": "$2b$10$" + "a" * 53,
            "company_unit_source_id": 3, "registered_by_source_id": None,
            "status": "Ativo",
        })
        self.assertIsNone(row["registered_by_source_id"])

    def test_unit_flattens_legacy_address_for_normalized_destination(self):
        row = normalize_legacy_row("company_unit", {
            "source_id": 3, "company_source_id": 2, "segment_source_id": 1,
            "segment_name": "Indústria", "name": "Usina", "cnpj": "11.222.333/0001-44",
            "email": "USINA@EXAMPLE.ORG", "phone": "11 99999-0000",
            "street_name": "Rua A", "number": "4", "additional_info": None,
            "neighborhood": "Centro", "city": "São Paulo", "state": "sp",
            "zip_code": "01234-567", "registered_by_source_id": 1,
            "status": "Cancelado",
        })
        self.assertEqual((row["cnpj"], row["zip_code"], row["state"]),
                         ("11222333000144", "01234567", "SP"))
        self.assertFalse(row["is_active"])

    def test_plaintext_hash_field_is_preserved_for_destination_validation(self):
        row = normalize_legacy_row("manager", {
            "source_id": 7, "full_name": "Ana", "email": "ana@example.org",
            "cpf": "12345678901", "password_hash": "senha123",
            "company_unit_source_id": 3, "registered_by_source_id": 1,
            "status": "Ativo",
        })
        self.assertEqual(row["password_hash"], "senha123")

    def test_bad_document_is_rejected_before_writing(self):
        with self.assertRaisesRegex(ValueError, "cnpj"):
            normalize_legacy_row("company", {
                "source_id": 2, "name": "Example", "cnpj": "123",
                "contact_email": "x@example.org", "description": None,
                "registered_by_source_id": 1, "status": "ATIVO",
            })


class PreflightTests(unittest.TestCase):
    def test_preflight_checks_destination_schema_procedure_and_role(self):
        queries = []

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def execute(self, query, *_):
                self.query = query
                queries.append(query)

            def fetchone(self):
                if "column_default" in self.query:
                    return (True,)
                if "pg_try_advisory" in self.query:
                    return (True,)
                if "to_regprocedure" in self.query:
                    return ("staging.pr_sync_legacy(bigint)",)
                return (1,)

            def fetchall(self):
                return []

        class Target:
            def cursor(self):
                return Cursor()

        validate_target_for_migration(Target())
        self.assertEqual(len(queries), 5)
        self.assertTrue(any("information_schema.columns" in query for query in queries))
        self.assertTrue(any("is_first_access" in query for query in queries))
        self.assertTrue(any("to_regprocedure" in query for query in queries))

    def test_preflight_stops_before_lock_when_target_column_is_missing(self):
        queries = []

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def execute(self, query, *_):
                self.query = query
                queries.append(query)

            def fetchall(self):
                return [("public.employee.is_first_access",)]

        class Target:
            def cursor(self):
                return Cursor()

        with self.assertRaisesRegex(ValueError, "public.employee.is_first_access"):
            validate_target_for_migration(Target())
        self.assertEqual(len(queries), 1)
        self.assertNotIn("pg_try_advisory_xact_lock", queries[0])

    def test_preflight_rejects_first_access_default_other_than_true(self):
        queries = []

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def execute(self, query, *_):
                self.query = query
                queries.append(query)

            def fetchall(self):
                return []

            def fetchone(self):
                return (False,)

        class Target:
            def cursor(self):
                return Cursor()

        with self.assertRaisesRegex(ValueError, "is_first_access DEFAULT true"):
            validate_target_for_migration(Target())
        self.assertEqual(len(queries), 2)
        self.assertNotIn("pg_try_advisory_xact_lock", queries[-1])


class AuditTests(unittest.TestCase):
    def test_load_clears_error_payload_before_returning_batch(self):
        executed = []

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def execute(self, query, params=None):
                executed.append((query, params))

            def executemany(self, *_):
                pass

            def fetchone(self):
                return (17,) if len(executed) == 1 else ("FAILED", 1, 0, 1)

        class Target:
            def cursor(self):
                return Cursor()

        result = load_staging_batch(Target(), {
            "administrator": [], "company": [], "company_unit": [], "manager": [],
        })
        self.assertEqual(result, (17, "FAILED", 1, 0, 1))
        self.assertIn("CALL staging.pr_sync_legacy", executed[1][0])
        self.assertIn("SET source_payload = NULL", executed[2][0])
        self.assertEqual(executed[2][1], (17,))

    def test_empty_snapshot_fails_check_and_normal_run_before_staging(self):
        class Connections:
            def __enter__(self):
                return SimpleNamespace(source=object(), target=object())

            def __exit__(self, *_):
                pass

        with patch.dict("os.environ", {
            "LEGACY_DATABASE_URL": "legacy", "TARGET_DATABASE_URL": "target"
        }), patch("app.main.load_dotenv"), patch(
            "app.main.DatabaseConnections", return_value=Connections()
        ), patch(
            "app.main.extract_legacy_snapshot",
            side_effect=ValueError("legacy snapshot has no records in the migration contract"),
        ), patch("app.main.load_staging_batch") as load, patch(
            "app.main.record_failed_batch", return_value=42
        ) as record, redirect_stderr(StringIO()):
            self.assertEqual(main(["--check"]), 1)
            record.assert_not_called()
            self.assertEqual(main([]), 1)
            record.assert_called_once()
            load.assert_not_called()

    def test_validation_failure_creates_failed_batch_without_source_payload(self):
        executed = []

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def execute(self, query, params=None):
                executed.append((query, params))

            def fetchone(self):
                return (42,)

        class Target:
            def cursor(self):
                return Cursor()

        batch_id = record_failed_batch(Target(), ValueError("company:7 has invalid cnpj"))
        self.assertEqual(batch_id, 42)
        self.assertIn("'FAILED'", executed[0][0])
        self.assertIn("1, 1", executed[0][0])
        self.assertEqual(executed[1][1], (42, "company:7", "company:7 has invalid cnpj"))
        self.assertNotIn("source_payload", executed[1][0])

    def test_normal_run_records_validation_error_but_check_does_not_write(self):
        class Connections:
            def __enter__(self):
                return SimpleNamespace(source=object(), target=object())

            def __exit__(self, *_):
                pass

        with patch.dict("os.environ", {
            "LEGACY_DATABASE_URL": "legacy", "TARGET_DATABASE_URL": "target"
        }), patch("app.main.load_dotenv"), patch(
            "app.main.DatabaseConnections", return_value=Connections()
        ), patch(
            "app.main.extract_legacy_snapshot", side_effect=ValueError("company:7 has invalid cnpj")
        ), patch("app.main.record_failed_batch", return_value=42) as record, redirect_stderr(StringIO()):
            self.assertEqual(main([]), 1)
            record.assert_called_once()
            record.reset_mock()
            self.assertEqual(main(["--check"]), 1)
            record.assert_not_called()


class DatabaseConnectionTests(unittest.TestCase):
    def test_source_is_read_only_and_both_connections_close_on_error(self):
        events = []

        class Connection:
            def __init__(self, name):
                self.name = name

            def __enter__(self):
                events.append((self.name, "open"))
                return self

            def __exit__(self, exc_type, *_):
                events.append((self.name, "rollback" if exc_type else "commit"))

            def execute(self, sql):
                events.append((self.name, sql))

        with patch("app.database.psycopg.connect", side_effect=lambda url: Connection(url)):
            with self.assertRaisesRegex(ValueError, "stop"):
                with DatabaseConnections("legacy", "target") as databases:
                    self.assertEqual(databases.source.name, "legacy")
                    self.assertEqual(databases.target.name, "target")
                    raise ValueError("stop")

        self.assertEqual(events, [
            ("legacy", "open"),
            ("legacy", "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"),
            ("target", "open"),
            ("target", "rollback"),
            ("legacy", "rollback"),
        ])


if __name__ == "__main__":
    unittest.main()
