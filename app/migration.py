"""Extrai, transforma e carrega os cadastros legados no banco final."""

import re


SOURCE_QUERIES = {
    "administrator": """
        SELECT u.id AS source_id, u.nome AS full_name, u.email, u.cpf,
               u.ativo AS status
        FROM usuario u JOIN tipo_usuario t ON t.id = u.id_tipo_usuario
        WHERE upper(btrim(t.nome)) = 'ADMINISTRADOR' ORDER BY u.id
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
        WHERE upper(btrim(t.nome)) = 'GERENTE' ORDER BY u.id
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

TARGET_REQUIRED_COLUMNS = {
    "roles": ("name",),
    "administrator": ("id", "full_name", "email", "cpf", "is_active", "source_id", "synced_at"),
    "company": (
        "id", "name", "cnpj", "contact_email", "description", "is_active", "registered_by",
        "source_id", "synced_at",
    ),
    "segment": ("id", "name", "source_id", "synced_at"),
    "address": ("id", "street_name", "number", "additional_info", "neighborhood", "city", "state", "zip_code"),
    "company_unit": (
        "id", "company_id", "segment_id", "address_id", "name", "cnpj", "email", "phone",
        "registered_by", "is_active", "source_id", "synced_at", "responsible_employee_id",
    ),
    "employee": (
        "id", "full_name", "email", "password_hash", "role_id", "company_unit_id",
        "is_active", "is_first_access", "registered_by", "source_id", "synced_at",
    ),
    "staging.rpa_load_batch": (
        "id", "source_system", "status", "total_records", "processed_records", "failed_records",
    ),
    "staging.legacy_user": (
        "load_batch_id", "source_id", "user_type", "full_name", "email", "cpf", "password_hash",
        "company_unit_source_id", "registered_by_source_id", "is_active", "processing_status",
    ),
    "staging.legacy_company": (
        "load_batch_id", "source_id", "name", "cnpj", "contact_email", "description",
        "is_active", "registered_by_source_id", "processing_status",
    ),
    "staging.legacy_company_unit": (
        "load_batch_id", "source_id", "company_source_id", "segment_source_id", "segment_name",
        "name", "cnpj", "email", "phone", "street_name", "number", "additional_info",
        "neighborhood", "city", "state", "zip_code", "is_active", "registered_by_source_id",
        "processing_status",
    ),
    "staging.rpa_load_error": ("load_batch_id", "source_record_key", "error_message", "source_payload"),
}

TARGET_SOURCE_ID_QUERIES = {
    "administrator": "SELECT source_id FROM administrator WHERE source_id = ANY(%s)",
    "company": "SELECT source_id FROM company WHERE source_id = ANY(%s)",
    "company_unit": "SELECT source_id FROM company_unit WHERE source_id = ANY(%s)",
    "manager": """
        SELECT e.source_id, r.name
        FROM employee e JOIN roles r ON r.id = e.role_id
        WHERE e.source_id = ANY(%s)
    """,
}


def normalize_digits(value, length, table, source_id, field):
    normalized = re.sub(r"[^0-9]", "", value or "")
    if len(normalized) != length:
        raise ValueError(f"{table}:{source_id} has invalid {field}; expected {length} digits")
    return normalized


def require_text(value, table, source_id, field):
    if value is None or not str(value).strip():
        raise ValueError(f"{table}:{source_id} has empty {field}")
    return str(value).strip()


def normalize_legacy_row(table, row):
    """Converte nomes, status e documentos para os campos de staging."""
    source_id = row["source_id"]
    item = dict(row)
    status = str(item.pop("status")).strip().upper()
    if status not in ("ATIVO", "INATIVO", "CANCELADO"):
        raise ValueError(f"{table}:{source_id} has unsupported status")
    item["is_active"] = status == "ATIVO"
    if table in ("administrator", "manager"):
        item["user_type"] = "ADMINISTRADOR" if table == "administrator" else "GERENTE"
        item["cpf"] = normalize_digits(item["cpf"], 11, table, source_id, "cpf")
    if table in ("company", "company_unit"):
        item["cnpj"] = normalize_digits(item["cnpj"], 14, table, source_id, "cnpj")
    for field in ("email", "contact_email"):
        if field in item:
            item[field] = require_text(item[field], table, source_id, field).lower()
    if table == "company_unit":
        item["zip_code"] = normalize_digits(item["zip_code"], 8, table, source_id, "zip_code")
        item["state"] = require_text(item["state"], table, source_id, "state").upper()
        item["phone"] = require_text(item["phone"], table, source_id, "phone")
    return item


def extract_legacy_snapshot(source):
    from psycopg.rows import dict_row

    result = {}
    with source.cursor(row_factory=dict_row) as cursor:
        for table, query in SOURCE_QUERIES.items():
            cursor.execute(query)
            result[table] = [normalize_legacy_row(table, row) for row in cursor.fetchall()]
        cursor.execute("SELECT t.nome, count(*) AS total FROM usuario u JOIN tipo_usuario t ON t.id = u.id_tipo_usuario GROUP BY t.nome")
        user_types = {row["nome"].strip().upper(): row["total"] for row in cursor.fetchall()}
        cursor.execute("SELECT 'contrato' AS name, count(*) AS total FROM contrato UNION ALL "
                       "SELECT 'inversor', count(*) FROM inversor UNION ALL "
                       "SELECT 'string', count(*) FROM string UNION ALL "
                       "SELECT 'painel', count(*) FROM painel UNION ALL "
                       "SELECT 'manutencao', count(*) FROM manutencao")
        outside_contract = {row["name"]: row["total"] for row in cursor.fetchall()}
    if not any(result.values()):
        raise ValueError("legacy snapshot has no records in the migration contract")
    companies = {row["source_id"] for row in result["company"]}
    for row in result["company_unit"]:
        if row["company_source_id"] not in companies:
            raise ValueError(f"company_unit:{row['source_id']} references an unknown company")
    return result, user_types, outside_contract


def find_records_missing_from_target(target, records):
    """Retorna apenas IDs de origem ainda ausentes no banco final."""
    missing = {}
    with target.cursor() as cursor:
        for table, rows in records.items():
            source_ids = [row["source_id"] for row in rows]
            if not source_ids:
                missing[table] = []
                continue

            cursor.execute(TARGET_SOURCE_ID_QUERIES[table], (source_ids,))
            target_rows = cursor.fetchall()
            if table == "manager":
                wrong_roles = [source_id for source_id, role in target_rows if role != "GERENTE"]
                if wrong_roles:
                    raise ValueError(
                        "manager source IDs already belong to another employee role: "
                        + ", ".join(map(str, wrong_roles))
                    )
                existing_ids = {source_id for source_id, _ in target_rows}
            else:
                existing_ids = {row[0] for row in target_rows}

            missing[table] = [row for row in rows if row["source_id"] not in existing_ids]
    return missing


def validate_target_for_migration(target):
    """Confere os pré-requisitos do destino e reserva a carga em andamento."""
    expected_columns = [
        ("staging" if "." in table else "public", table.split(".")[-1], column)
        for table, columns in TARGET_REQUIRED_COLUMNS.items()
        for column in columns
    ]
    values = ", ".join(["(%s, %s, %s)"] * len(expected_columns))
    with target.cursor() as cursor:
        cursor.execute(
            "WITH expected(table_schema, table_name, column_name) AS (VALUES " + values + ") "
            "SELECT e.table_schema || '.' || e.table_name || '.' || e.column_name "
            "FROM expected e LEFT JOIN information_schema.columns c "
            "ON c.table_schema = e.table_schema AND c.table_name = e.table_name "
            "AND c.column_name = e.column_name WHERE c.column_name IS NULL "
            "ORDER BY e.table_schema, e.table_name, e.column_name",
            [value for row in expected_columns for value in row],
        )
        missing_columns = [row[0] for row in cursor.fetchall()]
        if missing_columns:
            raise ValueError(
                "destination schema is incompatible; missing columns: " + ", ".join(missing_columns)
            )
        cursor.execute(
            "SELECT COALESCE(column_default::boolean, false) "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'employee' "
            "AND column_name = 'is_first_access'"
        )
        if not cursor.fetchone()[0]:
            raise ValueError("destination schema requires employee.is_first_access DEFAULT true")
        cursor.execute("SELECT pg_try_advisory_xact_lock(7193026)")
        if not cursor.fetchone()[0]:
            raise ValueError("another migration is running against this destination")
        cursor.execute("SELECT to_regprocedure('staging.pr_sync_legacy(bigint)')")
        if cursor.fetchone()[0] is None:
            raise ValueError("destination is missing staging.pr_sync_legacy(bigint)")
        cursor.execute("SELECT 1 FROM roles WHERE name = 'GERENTE'")
        if cursor.fetchone() is None:
            raise ValueError("destination is missing the GERENTE role")


def load_staging_batch(target, records):
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
            "UPDATE staging.rpa_load_error SET source_payload = NULL "
            "WHERE load_batch_id = %s AND source_payload IS NOT NULL",
            (batch_id,),
        )
        cursor.execute(
            "SELECT status, total_records, processed_records, failed_records "
            "FROM staging.rpa_load_batch WHERE id = %s", (batch_id,)
        )
        status, total, processed, failed = cursor.fetchone()
        return batch_id, status, total, processed, failed


def record_failed_batch(target, error):
    """Registra uma falha anterior à carga sem gravar o conteúdo do registro."""
    match = re.search(r"(?:administrator|company_unit|company|manager):\d+\b", str(error))
    source_key = match.group(0) if match else None
    with target.cursor() as cursor:
        cursor.execute(
            "INSERT INTO staging.rpa_load_batch "
            "(source_system, status, finished_at, total_records, failed_records) "
            "VALUES ('CRUD_1ANO', 'FAILED', CURRENT_TIMESTAMP, 1, 1) RETURNING id"
        )
        batch_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO staging.rpa_load_error "
            "(load_batch_id, source_record_key, error_message) VALUES (%s, %s, %s)",
            (batch_id, source_key, str(error)),
        )
    return batch_id
