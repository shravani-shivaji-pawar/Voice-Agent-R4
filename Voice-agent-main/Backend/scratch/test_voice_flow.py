import asyncio
import json
import os
import sys
from pathlib import Path

# Add Backend to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.db_manager import db
from runtime_resolver import AgentRuntimeResolver
from tts.provider import _provider_config_from_agent_schema, clear_agent_config_cache

async def test_voice_save_publish_flow():
    print("=== TESTING VOICE SAVE & PUBLISH FLOW FOR REAL_ESTATE ===")

    # Step 1: Initial state
    agent_id = "real_estate"
    initial_agent = await db.get_agent(agent_id)
    print(f"1. Initial DB agent voice: '{initial_agent.get('voice')}'")

    initial_resolved = await AgentRuntimeResolver.resolve(agent_id)
    print(f"1. Initial Resolved voice: '{initial_resolved.get('voice')}'")

    initial_provider_cfg = _provider_config_from_agent_schema(agent_id)
    print(f"1. Initial Provider Cfg voice: '{initial_provider_cfg.get('voice')}'")

    # Step 2: Update voice to Divya
    print("\n--- Updating voice to 'divya' ---")
    update_payload = {
        **initial_agent,
        "voice": "divya",
        "smallest_voice": "divya",
        "voice_id": "divya",
        "tts": {"provider": "smallest", "model": "lightning_v3.1", "voice": "divya"},
        "status": "Published"
    }

    # Simulate PUT /api/agents/real_estate logic from main.py
    from main import _normalize_agent_record, _voice_id_for_agent, _agent_schema_path, _write_agent_runtime_schema
    merged = _normalize_agent_record({**initial_agent, **update_payload})
    voice_id = _voice_id_for_agent(merged["voice"])
    schema_path = _agent_schema_path(agent_id, initial_agent.get("schema_path"))
    
    _write_agent_runtime_schema(agent_id, schema_path, merged, voice_id, None)
    updated_db = await db.update_agent(agent_id, merged)
    clear_agent_config_cache(agent_id)

    print(f"2. Updated DB voice: '{updated_db.get('voice')}'")
    
    # Step 3: Resolve at session init
    session_resolved = await AgentRuntimeResolver.resolve(agent_id)
    print(f"3. Session Resolved voice: '{session_resolved.get('voice')}'")

    session_provider_cfg = _provider_config_from_agent_schema(agent_id)
    print(f"3. Session Provider Cfg voice: '{session_provider_cfg.get('voice')}'")

    # Check JSON files
    with open(schema_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)
        print(f"3. Schema JSON ({schema_path}) voice: '{json_data.get('voice')}' (voice_id: '{json_data.get('voice_id')}')")

if __name__ == "__main__":
    asyncio.run(test_voice_save_publish_flow())
