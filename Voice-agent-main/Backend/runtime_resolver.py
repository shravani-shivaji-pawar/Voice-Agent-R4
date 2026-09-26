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


def format_applied_website_knowledge(knowledge: dict, source_url: str = "") -> str:
    """Formats raw website intelligence knowledge dictionary into structured LLM context."""
    parts = []
    if source_url:
        parts.append(f"SOURCE WEBSITE: {source_url}")
    
    company = knowledge.get("company") if isinstance(knowledge.get("company"), dict) else {}
    if company.get("name"):
        parts.append(f"COMPANY NAME: {company.get('name')}")
    if company.get("summary"):
        parts.append(f"BUSINESS SUMMARY: {company.get('summary')}")
    if company.get("value_proposition"):
        parts.append(f"VALUE PROPOSITION: {company.get('value_proposition')}")
    if company.get("target_audience"):
        parts.append(f"TARGET AUDIENCE: {company.get('target_audience')}")
        
    services = knowledge.get("products_or_services") or []
    if services:
        s_lines = []
        for s in services:
            if isinstance(s, dict) and s.get("name"):
                desc = f": {s.get('description')}" if s.get('description') else ""
                s_lines.append(f"- {s.get('name')}{desc}")
            elif isinstance(s, str) and s.strip():
                s_lines.append(f"- {s.strip()}")
        if s_lines:
            parts.append("PRODUCTS & SERVICES:\n" + "\n".join(s_lines))
            
    faqs = knowledge.get("faqs") or []
    if faqs:
        f_lines = []
        for f in faqs:
            if isinstance(f, dict) and f.get("question") and f.get("answer"):
                f_lines.append(f"Q: {f.get('question')}\nA: {f.get('answer')}")
        if f_lines:
            parts.append("FREQUENTLY ASKED QUESTIONS:\n" + "\n".join(f_lines))
            
    quals = knowledge.get("qualification_questions") or []
    if quals:
        q_lines = [f"- {q}" for q in quals if isinstance(q, str) and q.strip()]
        if q_lines:
            parts.append("QUALIFICATION QUESTIONS:\n" + "\n".join(q_lines))

    objections = knowledge.get("objections") or []
    if objections:
        o_lines = []
        for o in objections:
            if isinstance(o, dict) and (o.get("intent") or o.get("guidance")):
                o_lines.append(f"- {o.get('intent', 'Objection')}: {o.get('guidance', '')}")
        if o_lines:
            parts.append("OBJECTION HANDLING:\n" + "\n".join(o_lines))

    return "\n\n".join(parts)


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

        # Base prompt setup
        base_prompt = (
            agent.get("script") or agent.get("system_prompt") or f"You are {agent.get('name')}, an AI assistant."
        )

        # Check for applied website knowledge draft strictly belonging to THIS agent_id
        applied_draft = await db.get_latest_applied_script_draft_for_agent(agent_id_str)
        formatted_knowledge = ""
        source_url = ""
        applied_draft_id = None

        if applied_draft:
            knowledge = applied_draft.get("knowledge") if isinstance(applied_draft.get("knowledge"), dict) else {}
            draft_spec = applied_draft.get("draft") if isinstance(applied_draft.get("draft"), dict) else {}
            source_url = (
                knowledge.get("source_url")
                or applied_draft.get("source_url")
                or draft_spec.get("metadata", {}).get("website_intelligence", {}).get("source_url", "")
            )
            applied_draft_id = applied_draft.get("id")
            formatted_knowledge = format_applied_website_knowledge(knowledge, source_url)

        if formatted_knowledge:
            system_prompt = (
                f"{base_prompt}\n\n"
                f"APPLIED WEBSITE KNOWLEDGE:\n"
                f"{formatted_knowledge}\n\n"
                f"RULES FOR WEBSITE KNOWLEDGE:\n"
                f"- Use the applied website knowledge above when answering questions about the company, services, products, or FAQs.\n"
                f"- Do not invent details not present in the website knowledge.\n"
                f"- If the user asks questions outside the website knowledge, preserve your base persona politely.\n"
                f"- Preserve your base persona, language, tone, and conversation flow."
            )
            logger.info(
                "[RUNTIME RESOLVER] Loaded applied website knowledge for agent_id='%s' draft_id='%s' source_url='%s' knowledge_length=%d",
                agent_id_str, applied_draft_id, source_url, len(formatted_knowledge)
            )
        else:
            system_prompt = base_prompt
            logger.info("[RUNTIME RESOLVER] No applied website knowledge found for agent_id='%s'", agent_id_str)

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
            "base_prompt": base_prompt,
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
            "has_applied_website_knowledge": bool(formatted_knowledge),
            "applied_draft_id": applied_draft_id,
            "website_source_url": source_url or None,
            "website_knowledge": formatted_knowledge or None,
        }

        logger.info(
            "[RUNTIME RESOLVER] Resolved agent_id='%s' name='%s' type='%s' is_builtin=%s has_knowledge=%s",
            config["id"], config["name"], config["agent_type"], config["is_builtin"], config["has_applied_website_knowledge"]
        )
        return config


# Singleton instance alias
agent_resolver = AgentRuntimeResolver()

