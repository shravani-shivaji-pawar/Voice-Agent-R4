"""
Scratch script to test end-to-end voice setting changes, Save, Publish, and TTS resolution.
"""

import sys
import os
import asyncio

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from db.db_manager import db
from runtime_resolver import AgentRuntimeResolver
from tts.provider import _provider_config_from_agent_schema, clear_agent_config_cache, generate_speech_stream
from main import _normalize_agent_record, _write_agent_runtime_schema, _voice_id_for_agent, _agent_schema_path

async def run_publish_test():
    agent_id = "real_estate"
    print(f"=== TESTING SAVE AND PUBLISH VOICE SWITCHING FOR AGENT '{agent_id}' ===")
    
    test_voices = ["divya", "dhruv", "anika", "devansh"]
    
    for voice in test_voices:
        print(f"\n--- STEP: Setting voice to '{voice}' ---")
        existing = await db.get_agent(agent_id)
        if not existing:
            print(f"Error: Agent '{agent_id}' not found in DB")
            return
            
        # 1. Simulate SAVE (PUT /api/agents/{agent_id})
        patch = {"voice": voice}
        merged = _normalize_agent_record({**existing, **patch})
        voice_id = _voice_id_for_agent(merged["voice"])
        schema_path = _agent_schema_path(agent_id, existing.get("schema_path"))
        _write_agent_runtime_schema(agent_id, schema_path, merged, voice_id, None)
        await db.update_agent(agent_id, merged)
        
        # 2. Simulate PUBLISH (POST /api/agents/{agent_id}/publish)
        published_merged = _normalize_agent_record({
            **merged,
            "certification_status": "Certified",
            "status": "Published"
        })
        _write_agent_runtime_schema(agent_id, schema_path, published_merged, voice_id, None)
        await db.update_agent(agent_id, published_merged)
        clear_agent_config_cache(agent_id)
        
        # 3. Verify DB record
        fresh_db = await db.get_agent(agent_id)
        db_voice = fresh_db.get("voice")
        print(f"[DB RECORD] voice='{db_voice}', smallest_voice='{fresh_db.get('smallest_voice')}'")
        assert db_voice == voice, f"DB voice mismatch: expected '{voice}', got '{db_voice}'"
        
        # 4. Verify Runtime Resolver
        resolved_config = await AgentRuntimeResolver.resolve(agent_id)
        resolved_voice = resolved_config.get("voice")
        print(f"[RUNTIME RESOLVER] resolved_voice='{resolved_voice}'")
        assert resolved_voice == voice, f"Resolver voice mismatch: expected '{voice}', got '{resolved_voice}'"
        
        # 5. Verify TTS Provider Schema Config
        provider_cfg = _provider_config_from_agent_schema(agent_id)
        schema_voice = provider_cfg.get("voice")
        print(f"[TTS PROVIDER CFG] schema_voice='{schema_voice}'")
        assert schema_voice == voice, f"Provider schema voice mismatch: expected '{voice}', got '{schema_voice}'"
        
        # 6. Verify Live Audio Generation
        audio_stream = generate_speech_stream(f"Testing voice {voice}", agent_id=agent_id, voice=resolved_voice)
        chunks = []
        for chunk in audio_stream:
            if chunk:
                chunks.append(chunk)
                if len(chunks) >= 3:
                    break
        print(f"[LIVE SYNTHESIS] Voice '{voice}' generated {len(chunks)} PCM16 audio chunks successfully!")

    print("\n==========================================")
    print("SUCCESS: Save & Publish voice persistence test passed for all voices!")
    print("==========================================")

if __name__ == "__main__":
    asyncio.run(run_publish_test())
