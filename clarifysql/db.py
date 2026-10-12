import psycopg2

from clarifysql.config import DB_SETTINGS


def get_connection():
    return psycopg2.connect(**DB_SETTINGS)


def run_query(sql):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(sql)
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return columns, rows
