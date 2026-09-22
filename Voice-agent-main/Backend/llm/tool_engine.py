"""
tool_engine.py — Agent Tools & Function Calling Execution Engine.

File Path: backend/llm/tool_engine.py

Supports built-in tools (end_call, transfer_to_human, collect_information) and
custom HTTP webhook API execution.
"""

from __future__ import annotations

import json
import logging
import os
import time
import requests
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ToolExecutionResult:
    def __init__(self, tool_name: str, success: bool, output: Any, message: str = ""):
        self.tool_name = tool_name
        self.success = success
        self.output = output
        self.message = message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "output": self.output,
            "message": self.message,
            "timestamp": int(time.time() * 1000)
        }


async def execute_agent_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    tool_def: Optional[Dict[str, Any]] = None,
    session_context: Optional[Dict[str, Any]] = None
) -> ToolExecutionResult:
    """
    Executes a requested tool function and returns structured ToolExecutionResult.
    """
    t_name = (tool_name or "").strip().lower()
    session_context = session_context or {}

    logger.info("[TOOL ENGINE] Executing tool '%s' with args: %s", t_name, arguments)

    # 1. Builtin Tool: end_call
    if t_name == "end_call":
        reason = arguments.get("reason", "Conversation completed naturally.")
        return ToolExecutionResult(
            tool_name="end_call",
            success=True,
            output={"session_ended": True, "reason": reason},
            message=f"Call ended by agent: {reason}"
        )

    # 2. Builtin Tool: transfer_to_human
    if t_name in ("transfer_to_human", "transfer"):
        department = arguments.get("department", "support")
        phone_number = arguments.get("phone_number", "")
        return ToolExecutionResult(
            tool_name="transfer_to_human",
            success=True,
            output={"transfer_initiated": True, "department": department, "phone_number": phone_number},
            message=f"Transferring call to human agent in department '{department}'."
        )

    # 3. Builtin Tool: collect_information
    if t_name == "collect_information":
        extracted = arguments.get("slots") or arguments
        return ToolExecutionResult(
            tool_name="collect_information",
            success=True,
            output={"collected_slots": extracted},
            message="Slots collected successfully."
        )

    # 4. Custom HTTP Webhook / API Tool
    if tool_def and tool_def.get("tool_type") == "http_webhook":
        endpoint = tool_def.get("endpoint")
        method = (tool_def.get("method") or "POST").upper()
        headers = tool_def.get("headers") or {"Content-Type": "application/json"}

        if not endpoint:
            return ToolExecutionResult(tool_name=t_name, success=False, output={}, message="Missing endpoint URL")

        try:
            if method == "GET":
                resp = requests.get(endpoint, params=arguments, headers=headers, timeout=5.0)
            else:
                resp = requests.post(endpoint, json=arguments, headers=headers, timeout=5.0)

            resp.raise_for_status()
            res_data = resp.json() if "application/json" in resp.headers.get("Content-Type", "") else {"text": resp.text[:500]}

            return ToolExecutionResult(
                tool_name=t_name,
                success=True,
                output=res_data,
                message=f"Webhook executed successfully with HTTP {resp.status_code}"
            )
        except Exception as exc:
            logger.error("[TOOL ENGINE] HTTP Webhook '%s' failed: %s", t_name, exc)
            return ToolExecutionResult(
                tool_name=t_name,
                success=False,
                output={"error": str(exc)},
                message=f"Webhook execution failed: {exc}"
            )

    return ToolExecutionResult(
        tool_name=t_name,
        success=False,
        output={},
        message=f"Unknown tool '{t_name}'"
    )
