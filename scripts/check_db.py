"""Shows exactly what database the app is connecting to and what tables
exist in it. Run this if a query fails with "relation ... does not
exist" — it tells you whether scripts/init_db.py needs to be (re)run, or
whether the app is pointed at a different database than you think.
"""
from clarifysql.db import get_connection

conn = get_connection()
cur = conn.cursor()

cur.execute("SELECT current_database(), current_user;")
db_name, db_user = cur.fetchone()
print(f"Connected to database '{db_name}' as user '{db_user}'")

cur.execute(
    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
)
tables = [row[0] for row in cur.fetchall()]
print("Tables found:", tables if tables else "(none — run python -m scripts.init_db)")

cur.close()
conn.close()
