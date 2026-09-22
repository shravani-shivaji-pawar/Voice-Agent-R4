"""
test_dynamic_agents_e2e.py — End-to-end verification that every user-created agent operates as an independent configuration-driven agent.
"""

import sys
import os
import asyncio
import pytest

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from agents.agent_builder import generate_agent_config_from_prompt
from db.db_manager import db
from llm.llm import generate_combined_intent_and_response
from flows.runtime import RealEstateLLMProcessor, VoiceTurnState


def test_dynamic_agent_creation_and_persistence():
    async def _async():
        await db.initialize()

        # 1. Generate an LIC Insurance Customer Support Agent from prompt
        lic_prompt = "Create a professional LIC insurance customer support agent named Kavya to help clients with policy renewal, term insurance quotes, and claim status."
        lic_config = await generate_agent_config_from_prompt(lic_prompt, client_id="test-client-lic")

        assert lic_config.id is not None
        assert "lic" in lic_config.name.lower() or "insurance" in lic_config.name.lower() or "kavya" in lic_config.name.lower()
        assert "insurance" in lic_config.system_prompt.lower() or "lic" in lic_config.system_prompt.lower()
        assert lic_config.stt.provider == "smallest"
        assert lic_config.tts.provider == "smallest"

        # Save agent to SQLite DB
        legacy_lic = lic_config.to_legacy_dict()
        await db.save_agent(legacy_lic)

        # Retrieve saved agent from SQLite DB
        retrieved_agent = await db.get_agent(lic_config.id)
        assert retrieved_agent is not None
        assert retrieved_agent["id"] == lic_config.id
        assert retrieved_agent["name"] == lic_config.name

        # 2. Generate a Banking Customer Support Agent from prompt
        bank_prompt = "Create a friendly HDFC bank customer support voice agent named Rohan for credit card queries and loan options."
        bank_config = await generate_agent_config_from_prompt(bank_prompt, client_id="test-client-bank")
        await db.save_agent(bank_config.to_legacy_dict())

        retrieved_bank = await db.get_agent(bank_config.id)
        assert retrieved_bank is not None
        assert retrieved_bank["id"] == bank_config.id

        print("SUCCESS: Prompt-generated agents correctly persisted in SQLite DB.")

    asyncio.run(_async())


def test_dynamic_agent_llm_turn_execution():
    async def _async():
        await db.initialize()

        # Test LIC Insurance Agent turn execution
        lic_system_prompt = (
            "You are Kavya, a senior LIC Insurance advisor on a live call. "
            "Help customers check policy details, term insurance, and premium renewals. "
            "Never talk about real estate, apartments, or education."
        )

        history = [{"role": "user", "content": "I want to know about my LIC term insurance plan."}]
        analysis = await generate_combined_intent_and_response(
            user_input="How can I renew my LIC policy online?",
            history=history,
            domain="insurance",
            system_prompt=lic_system_prompt
        )

        assert analysis is not None
        assert analysis.spoken_reply_text is not None
        assert len(analysis.spoken_reply_text) > 0
        reply_lower = analysis.spoken_reply_text.lower()
        
        # Verify NO leakage of Suncity / Real Estate / Aarohi
        assert "suncity" not in reply_lower
        assert "bhk" not in reply_lower
        assert "aarohi" not in reply_lower

        print(f"LIC Agent Response: '{analysis.spoken_reply_text}'")

    asyncio.run(_async())


def test_real_estate_llm_processor_with_custom_config():
    async def _async():
        turn_state = VoiceTurnState()
        custom_lic_config = {
            "id": "lic_agent_101",
            "name": "LIC Insurance Assistant",
            "agent_type": "insurance",
            "script": "You are Kavya, an LIC insurance assistant. Help users renew policies and answer claim questions.",
            "greeting_response": "Hello! Welcome to LIC customer service. How can I help with your policy today?",
            "language": "en"
        }

        processor = RealEstateLLMProcessor(turn_state=turn_state, agent_id="lic_agent_101", agent_config=custom_lic_config)
        assert processor.custom_system_prompt == custom_lic_config["script"]
        assert processor.custom_greeting == custom_lic_config["greeting_response"]

        print("SUCCESS: RealEstateLLMProcessor correctly initialized with custom agent config.")

    asyncio.run(_async())


if __name__ == "__main__":
    test_dynamic_agent_creation_and_persistence()
    test_dynamic_agent_llm_turn_execution()
    test_real_estate_llm_processor_with_custom_config()
    print("ALL DYNAMIC AGENTS E2E TESTS PASSED!")
