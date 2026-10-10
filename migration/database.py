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

    def __enter__(self):
        try:
            self.source = self._stack.enter_context(psycopg.connect(self.legacy_url))
            self.source.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            self.target = self._stack.enter_context(psycopg.connect(self.target_url))
        except BaseException:
            self._stack.close()
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self._stack.__exit__(exc_type, exc_value, traceback)
