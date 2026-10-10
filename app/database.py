"""Gerencia as transações de leitura do legado e de escrita no destino."""

from contextlib import ExitStack

import psycopg


class DatabaseConnections:
    """Abre os dois bancos e encerra as conexões na ordem inversa."""

    def __init__(self, legacy_url, target_url):
        self.legacy_url = legacy_url
        self.target_url = target_url
        self._stack = ExitStack()
        self.source = None
        self.target = None

    def connect_legacy(self):
        """Conecta ao banco antigo com leitura consistente e sem escrita."""
        self.source = self._stack.enter_context(psycopg.connect(self.legacy_url))
        self.source.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        return self.source

    def connect_target(self):
        """Conecta ao banco novo para registrar e processar o lote."""
        self.target = self._stack.enter_context(psycopg.connect(self.target_url))
        return self.target

    def close_connections(self, exc_type=None, exc_value=None, traceback=None):
        """Encerra as conexões; uma exceção desfaz a transação do destino."""
        return self._stack.__exit__(exc_type, exc_value, traceback)

    def __enter__(self):
        try:
            self.connect_legacy()
            self.connect_target()
        except BaseException:
            self.close_connections()
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self.close_connections(exc_type, exc_value, traceback)
