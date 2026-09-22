"""
test_agent_builder.py — Verification test for prompt-first agent generator.
"""

import sys
import os
import asyncio
import pytest

backend_dir = r"s:\voice agent roy\Voice agent R4\Voice-agent-main\backend"
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from agents.agent_builder import generate_agent_config_from_prompt


def test_prompt_first_generator():
    async def _async():
        prompt = "Create an education counselling voice agent for a university named Aarohi."
        config = await generate_agent_config_from_prompt(prompt, client_id="user-123")
        
        assert config.name is not None
        assert config.system_prompt is not None
        assert config.stt.provider == "smallest"
        assert config.tts.provider == "smallest"
        assert config.client_id == "user-123"
        
        legacy = config.to_legacy_dict()
        assert legacy["agent_id"] == config.id
        assert legacy["stt_provider"] == "smallest"

    asyncio.run(_async())
