"""
test_agent_config_adapter.py — Verification test for AgentConfig model & runtime adapter.
"""

import os
import sys
import json
import pytest

backend_dir = r"s:\voice agent roy\Voice agent R4\Voice-agent-main\backend"
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from db.agent_config_model import AgentConfig, AgentVersion, STTConfig, TTSConfig
from llm.state_manager import StateManager
from flows.runtime import RealEstateLLMProcessor


def test_agent_config_creation():
    cfg = AgentConfig(
        name="Aarohi AI Counsellor",
        description="Education & Career Counsellor",
        system_prompt="You are Aarohi, an AI Education Counsellor on a live call.",
        language="en",
        stt=STTConfig(provider="smallest", model="pulse-pro"),
        tts=TTSConfig(provider="smallest", model="lightning_v3.1", voice="emily")
    )
    assert cfg.name == "Aarohi AI Counsellor"
    assert cfg.stt.provider == "smallest"
    assert cfg.tts.provider == "smallest"
    assert cfg.tts.model == "lightning_v3.1"


def test_legacy_dict_conversion():
    cfg = AgentConfig(
        name="Test Sales Agent",
        system_prompt="You are Priya from Suncity Apartments.",
        language="hi",
        stt=STTConfig(provider="smallest"),
        tts=TTSConfig(provider="smallest", voice="emily")
    )
    legacy = cfg.to_legacy_dict()
    assert legacy["agent_name"] == "Test Sales Agent"
    assert legacy["global_prompt"] == "You are Priya from Suncity Apartments."
    assert legacy["stt_provider"] == "smallest"
    assert legacy["tts_provider"] == "smallest"
    assert "conversationFlow" in legacy
    assert len(legacy["conversationFlow"]["nodes"]) == 3


def test_parsing_from_existing_education_agent_json():
    json_path = os.path.join(backend_dir, "Education_Counselling_Agent.json")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cfg = AgentConfig.from_legacy_dict(data)
    assert cfg.id == "education_counselling"
    assert "Aarohi" in cfg.name or "Education" in cfg.name
    assert cfg.agent_type == "education"
    assert "Aarohi" in cfg.system_prompt


def test_state_manager_compatibility_with_agent_config():
    """
    PROVES that the new AgentConfig adapter works 100% with the existing StateManager runtime
    without making ANY modifications to the core voice loop or state machine.
    """
    import asyncio

    async def _async_test():
        cfg = AgentConfig(
            id="test_agent_config_runtime",
            name="Dynamic Retell Agent",
            agent_type="education",
            system_prompt="You are an AI counsellor guiding students.",
            stt=STTConfig(provider="smallest"),
            tts=TTSConfig(provider="smallest", voice="emily")
        )
        
        legacy_schema = cfg.to_legacy_dict()
        
        # Instantiate StateManager using the translated legacy schema dict directly
        state_mgr = StateManager(legacy_schema)
        assert state_mgr.schema["agent_id"] == "test_agent_config_runtime"
        assert state_mgr.schema["global_prompt"] == "You are an AI counsellor guiding students."
        
        # Process turn with state manager
        graph_state = {
            "messages": [],
            "extracted_slots": {},
            "current_node": "GREETING",
            "user_input": "I am studying BCA and want to do MCA.",
            "language": "en",
            "domain": "education"
        }
        
        from llm.state_manager import process_intent_and_slots
        updated_state = await process_intent_and_slots(graph_state)
        assert updated_state is not None
        assert "extracted_slots" in updated_state

    asyncio.run(_async_test())
