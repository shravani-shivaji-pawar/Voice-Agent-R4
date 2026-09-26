import sys
import os
import sqlite3

sys.path.insert(0, os.path.abspath("."))

from db.db_manager import _get_connection

conn = _get_connection()
conn.row_factory = sqlite3.Row
cursor = conn.execute("SELECT id, name, agent_type FROM agents")
rows = cursor.fetchall()
print(f"Total agents in DB: {len(rows)}")
for r in rows:
    print(dict(r))
conn.close()
