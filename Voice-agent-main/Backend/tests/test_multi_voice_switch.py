"""
test_multi_voice_switch.py

Comprehensive test suite verifying that ONE SAME voice agent can switch voices
between conversations (Anika -> Dhruv -> Meher -> Anika) without recreating the agent,
with full persistence and session isolation.
"""

import unittest
import asyncio
import uuid
import sys
from pathlib import Path

# Ensure Backend is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from db.db_manager import db
from runtime_resolver import AgentRuntimeResolver
from tts.provider import _provider_config_from_agent_schema, clear_agent_config_cache, generate_speech_stream
from tts.tts_smallest import _resolve_speaker
from flows.runtime import RealEstateTTSProcessor, VoiceTurnState


class TestMultiVoiceSwitchForSameAgent(unittest.TestCase):

    def setUp(self):
        clear_agent_config_cache()

    def test_01_same_agent_multiple_voices_cycle(self):
        """
        Test 1 & 2 & 3: Same agent switching voices between conversations.
        Conversation 1: Anika
        Conversation 2: Dhruv
        Conversation 3: Meher
        Conversation 4: Back to Anika
        """
        agent_id = f"agent-foodie-{uuid.uuid4().hex[:6]}"
        initial_payload = {
            "name": "Foodie Agent",
            "agent_type": "custom",
            "script": "You are Foodie, a food recommendation expert.",
            "tts_provider": "smallest",
            "stt_provider": "smallest",
            "smallest_model": "lightning_v3.1",
            "smallest_voice": "anika",
            "voice": "anika",
            "language": "en",
        }

        async def run():
            # 1. Create agent with Anika voice
            created = await db.create_agent(agent_id, initial_payload)
            self.assertEqual(created.get("voice"), "anika")

            # --- Conversation 1 ---
            config_1 = await AgentRuntimeResolver.resolve(agent_id)
            self.assertEqual(config_1.get("voice"), "anika")
            tts_proc_1 = RealEstateTTSProcessor(agent_id=agent_id, voice_id=config_1.get("voice"))
            self.assertEqual(tts_proc_1.voice_id, "anika")
            spk_1, _ = _resolve_speaker(tts_proc_1.voice_id, model=config_1.get("smallest_model"), language="en")
            self.assertEqual(spk_1, "anika")

            # 2. Update same agent to Dhruv voice (Conversation 2)
            update_dhruv = {
                **created,
                "smallest_voice": "dhruv",
                "voice": "dhruv",
                "voice_id": "dhruv",
                "tts": {"provider": "smallest", "model": "lightning_v3.1", "voice": "dhruv"},
            }
            updated_dhruv = await db.update_agent(agent_id, update_dhruv)
            self.assertEqual(updated_dhruv.get("voice"), "dhruv")

            # --- Conversation 2 ---
            config_2 = await AgentRuntimeResolver.resolve(agent_id)
            self.assertEqual(config_2.get("voice"), "dhruv")
            tts_proc_2 = RealEstateTTSProcessor(agent_id=agent_id, voice_id=config_2.get("voice"))
            self.assertEqual(tts_proc_2.voice_id, "dhruv")
            spk_2, _ = _resolve_speaker(tts_proc_2.voice_id, model=config_2.get("smallest_model"), language="en")
            self.assertEqual(spk_2, "dhruv")

            # 3. Update same agent to Meher voice (Conversation 3)
            update_meher = {
                **updated_dhruv,
                "smallest_model": "lightning_v3.1_pro",
                "smallest_voice": "meher",
                "voice": "meher",
                "voice_id": "meher",
                "tts": {"provider": "smallest", "model": "lightning_v3.1_pro", "voice": "meher"},
            }
            updated_meher = await db.update_agent(agent_id, update_meher)
            self.assertEqual(updated_meher.get("voice"), "meher")

            # --- Conversation 3 ---
            config_3 = await AgentRuntimeResolver.resolve(agent_id)
            self.assertEqual(config_3.get("voice"), "meher")
            tts_proc_3 = RealEstateTTSProcessor(agent_id=agent_id, voice_id=config_3.get("voice"))
            self.assertEqual(tts_proc_3.voice_id, "meher")
            spk_3, _ = _resolve_speaker(tts_proc_3.voice_id, model=config_3.get("smallest_model"), language="en")
            self.assertEqual(spk_3, "meher")

            # 4. Switch back to Anika (Conversation 4)
            update_anika_again = {
                **updated_meher,
                "smallest_model": "lightning_v3.1",
                "smallest_voice": "anika",
                "voice": "anika",
                "voice_id": "anika",
                "tts": {"provider": "smallest", "model": "lightning_v3.1", "voice": "anika"},
            }
            updated_anika = await db.update_agent(agent_id, update_anika_again)
            self.assertEqual(updated_anika.get("voice"), "anika")

            # --- Conversation 4 ---
            config_4 = await AgentRuntimeResolver.resolve(agent_id)
            self.assertEqual(config_4.get("voice"), "anika")
            tts_proc_4 = RealEstateTTSProcessor(agent_id=agent_id, voice_id=config_4.get("voice"))
            self.assertEqual(tts_proc_4.voice_id, "anika")
            spk_4, _ = _resolve_speaker(tts_proc_4.voice_id, model=config_4.get("smallest_model"), language="en")
            self.assertEqual(spk_4, "anika")

            # Clean up
            await db.delete_agent(agent_id)

        asyncio.run(run())

    def test_02_persistence_after_db_reload(self):
        """Test 4: Verify selected voice survives DB re-query without memory caching issues."""
        agent_id = f"agent-persist-{uuid.uuid4().hex[:6]}"
        data = {
            "name": "Persistence Check Agent",
            "smallest_voice": "devansh",
            "voice": "devansh",
        }

        async def run():
            await db.create_agent(agent_id, data)

            # Reload from DB fresh
            agent_db = await db.get_agent(agent_id)
            self.assertEqual(agent_db.get("voice"), "devansh")
            self.assertEqual(agent_db.get("smallest_voice"), "devansh")

            resolved = await AgentRuntimeResolver.resolve(agent_id)
            self.assertEqual(resolved.get("voice"), "devansh")

            await db.delete_agent(agent_id)

        asyncio.run(run())

    def test_03_active_session_isolation(self):
        """
        Test 5: Active session continues with its initialized voice even if agent
        voice settings are modified during the active session. The next session picks up the new voice.
        """
        agent_id = f"agent-active-{uuid.uuid4().hex[:6]}"
        initial_data = {
            "name": "Active Session Agent",
            "smallest_voice": "anika",
            "voice": "anika",
        }

        async def run():
            await db.create_agent(agent_id, initial_data)

            # Session 1 starts with Anika
            cfg_s1 = await AgentRuntimeResolver.resolve(agent_id)
            session_1_tts = RealEstateTTSProcessor(agent_id=agent_id, voice_id=cfg_s1.get("voice"))
            self.assertEqual(session_1_tts.voice_id, "anika")

            # Mid-session 1: User updates agent settings to Dhruv in UI
            update_data = {
                **initial_data,
                "smallest_voice": "dhruv",
                "voice": "dhruv",
                "voice_id": "dhruv",
            }
            await db.update_agent(agent_id, update_data)

            # Active Session 1 remains stable on Anika
            self.assertEqual(session_1_tts.voice_id, "anika")

            # Session 2 starts: resolves newly saved Dhruv voice
            cfg_s2 = await AgentRuntimeResolver.resolve(agent_id)
            session_2_tts = RealEstateTTSProcessor(agent_id=agent_id, voice_id=cfg_s2.get("voice"))
            self.assertEqual(session_2_tts.voice_id, "dhruv")

            await db.delete_agent(agent_id)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
