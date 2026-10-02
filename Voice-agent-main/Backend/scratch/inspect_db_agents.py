import sqlite3
import json
import os

db_path = "Backend/db/platform.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
rows = cur.execute("SELECT id, name, voice, tts_provider, smallest_model FROM agents").fetchall()
print("=== AGENTS TABLE IN DB ===")
for r in rows:
    print(dict(r))
conn.close()
