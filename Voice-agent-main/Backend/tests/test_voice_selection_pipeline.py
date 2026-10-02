"""
test_voice_selection_pipeline.py

Comprehensive test suite verifying voice selection from agent settings to runtime resolution and Smallest AI TTS payload.
"""

import unittest
import asyncio
import uuid
from pathlib import Path
import sys

# Ensure Backend is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from db.db_manager import db
from runtime_resolver import AgentRuntimeResolver
from tts.provider import _provider_config_from_agent_schema, clear_agent_config_cache, generate_speech_stream
from tts.tts_smallest import _resolve_speaker, get_voices_for_model_and_language, fetch_voice_catalog


class TestVoiceSelectionPipeline(unittest.TestCase):

    def setUp(self):
        clear_agent_config_cache()

    def test_01_anika_voice_selection(self):
        """Test 1: Anika selected in settings -> stored -> resolved -> Smallest AI TTS speaker == 'anika'."""
        agent_id = f"test-anika-{uuid.uuid4().hex[:6]}"
        data = {
            "name": "Test Anika Agent",
            "tts_provider": "smallest",
            "stt_provider": "smallest",
            "smallest_model": "lightning_v3.1",
            "smallest_voice": "anika",
            "voice": "anika",
            "language": "en",
        }
        
        async def run():
            created = await db.create_agent(agent_id, data)
            self.assertEqual(created.get("voice"), "anika")
            
            # Runtime resolution
            resolved = await AgentRuntimeResolver.resolve(agent_id)
            self.assertEqual(resolved.get("voice"), "anika")
            
            # TTS provider config lookup
            provider_cfg = _provider_config_from_agent_schema(agent_id)
            self.assertEqual(provider_cfg.get("voice"), "anika")
            
            # Smallest TTS speaker resolution
            speaker, _ = _resolve_speaker(provider_cfg.get("voice"), model="lightning_v3.1", language="en")
            self.assertEqual(speaker, "anika")
            
            # Clean up
            await db.delete_agent(agent_id)

        asyncio.run(run())

    def test_02_devansh_voice_selection(self):
        """Test 2: Devansh (male) selected -> stored -> resolved -> Smallest AI TTS speaker == 'devansh'."""
        agent_id = f"test-devansh-{uuid.uuid4().hex[:6]}"
        data = {
            "name": "Test Devansh Agent",
            "tts_provider": "smallest",
            "stt_provider": "smallest",
            "smallest_model": "lightning_v3.1",
            "smallest_voice": "devansh",
            "voice": "devansh",
            "language": "en",
        }
        
        async def run():
            created = await db.create_agent(agent_id, data)
            self.assertEqual(created.get("voice"), "devansh")
            
            # Runtime resolution
            resolved = await AgentRuntimeResolver.resolve(agent_id)
            self.assertEqual(resolved.get("voice"), "devansh")
            
            # TTS provider config lookup
            provider_cfg = _provider_config_from_agent_schema(agent_id)
            self.assertEqual(provider_cfg.get("voice"), "devansh")
            
            # Smallest TTS speaker resolution
            speaker, _ = _resolve_speaker(provider_cfg.get("voice"), model="lightning_v3.1", language="en")
            self.assertEqual(speaker, "devansh")
            
            # Clean up
            await db.delete_agent(agent_id)

        asyncio.run(run())

    def test_03_other_male_and_female_voices(self):
        """Test 3: Verify all supported catalog voices (divya, meher, arav, karan, emily, rachel)."""
        test_cases = [
            ("divya", "lightning_v3.1", "en"),
            ("karan", "lightning_v3.1", "en"),
            ("meher", "lightning_v3.1_pro", "en"),
            ("arav", "lightning_v3.1_pro", "en"),
            ("emily", "lightning_v3.1_pro", "en"),
            ("rachel", "lightning_v3.1_pro", "en"),
        ]
        
        async def run():
            for voice_name, model_name, lang in test_cases:
                agent_id = f"test-voice-{voice_name}-{uuid.uuid4().hex[:4]}"
                data = {
                    "name": f"Agent {voice_name}",
                    "tts_provider": "smallest",
                    "stt_provider": "smallest",
                    "smallest_model": model_name,
                    "smallest_voice": voice_name,
                    "voice": voice_name,
                    "language": lang,
                }
                await db.create_agent(agent_id, data)
                clear_agent_config_cache(agent_id)

                resolved = await AgentRuntimeResolver.resolve(agent_id)
                self.assertEqual(resolved.get("voice"), voice_name, f"Expected {voice_name} in runtime resolver")

                provider_cfg = _provider_config_from_agent_schema(agent_id)
                self.assertEqual(provider_cfg.get("voice"), voice_name, f"Expected {voice_name} in provider schema lookup")

                speaker, _ = _resolve_speaker(voice_name, model=model_name, language=lang)
                self.assertEqual(speaker, voice_name, f"Expected {voice_name} in Smallest AI TTS speaker resolver")

                await db.delete_agent(agent_id)

        asyncio.run(run())

    def test_04_configuration_persistence(self):
        """Test 4: Verify updating an agent's voice persists across DB get_agent and runtime reloads."""
        agent_id = f"test-persist-{uuid.uuid4().hex[:6]}"
        initial_data = {
            "name": "Persistence Agent",
            "tts_provider": "smallest",
            "smallest_voice": "anika",
            "voice": "anika",
        }
        
        async def run():
            await db.create_agent(agent_id, initial_data)
            
            # Verify initial
            ag1 = await db.get_agent(agent_id)
            self.assertEqual(ag1.get("voice"), "anika")
            
            # Update to devansh
            update_payload = {
                "name": "Persistence Agent Updated",
                "tts_provider": "smallest",
                "smallest_voice": "devansh",
                "voice": "devansh",
                "tts": {"provider": "smallest", "model": "lightning_v3.1", "voice": "devansh"}
            }
            await db.update_agent(agent_id, update_payload)
            clear_agent_config_cache(agent_id)

            # Reload and verify persistence
            ag2 = await db.get_agent(agent_id)
            self.assertEqual(ag2.get("voice"), "devansh")
            self.assertEqual(ag2.get("smallest_voice"), "devansh")
            
            resolved2 = await AgentRuntimeResolver.resolve(agent_id)
            self.assertEqual(resolved2.get("voice"), "devansh")

            # Clean up
            await db.delete_agent(agent_id)

        asyncio.run(run())

    def test_05_multiple_agents_isolation(self):
        """Test 5: Two agents with different voices must not leak voice configuration."""
        agent_a_id = f"agent-a-{uuid.uuid4().hex[:4]}"
        agent_b_id = f"agent-b-{uuid.uuid4().hex[:4]}"
        
        async def run():
            await db.create_agent(agent_a_id, {
                "name": "Agent A",
                "tts_provider": "smallest",
                "smallest_voice": "devansh",
                "voice": "devansh",
            })
            await db.create_agent(agent_b_id, {
                "name": "Agent B",
                "tts_provider": "smallest",
                "smallest_model": "lightning_v3.1_pro",
                "smallest_voice": "meher",
                "voice": "meher",
            })

            res_a = await AgentRuntimeResolver.resolve(agent_a_id)
            res_b = await AgentRuntimeResolver.resolve(agent_b_id)

            self.assertEqual(res_a.get("voice"), "devansh")
            self.assertEqual(res_b.get("voice"), "meher")

            cfg_a = _provider_config_from_agent_schema(agent_a_id)
            cfg_b = _provider_config_from_agent_schema(agent_b_id)

            self.assertEqual(cfg_a.get("voice"), "devansh")
            self.assertEqual(cfg_b.get("voice"), "meher")

            await db.delete_agent(agent_a_id)
            await db.delete_agent(agent_b_id)

        asyncio.run(run())

    def test_06_fallback_behavior(self):
        """Test 6: Agent without configured voice defaults safely without silent override of valid voices."""
        agent_id = f"test-fallback-{uuid.uuid4().hex[:6]}"
        data = {
            "name": "Unconfigured Voice Agent",
            "tts_provider": "smallest",
        }
        
        async def run():
            await db.create_agent(agent_id, data)
            
            resolved = await AgentRuntimeResolver.resolve(agent_id)
            self.assertEqual(resolved.get("voice"), "anika")

            # Test invalid voice name fallback
            speaker, _ = _resolve_speaker("non_existent_voice_xyz", model="lightning_v3.1", language="en")
            self.assertEqual(speaker, "anika")

            await db.delete_agent(agent_id)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
