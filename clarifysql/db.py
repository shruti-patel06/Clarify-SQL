"""PostgreSQL access. Generated SQL only ever runs inside a read-only
transaction with a time limit, so even a query that slips past the
validator cannot change data or hang the app.
"""
from contextlib import contextmanager

import psycopg2

from clarifysql.config import DB_SETTINGS

STATEMENT_TIMEOUT_MS = 5000


def get_connection():
    return psycopg2.connect(**DB_SETTINGS)


@contextmanager
def read_only_cursor():
    conn = get_connection()
    try:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = %s", (STATEMENT_TIMEOUT_MS,))
            yield cur
    finally:
        conn.close()  # closing without commit rolls the transaction back


def run_query(sql):
    with read_only_cursor() as cur:
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description]
        return columns, cur.fetchall()


def explain_error(sql):
    """Asks Postgres to plan the query without running it. Returns None if
    the query is valid, otherwise Postgres's error message (which often
    includes a HINT such as "Perhaps you meant to reference column ...").
    """
    try:
        with read_only_cursor() as cur:
            cur.execute("EXPLAIN " + sql)
        return None
    except psycopg2.Error as e:
        return str(e).strip()
