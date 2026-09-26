import sys
import os
import sqlite3

sys.path.insert(0, os.path.abspath("."))
from db.db_manager import _get_connection, _CACHE_GET_AGENT

conn = _get_connection()
conn.execute("""
    UPDATE agents 
    SET agent_type = 'custom',
        script = 'You are Mock Interview Coach, an expert technical interview coach. You help candidates practice technical interviews, answer questions, provide instant feedback, and boost candidate confidence for AI/ML and IT engineering roles.',
        greeting_response = 'Hello! I''m Mock Interview Coach. How can I assist you today?'
    WHERE id = 'agent-49f64ad7d683' OR name LIKE '%Mock Interview%'
""")
conn.commit()
conn.close()
_CACHE_GET_AGENT.clear()
print("Updated Mock Interview Coach agent in DB successfully.")
