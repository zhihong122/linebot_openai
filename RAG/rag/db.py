from contextlib import contextmanager
import psycopg
from pgvector.psycopg import register_vector
from . import config

@contextmanager
def connection():
    if not config.DATABASE_URL:
        raise RuntimeError('請先設定 DATABASE_URL')
    with psycopg.connect(config.DATABASE_URL, connect_timeout=15) as conn:
        register_vector(conn)
        yield conn
