"""Own the legacy read transaction and the destination write transaction."""

from contextlib import ExitStack

import psycopg


class DatabaseConnections:
    """Open both databases and close them in reverse order on every exit path."""

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
