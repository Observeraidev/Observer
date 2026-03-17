import os
from typing import Any, Callable, Optional

import psycopg
from psycopg.rows import dict_row as _psycopg_dict_row


# Single source of truth for DB connection string
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://observer:observer@127.0.0.1:5432/observer",
)

def dict_row(cursor):
    """
    psycopg3 row_factory must be a callable that accepts ONLY (cursor)
    and returns a row-maker function.
    """
    return _psycopg_dict_row(cursor)

def connect(dsn: str = DATABASE_URL, row_factory: Optional[Callable[..., Any]] = None):
    """
    Wrapper around psycopg.connect used by core modules.
    """
    if row_factory is not None:
        return psycopg.connect(dsn, row_factory=row_factory)
    return psycopg.connect(dsn)
