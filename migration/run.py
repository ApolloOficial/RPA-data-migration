"""Lê uma visão consistente do legado e aciona a procedure de destino."""

import argparse
import os
import re
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from .database import DatabaseConnections


SOURCE_QUERIES = {
    "administrator": """
        SELECT u.id AS source_id, u.nome AS full_name, u.email, u.cpf,
               u.ativo AS status
        FROM usuario u JOIN tipo_usuario t ON t.id = u.id_tipo_usuario
        WHERE t.nome = 'ADMINISTRADOR' ORDER BY u.id
    """,
    "company": """
        SELECT e.id AS source_id, e.nome AS name, e.cnpj,
               e.email_contato AS contact_email, e.descricao AS description,
               e.ativo AS status, e.id_usuario_cadastro AS registered_by_source_id
        FROM empresa e ORDER BY e.id
    """,
    "company_unit": """
        SELECT f.id AS source_id, f.id_empresa AS company_source_id,
               f.id_segmento AS segment_source_id, s.nome AS segment_name,
               f.nome AS name, f.cnpj, f.email, f.telefone AS phone,
               a.logradouro AS street_name, a.numero AS number,
               a.complemento AS additional_info, a.bairro AS neighborhood,
               a.cidade AS city, a.estado AS state, a.cep AS zip_code,
               f.ativo AS status, f.id_usuario_cadastro AS registered_by_source_id
        FROM filial f JOIN segmento s ON s.id = f.id_segmento
        JOIN endereco a ON a.id = f.id_endereco ORDER BY f.id
    """,
    "manager": """
        SELECT u.id AS source_id, u.nome AS full_name, u.email, u.cpf,
               u.senha_hash AS password_hash, u.id_filial AS company_unit_source_id,
               u.id_usuario_cadastro AS registered_by_source_id,
               u.ativo AS status
        FROM usuario u JOIN tipo_usuario t ON t.id = u.id_tipo_usuario
        WHERE t.nome = 'GERENTE' ORDER BY u.id
    """,
}

STAGING_COLUMNS = {
    "administrator": ("source_id", "user_type", "full_name", "email", "cpf", "is_active"),
    "company": ("source_id", "name", "cnpj", "contact_email", "description", "is_active", "registered_by_source_id"),
    "company_unit": (
        "source_id", "company_source_id", "segment_source_id", "segment_name",
        "name", "cnpj", "email", "phone", "street_name", "number",
        "additional_info", "neighborhood", "city", "state", "zip_code",
        "is_active", "registered_by_source_id",
    ),
    "manager": (
        "source_id", "user_type", "full_name", "email", "cpf", "password_hash",
        "company_unit_source_id", "registered_by_source_id", "is_active",
    ),
}


def digits(value, length, table, source_id, field):
    normalized = re.sub(r"[^0-9]", "", value or "")
    if len(normalized) != length:
        raise ValueError(f"{table}:{source_id} has invalid {field}; expected {length} digits")
    return normalized


def required(value, table, source_id, field):
    if value is None or not str(value).strip():
        raise ValueError(f"{table}:{source_id} has empty {field}")
    return str(value).strip()


def transform(table, row):
    """Converte nomes, status e documentos para os campos de staging."""
    source_id = row["source_id"]
    item = dict(row)
    status = item.pop("status")
    if status not in ("ATIVO", "INATIVO", "CANCELADO"):
        raise ValueError(f"{table}:{source_id} has unsupported status")
    item["is_active"] = status == "ATIVO"
    if table in ("administrator", "manager"):
        item["user_type"] = "ADMINISTRADOR" if table == "administrator" else "GERENTE"
        item["cpf"] = digits(item["cpf"], 11, table, source_id, "cpf")
    if table in ("company", "company_unit"):
        item["cnpj"] = digits(item["cnpj"], 14, table, source_id, "cnpj")
    for field in ("email", "contact_email"):
        if field in item:
            item[field] = required(item[field], table, source_id, field).lower()
    if table == "company_unit":
        item["zip_code"] = digits(item["zip_code"], 8, table, source_id, "zip_code")
        item["state"] = required(item["state"], table, source_id, "state").upper()
        item["phone"] = required(item["phone"], table, source_id, "phone")
    if table != "administrator" and item["registered_by_source_id"] is None:
        raise ValueError(f"{table}:{source_id} has no registering administrator")
    return item


def extract(source):
    from psycopg.rows import dict_row

    result = {}
    with source.cursor(row_factory=dict_row) as cursor:
        for table, query in SOURCE_QUERIES.items():
            cursor.execute(query)
            result[table] = [transform(table, row) for row in cursor.fetchall()]
        cursor.execute("SELECT t.nome, count(*) AS total FROM usuario u JOIN tipo_usuario t ON t.id = u.id_tipo_usuario GROUP BY t.nome")
        user_types = {row["nome"]: row["total"] for row in cursor.fetchall()}
        cursor.execute("SELECT 'contrato' AS name, count(*) AS total FROM contrato UNION ALL "
                       "SELECT 'inversor', count(*) FROM inversor UNION ALL "
                       "SELECT 'string', count(*) FROM string UNION ALL "
                       "SELECT 'painel', count(*) FROM painel UNION ALL "
                       "SELECT 'manutencao', count(*) FROM manutencao")
        outside_contract = {row["name"]: row["total"] for row in cursor.fetchall()}
    admins = {row["source_id"] for row in result["administrator"]}
    companies = {row["source_id"] for row in result["company"]}
    units = {row["source_id"] for row in result["company_unit"]}
    for table in ("company", "company_unit", "manager"):
        for row in result[table]:
            if row["registered_by_source_id"] not in admins:
                raise ValueError(f"{table}:{row['source_id']} references an administrator outside the legacy snapshot")
            if table == "company_unit" and row["company_source_id"] not in companies:
                raise ValueError(f"company_unit:{row['source_id']} references an unknown company")
            if table == "manager" and row["company_unit_source_id"] not in units:
                raise ValueError(f"manager:{row['source_id']} references an unknown company unit")
    return result, user_types, outside_contract


def preflight(target, records):
    """Evita colisões de source_id com dados de demonstração do destino."""
    checks = (
        ("administrator", "administrator", "cpf"),
        ("company", "company", "cnpj"),
        ("company_unit", "company_unit", "cnpj"),
        # O empregado no destino não tem CPF; o e-mail identifica um gerente existente.
        ("manager", "employee", "email"),
    )
    with target.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_xact_lock(7193026)")
        if not cursor.fetchone()[0]:
            raise ValueError("another migration is running against this destination")
        cursor.execute("SELECT to_regprocedure('staging.pr_sync_legacy(bigint)')")
        if cursor.fetchone()[0] is None:
            raise ValueError("destination is missing staging.pr_sync_legacy(bigint)")
        cursor.execute("SELECT 1 FROM roles WHERE name = 'GERENTE'")
        if cursor.fetchone() is None:
            raise ValueError("destination is missing the GERENTE role")
        for source_table, target_table, identity in checks:
            cursor.execute(f"SELECT source_id, {identity} FROM {target_table} WHERE source_id IS NOT NULL")
            existing = dict(cursor.fetchall())
            for row in records[source_table]:
                old = existing.get(row["source_id"])
                if old is not None and str(old).strip().lower() != row[identity].lower():
                    raise ValueError(
                        f"source_id collision in {target_table}:{row['source_id']}; "
                        "use a clean destination or resolve the conflicting demo data"
                    )


def load(target, records):
    tables = {"administrator": "legacy_user", "manager": "legacy_user",
              "company": "legacy_company", "company_unit": "legacy_company_unit"}
    with target.cursor() as cursor:
        cursor.execute(
            "INSERT INTO staging.rpa_load_batch (source_system) "
            "VALUES ('CRUD_1ANO') RETURNING id"
        )
        batch_id = cursor.fetchone()[0]
        for table in ("administrator", "company", "company_unit", "manager"):
            columns = STAGING_COLUMNS[table]
            names = ", ".join(("load_batch_id", *columns))
            placeholders = ", ".join(["%s"] * (len(columns) + 1))
            query = f"INSERT INTO staging.{tables[table]} ({names}) VALUES ({placeholders})"
            cursor.executemany(query, [(batch_id, *(row[column] for column in columns)) for row in records[table]])
        cursor.execute("CALL staging.pr_sync_legacy(%s)", (batch_id,))
        cursor.execute(
            "SELECT status, total_records, processed_records, failed_records "
            "FROM staging.rpa_load_batch WHERE id = %s", (batch_id,)
        )
        status, total, processed, failed = cursor.fetchone()
        return batch_id, status, total, processed, failed


def record_validation_failure(target, error):
    """Registra uma falha anterior à carga sem gravar o conteúdo do registro."""
    match = re.search(r"(?:administrator|company_unit|company|manager):\d+\b", str(error))
    source_key = match.group(0) if match else None
    with target.cursor() as cursor:
        cursor.execute(
            "INSERT INTO staging.rpa_load_batch (source_system, status, finished_at) "
            "VALUES ('CRUD_1ANO', 'FAILED', CURRENT_TIMESTAMP) RETURNING id"
        )
        batch_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO staging.rpa_load_error "
            "(load_batch_id, source_record_key, error_message) VALUES (%s, %s, %s)",
            (batch_id, source_key, str(error)),
        )
    return batch_id


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
                records, user_types, outside_contract = extract(databases.source)
                preflight(databases.target, records)
            except ValueError as exc:
                print(f"Migration stopped: {exc}", file=sys.stderr)
                if not args.check:
                    batch_id = record_validation_failure(databases.target, exc)
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
            batch_id, status, total, processed, failed = load(databases.target, records)
        print(f"Batch {batch_id}: {status}; total={total}, processed={processed}, failed={failed}")
        if failed:
            print(f"Inspect staging.rpa_load_error for batch {batch_id}", file=sys.stderr)
            return 2
        return 0
    except (ValueError, psycopg.Error) as exc:
        print(f"Migration stopped: {exc}", file=sys.stderr)
        return 1
