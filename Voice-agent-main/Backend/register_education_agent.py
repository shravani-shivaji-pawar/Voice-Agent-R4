"""
register_education_agent.py — Registers Aarohi (Education Counselling Agent) into SQLite DB platform.db
and backend/db/agents.json so it appears in the frontend dashboard dropdown menu.
"""
import sqlite3
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "db", "platform.db")
AGENTS_JSON_PATH = os.path.join(BASE_DIR, "db", "agents.json")

AGENT_ID = "education_counselling"
AGENT_NAME = "Aarohi — Education Counselling Specialist"
AGENT_VOICE = "en-IN-NeerjaExpressiveNeural"
AGENT_LANG = "Multi (English, Hindi, Hinglish)"
AGENT_TYPE = "education"
SCHEMA_PATH = "Education_Counselling_Agent.json"
SCRIPT = "You are Aarohi, an AI Education Counsellor guiding students on courses, colleges, entrance exams, and study abroad options."

def register_agent():
    print(f"1. Updating SQLite Database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT id FROM agents WHERE id=?", (AGENT_ID,))
    row = cur.fetchone()

    if row:
        print(f"   Agent '{AGENT_ID}' already exists in DB. Updating record...")
        cur.execute("""
            UPDATE agents
            SET name=?, voice=?, language=?, agent_type=?, schema_path=?, script=?
            WHERE id=?
        """, (AGENT_NAME, AGENT_VOICE, AGENT_LANG, AGENT_TYPE, SCHEMA_PATH, SCRIPT, AGENT_ID))
    else:
        print(f"   Inserting new Agent '{AGENT_ID}' into DB...")
        cur.execute("""
            INSERT INTO agents (id, name, voice, language, agent_type, schema_path, script, provider, stt_provider, tts_provider)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Groq / Smallest AI', 'groq', 'edge')
        """, (AGENT_ID, AGENT_NAME, AGENT_VOICE, AGENT_LANG, AGENT_TYPE, SCHEMA_PATH, SCRIPT))

    conn.commit()
    conn.close()
    print("   Database update complete.")

    print(f"2. Updating JSON File: {AGENTS_JSON_PATH}")
    agents = []
    if os.path.exists(AGENTS_JSON_PATH):
        try:
            with open(AGENTS_JSON_PATH, "r", encoding="utf-8") as f:
                agents = json.load(f)
        except Exception as e:
            print(f"   Error reading agents.json: {e}")

    # Remove existing entry if present
    agents = [a for a in agents if a.get("id") != AGENT_ID and a.get("agent_id") != AGENT_ID]

    # Append new Aarohi agent
    new_agent_entry = {
        "id": AGENT_ID,
        "agent_id": AGENT_ID,
        "name": AGENT_NAME,
        "voice": AGENT_VOICE,
        "language": AGENT_LANG,
        "max_duration": 300,
        "provider": "Groq / Smallest AI",
        "script": SCRIPT,
        "data_fields": [
            "Current Qualification",
            "Preferred Course",
            "Preferred City",
            "Study Abroad",
            "Budget"
        ],
        "schema_path": SCHEMA_PATH,
        "agent_type": AGENT_TYPE,
        "createdAt": "2026-09-17T23:53:00.000000"
    }
    agents.insert(0, new_agent_entry)

    with open(AGENTS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(agents, f, indent=4)
    print("   JSON file update complete.")
    print("Done! Aarohi is registered.")

if __name__ == "__main__":
    register_agent()
