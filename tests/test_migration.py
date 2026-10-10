import unittest
from unittest.mock import patch

from migration.database import DatabaseConnections
from migration.run import preflight, transform
from migration.schema_only import schema_only


class MappingTests(unittest.TestCase):
    def test_manager_is_normalized_without_rehashing_password(self):
        password = "$2b$10$" + "a" * 53
        row = transform("manager", {
            "source_id": 7, "full_name": "Ana", "email": " ANA@EXAMPLE.ORG ",
            "cpf": "123.456.789-01", "password_hash": password,
            "company_unit_source_id": 3, "registered_by_source_id": 1,
            "status": "INATIVO",
        })
        self.assertEqual(row["email"], "ana@example.org")
        self.assertEqual(row["cpf"], "12345678901")
        self.assertEqual(row["password_hash"], password)
        self.assertEqual(row["user_type"], "GERENTE")
        self.assertFalse(row["is_active"])

    def test_unit_flattens_legacy_address_for_normalized_destination(self):
        row = transform("company_unit", {
            "source_id": 3, "company_source_id": 2, "segment_source_id": 1,
            "segment_name": "Indústria", "name": "Usina", "cnpj": "11.222.333/0001-44",
            "email": "USINA@EXAMPLE.ORG", "phone": "11 99999-0000",
            "street_name": "Rua A", "number": "4", "additional_info": None,
            "neighborhood": "Centro", "city": "São Paulo", "state": "sp",
            "zip_code": "01234-567", "registered_by_source_id": 1,
            "status": "CANCELADO",
        })
        self.assertEqual((row["cnpj"], row["zip_code"], row["state"]),
                         ("11222333000144", "01234567", "SP"))
        self.assertFalse(row["is_active"])

    def test_plaintext_hash_field_is_preserved_for_destination_validation(self):
        row = transform("manager", {
            "source_id": 7, "full_name": "Ana", "email": "ana@example.org",
            "cpf": "12345678901", "password_hash": "senha123",
            "company_unit_source_id": 3, "registered_by_source_id": 1,
            "status": "ATIVO",
        })
        self.assertEqual(row["password_hash"], "senha123")

    def test_bad_document_is_rejected_before_writing(self):
        with self.assertRaisesRegex(ValueError, "cnpj"):
            transform("company", {
                "source_id": 2, "name": "Example", "cnpj": "123",
                "contact_email": "x@example.org", "description": None,
                "registered_by_source_id": 1, "status": "ATIVO",
            })


class DestinationSetupTests(unittest.TestCase):
    def test_derivation_keeps_procedure_and_omits_demo_load(self):
        sql = "BEGIN;\nCREATE OR REPLACE PROCEDURE staging.pr_sync_legacy(x bigint)\n" \
              "AS $$ BEGIN END $$ LANGUAGE plpgsql;\n" \
              "INSERT INTO staging.rpa_load_batch VALUES (1);\nCOMMIT;"
        result = schema_only(sql)
        self.assertIn("PROCEDURE staging.pr_sync_legacy", result)
        self.assertNotIn("INSERT INTO staging.rpa_load_batch", result)
        self.assertTrue(result.endswith("COMMIT;\n"))

    def test_changed_layout_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unexpected layout"):
            schema_only("BEGIN; CREATE TABLE x (id int); COMMIT;")


class PreflightTests(unittest.TestCase):
    def test_existing_source_id_with_different_identity_is_rejected(self):
        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def execute(self, query):
                self.query = query

            def fetchone(self):
                if "pg_try_advisory" in self.query:
                    return (True,)
                if "to_regprocedure" in self.query:
                    return ("staging.pr_sync_legacy(bigint)",)
                return (1,)

            def fetchall(self):
                return [(1, "99999999999")] if "FROM administrator" in self.query else []

        class Target:
            def cursor(self):
                return Cursor()

        records = {"administrator": [{"source_id": 1, "cpf": "11111111111"}],
                   "company": [], "company_unit": [], "manager": []}
        with self.assertRaisesRegex(ValueError, "source_id collision"):
            preflight(Target(), records)


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

        with patch("migration.database.psycopg.connect", side_effect=lambda url: Connection(url)):
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
