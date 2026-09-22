"""
test_tools_engine.py — Unit test for tool execution engine.
"""

import sys
import os
import asyncio
import pytest

backend_dir = r"s:\voice agent roy\Voice agent R4\Voice-agent-main\backend"
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from llm.tool_engine import execute_agent_tool


def test_builtin_end_call_tool():
    async def _async():
        res = await execute_agent_tool("end_call", {"reason": "User said goodbye"})
        assert res.success is True
        assert res.output["session_ended"] is True
        assert "goodbye" in res.message

    asyncio.run(_async())


def test_builtin_transfer_tool():
    async def _async():
        res = await execute_agent_tool("transfer_to_human", {"department": "sales"})
        assert res.success is True
        assert res.output["transfer_initiated"] is True
        assert res.output["department"] == "sales"

    asyncio.run(_async())
