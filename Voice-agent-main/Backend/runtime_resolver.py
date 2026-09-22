"""
AgentRuntimeResolver — Single Source of Truth for Voice Agent Runtime Configurations.

Resolves an agent_id to an immutable AgentRuntimeConfig dictionary.
Strictly prevents silent fallbacks to unrelated agent domains (Education, Real Estate, etc.).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from db.db_manager import db

logger = logging.getLogger("runtime_resolver")

BUILTIN_AGENT_IDS = {"education", "education_counselling", "real_estate", "real_estate_sales"}


class AgentRuntimeResolver:
    """Central authority for resolving agent configurations for voice calls and sessions."""

    @staticmethod
    async def resolve(
        agent_id: str,
        client_id: Optional[str] = None,
        mode: str = "published",
    ) -> Dict[str, Any]:
        """
        Resolve agent_id to a standardized, complete AgentRuntimeConfig dictionary.
        
        Args:
            agent_id: Target agent identifier.
            client_id: Optional client ID for tenant ownership validation.
            mode: 'draft' or 'published'.
            
        Returns:
            Dict containing full agent runtime configuration.
            
        Raises:
            ValueError: If agent_id is empty or agent is not found.
            PermissionError: If client_id is supplied and tenant access is unauthorized.
        """
        if not agent_id or not str(agent_id).strip():
            raise ValueError("agent_id must be provided to initialize a voice session.")

        agent_id_str = str(agent_id).strip()
        agent = await db.get_agent(agent_id_str)

        if not agent:
            logger.error("[RUNTIME RESOLVER] Agent not found in DB: agent_id='%s'", agent_id_str)
            raise ValueError(f"Agent configuration '{agent_id_str}' does not exist.")

        # Ownership validation for multi-tenant isolation
        is_global_request = not client_id or str(client_id).lower() in ("default", "global", "admin", "system")
        is_global_agent = not agent.get("client_id") or str(agent.get("client_id")).lower() in ("default", "global", "admin", "system")
        
        if not (is_global_request or is_global_agent or agent_id_str in BUILTIN_AGENT_IDS):
            if agent.get("client_id") != client_id:
                logger.warning(
                    "[RUNTIME RESOLVER] Tenant mismatch: agent_client='%s', request_client='%s'",
                    agent.get("client_id"), client_id
                )
                raise PermissionError(f"Access denied to agent '{agent_id_str}' for tenant '{client_id}'.")

        # Build standardized immutable runtime config object
        system_prompt = (
            agent.get("script") or agent.get("system_prompt") or f"You are {agent.get('name')}, an AI assistant."
        )
        greeting = (
            agent.get("greeting_response")
            or f"Hello! I'm {agent.get('name')}. How can I assist you today?"
        )

        config = {
            "id": agent.get("id") or agent_id_str,
            "agent_id": agent.get("id") or agent_id_str,
            "name": agent.get("name") or "Unnamed Agent",
            "client_id": agent.get("client_id"),
            "system_prompt": system_prompt,
            "script": system_prompt,
            "greeting_response": greeting,
            "greeting": greeting,
            "language": agent.get("language") or "en",
            "voice": agent.get("smallest_voice") or (agent.get("voice") if agent.get("voice") and agent.get("voice") not in ("emily", "default") else "anika"),
            "stt_provider": agent.get("stt_provider") or "smallest",
            "tts_provider": agent.get("tts_provider") or "smallest",
            "agent_type": agent.get("agent_type") or "custom",
            "data_fields": agent.get("data_fields") or [],
            "tools": agent.get("tools") or [],
            "knowledge_base_ids": agent.get("knowledge_base_ids") or [],
            "variables": agent.get("variables") or {},
            "status": agent.get("certification_status") or agent.get("status") or "Draft",
            "version": agent.get("version") or "1.0",
            "is_builtin": agent_id_str in BUILTIN_AGENT_IDS or "Aarohi" in agent.get("name", "") or "Priya" in agent.get("name", ""),
        }

        logger.info(
            "[RUNTIME RESOLVER] Resolved agent_id='%s' name='%s' type='%s' is_builtin=%s",
            config["id"], config["name"], config["agent_type"], config["is_builtin"]
        )
        return config


# Singleton instance alias
agent_resolver = AgentRuntimeResolver()
