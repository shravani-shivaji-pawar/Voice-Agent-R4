import sqlite3
import json
import os

def inspect_db():
    db_path = "Backend/db/platform.db"
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rows = cur.execute("SELECT * FROM agents").fetchall()
        print("=== AGENTS TABLE IN DB ===")
        for r in rows:
            d = dict(r)
            print(f"id={d.get('id')} name={d.get('name')} voice={d.get('voice')} status={d.get('certification_status') or d.get('status')}")
        conn.close()

def inspect_files():
    agents_dir = "Backend/db/agents"
    print("\n=== AGENT JSON FILES ===")
    if os.path.exists(agents_dir):
        for fname in os.listdir(agents_dir):
            if fname.endswith(".json"):
                fpath = os.path.join(agents_dir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    print(f"{fname}: id={data.get('id') or data.get('agent_id')} voice={data.get('voice')} voice_id={data.get('voice_id')} smallest_voice={data.get('smallest_voice')}")

if __name__ == "__main__":
    inspect_db()
    inspect_files()
