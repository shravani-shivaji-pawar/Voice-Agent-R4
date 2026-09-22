"""
agent_builder.py — Natural-Language Prompt-First Agent Builder Engine.

File Path: backend/agents/agent_builder.py

Takes a user's high-level natural language prompt (e.g. "Create an education counsellor agent..."),
calls Groq LLM, and produces a complete, normalized, Retell-style AgentConfig object.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, Dict

from db.agent_config_model import (
    AgentConfig,
    ConversationSettings,
    KnowledgeConfig,
    LLMConfig,
    STTConfig,
    ToolDefinition,
    ToolsConfig,
    TTSConfig,
)
from llm.llm import _call_groq_with_retry, cfg

logger = logging.getLogger(__name__)

PROMPT_BUILDER_SYSTEM = """You are an expert Voice AI Agent Architect.
Your task is to take a user's natural language request describing an AI voice agent and generate a complete, professional, highly structured Agent Configuration JSON.

Rules for Spoken Voice Prompts:
1. Write a clear, conversational, high-performing System Prompt for a live voice phone call.
2. The agent should be warm, concise, and natural (15-25 words per turn).
3. Specify clear discovery questions, tone, and escalation rules.
4. Pick an appropriate agent_type ("education", "real_estate_sales", "customer_support", or "general").
5. Pick an appropriate primary language ("en", "hi", "mr", "hinglish", or "multi").
6. Pick an appropriate initial greeting response.
7. Recommend a compatible Smallest AI voice ("anika", "devansh", "divya", "karan", "meher", "arav", "emily", "rachel").

Respond ONLY with a valid JSON object matching this schema:
{
  "name": "Short Agent Name",
  "description": "One sentence summary of purpose",
  "agent_type": "education | real_estate_sales | customer_support | general",
  "language": "en | hi | mr | hinglish | multi",
  "system_prompt": "Complete, detailed system prompt for the voice LLM",
  "greeting_response": "Natural initial spoken greeting",
  "recommended_voice": "anika | devansh | divya | meher | arav | emily",
  "recommended_model": "lightning_v3.1 | lightning_v3.1_pro",
  "suggested_builtins": ["end_call", "transfer_to_human", "collect_information"]
}
Do not return markdown, ticks, or text explanations outside the JSON.
"""


async def generate_agent_config_from_prompt(user_prompt: str, client_id: str | None = None) -> AgentConfig:
    """
    Parses natural-language user prompt into a complete AgentConfig object.
    """
    if not user_prompt or not user_prompt.strip():
        user_prompt = "Create a friendly customer support voice agent."

    messages = [
        {"role": "system", "content": PROMPT_BUILDER_SYSTEM},
        {"role": "user", "content": f"User Request: {user_prompt.strip()}"}
    ]

    try:
        raw = await _call_groq_with_retry(
            messages=messages,
            model_name=getattr(cfg, "MODEL_NAME", "groq/compound-mini"),
            max_tokens=600,
            temperature=0.3,
            max_attempts=2
        )
        clean_json = raw.strip()
        if clean_json.startswith("```"):
            clean_json = clean_json.strip("`").removeprefix("json").strip()
        parsed = json.loads(clean_json)
    except Exception as exc:
        logger.warning("Groq prompt builder call failed: %s; using smart fallback generator.", exc)
        parsed = {
            "name": "AI Voice Agent",
            "description": user_prompt[:80],
            "agent_type": "general",
            "language": "en",
            "system_prompt": f"You are a professional AI voice assistant. Primary instructions: {user_prompt}",
            "greeting_response": "Hello! How can I assist you today?",
            "recommended_voice": "emily",
            "recommended_model": "lightning_v3.1",
            "suggested_builtins": ["end_call", "transfer_to_human", "collect_information"]
        }

    agent_id = f"agent-{uuid.uuid4().hex[:12]}"
    rec_voice = parsed.get("recommended_voice") or "anika"
    rec_model = parsed.get("recommended_model") or "lightning_v3.1"
    builtins = parsed.get("suggested_builtins") or ["end_call", "transfer_to_human", "collect_information"]

    return AgentConfig(
        id=agent_id,
        client_id=client_id,
        name=parsed.get("name") or "AI Voice Agent",
        description=parsed.get("description") or "",
        agent_type=parsed.get("agent_type") or "general",
        status="Draft",
        system_prompt=parsed.get("system_prompt") or f"You are a helpful AI voice assistant. {user_prompt}",
        greeting_response=parsed.get("greeting_response") or "Hello! How can I help you today?",
        language=parsed.get("language") or "en",
        stt=STTConfig(provider="smallest", model="pulse-pro", language=parsed.get("language") or "en"),
        llm=LLMConfig(provider="groq", model="groq/compound-mini"),
        tts=TTSConfig(provider="smallest", model=rec_model, voice=rec_voice),
        knowledge=KnowledgeConfig(),
        tools=ToolsConfig(enabled_builtins=builtins),
        settings=ConversationSettings(max_duration_seconds=300)
    )
