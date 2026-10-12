"""Creates the tables by running schema.sql against the database.
Run this once after starting PostgreSQL (docker compose up -d):
    python -m scripts.init_db
"""
from pathlib import Path

from clarifysql.db import get_connection

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"


def init():
    with open(SCHEMA_PATH) as f:
        sql = f.read()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close()
    conn.close()
    print("Tables created.")


if __name__ == "__main__":
    init()
