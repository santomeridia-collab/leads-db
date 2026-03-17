import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', '140.245.239.67'),
    'database': os.getenv('DB_NAME', 'smrl_dev'),
    'user': os.getenv('DB_USER', 'teamsdb'),
    'password': os.getenv('DB_PASSWORD', 'smrl_dev251125'),
    'port': os.getenv('DB_PORT', '5432')
}

# Create connection pool
try:
    connection_pool = psycopg2.pool.SimpleConnectionPool(1, 20, **DB_CONFIG)
    print("Connection pool created successfully")
except Exception as e:
    print(f"Failed to create connection pool: {e}")
    raise

@contextmanager
def get_db_cursor(commit=False):
    conn = None
    cur = None
    try:
        conn = connection_pool.getconn()
        cur = conn.cursor()
        cur.execute("SET search_path TO test, public")
        yield cur
        if commit:
            conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if cur:
            cur.close()
        if conn:
            connection_pool.putconn(conn)