import sys
import os
import sqlite3

sys.path.insert(0, os.path.abspath("."))
from db.db_manager import _get_connection

conn = _get_connection()
conn.row_factory = sqlite3.Row
row = conn.execute("SELECT * FROM agents WHERE id='agent-49f64ad7d683'").fetchone()
if row:
    d = dict(row)
    print("ID:", d.get("id"))
    print("NAME:", d.get("name"))
    print("AGENT_TYPE:", d.get("agent_type"))
    print("SCRIPT:", d.get("script"))
    print("SYSTEM_PROMPT:", d.get("system_prompt"))
    print("GREETING:", d.get("greeting_response"))
conn.close()
