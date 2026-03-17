from psycopg_pool import ConnectionPool
from app.core.settings import settings

pool = ConnectionPool(conninfo=settings.DATABASE_URL, min_size=1, max_size=10)

def get_conn():
    return pool.connection()
