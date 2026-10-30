"""Ponto de entrada da execução agendada na AWS Lambda."""

import json
import os

import boto3

from .main import run_once


def handler(event, context):
    """Carrega as conexões do Secrets Manager e executa uma migração."""
    secret_arn = os.environ["DATABASE_SECRET_ARN"]
    secret = boto3.client("secretsmanager").get_secret_value(SecretId=secret_arn)
    connections = json.loads(secret["SecretString"])
    legacy_dsn = connections.get("LEGACY_DATABASE_URL")
    target_dsn = connections.get("TARGET_DATABASE_URL")
    if not legacy_dsn or not target_dsn:
        raise ValueError("Database secret must define both connection URLs")

    result = run_once(legacy_dsn=legacy_dsn, target_dsn=target_dsn)
    if result:
        raise RuntimeError(f"Migration stopped with exit code {result}")
    return {"status": "success"}
