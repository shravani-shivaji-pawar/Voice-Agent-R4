"""
agent_config_model.py — Canonical Retell-AI Style Agent Configuration Model & Legacy Adapter.

File Path: backend/db/agent_config_model.py

Provides:
  - AgentConfig Pydantic model (canonical platform schema)
  - AgentVersion Pydantic model (published immutable snapshots)
  - STTConfig, LLMConfig, TTSConfig, ToolsConfig, KnowledgeConfig, ConversationSettings sub-models
  - legacy_to_agent_config() & agent_config_to_legacy() adapters to guarantee 100% backward compatibility
    with existing runtime processors (StateManager, RealEstateLLMProcessor, core_voice_loop.py)
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── Canonical Provider Configurations ──────────────────────────────────────────

class STTConfig(BaseModel):
    provider: str = Field("smallest", description="STT provider: canonical 'smallest' (pulse-pro)")
    model: str = Field("pulse-pro", description="STT model name")
    language: str = Field("multi", description="Default language or 'multi' / 'auto'")


class LLMConfig(BaseModel):
    provider: str = Field("groq", description="LLM provider: groq / openai")
    model: str = Field("groq/compound-mini", description="LLM model name")
    temperature: float = Field(0.35, ge=0.0, le=1.0)
    max_tokens: int = Field(100, ge=20, le=2000)
    top_p: float = Field(0.9, ge=0.0, le=1.0)


class TTSConfig(BaseModel):
    provider: str = Field("smallest", description="TTS provider: canonical 'smallest'")
    model: str = Field("lightning_v3.1", description="Smallest AI model: lightning_v3.1 or lightning_v3.1_pro")
    voice: str = Field("emily", description="Selected voice identifier or name")
    voice_id: Optional[str] = Field(None, description="Optional provider voice ID")
    speed: float = Field(1.0, ge=0.5, le=2.0)
    pitch: float = Field(1.0, ge=0.5, le=2.0)


class ToolDefinition(BaseModel):
    id: str = Field(default_factory=lambda: f"tool-{uuid.uuid4().hex[:8]}")
    name: str = Field(..., description="Function name e.g. end_call, transfer_to_human, check_order")
    description: str = Field("", description="Natural language description of what the tool does")
    tool_type: str = Field("builtin", description="builtin | http_webhook | slot_collector")
    endpoint: Optional[str] = Field(None, description="HTTP webhook URL if tool_type == http_webhook")
    method: str = Field("POST", description="HTTP method: GET | POST | PUT")
    headers: Dict[str, str] = Field(default_factory=dict)
    parameters: Dict[str, Any] = Field(default_factory=dict, description="JSON Schema for parameters")
    enabled: bool = Field(True)


class ToolsConfig(BaseModel):
    enabled_builtins: List[str] = Field(
        default_factory=lambda: ["end_call", "transfer_to_human", "collect_information"]
    )
    custom_tools: List[ToolDefinition] = Field(default_factory=list)


class KnowledgeConfig(BaseModel):
    knowledge_base_ids: List[str] = Field(default_factory=list)
    search_top_k: int = Field(3, ge=1, le=10)
    min_score_threshold: float = Field(0.65, ge=0.0, le=1.0)
    require_knowledge_only: bool = Field(False)


class ConversationSettings(BaseModel):
    max_duration_seconds: int = Field(300, ge=30, le=3600)
    interruption_sensitivity: float = Field(0.5, ge=0.0, le=1.0)
    silence_timeout_ms: int = Field(8000, ge=2000, le=30000)
    responsiveness: str = Field("high", description="high | medium | low")
    ambient_noise_cancellation: bool = Field(True)


# ── Main Canonical Agent Model ──────────────────────────────────────────────────

class AgentConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_id: Optional[str] = Field(None, description="Tenant owner client ID")
    name: str = Field(..., description="Display name of the voice agent")
    description: str = Field("", description="Agent overview and domain purpose")
    agent_type: str = Field("education", description="education | real_estate_sales | customer_support | general")
    status: str = Field("Draft", description="Draft | Testing | Published | Archived")
    
    # Prompt & Persona
    system_prompt: str = Field(..., description="System prompt defining identity, instructions, and rules")
    greeting_response: Optional[str] = Field(None, description="Initial spoken greeting")
    language: str = Field("en", description="Primary spoken language: en | hi | mr | hinglish | multi")
    
    # Provider Configurations
    stt: STTConfig = Field(default_factory=STTConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    
    # Capabilities
    knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    settings: ConversationSettings = Field(default_factory=ConversationSettings)
    
    # Conversation Flow Spec (optional visual flow nodes)
    flow_spec: Optional[Dict[str, Any]] = Field(None, description="Legacy/Retell conversation node graph spec")
    
    # Versioning
    published_version_id: Optional[str] = Field(None)
    created_at: int = Field(default_factory=lambda: int(time.time() * 1000))
    updated_at: int = Field(default_factory=lambda: int(time.time() * 1000))

    def to_legacy_dict(self) -> Dict[str, Any]:
        """
        Converts canonical AgentConfig into the exact dictionary schema expected by
        existing runtime modules (StateManager, db_manager, RealEstateLLMProcessor, flows/v2.py).
        """
        global_prompt = self.system_prompt
        nodes = []
        if self.flow_spec and isinstance(self.flow_spec, dict) and "nodes" in self.flow_spec:
            nodes = self.flow_spec["nodes"]
        else:
            # Construct standard 3-node flow from system prompt & greeting if no explicit flow graph
            greeting_text = self.greeting_response or (
                "Hi! I'm your AI counsellor. How can I guide you today?"
                if self.agent_type == "education"
                else "Hello! I'm here to assist you with your property requirements. How can I help you today?"
            )
            nodes = [
                {
                    "id": "node-greeting",
                    "name": "Greeting",
                    "type": "conversation",
                    "response": greeting_text,
                    "instruction": {"type": "prompt", "text": "Greet naturally and ask how you can help."},
                    "intent_triggers": ["call_connected"],
                    "edges": [
                        {
                            "id": "edge-1",
                            "condition": "user speaks",
                            "destination_node_id": "node-discovery",
                            "transition_condition": {"type": "prompt", "prompt": "user shares query or requirement"}
                        }
                    ]
                },
                {
                    "id": "node-discovery",
                    "name": "Discovery",
                    "type": "conversation",
                    "response": "Could you please tell me more about your requirements?",
                    "instruction": {"type": "prompt", "text": "Understand the user's requirement step by step."},
                    "intent_triggers": ["course_discovery", "provide_info", "general_query"],
                    "edges": [
                        {
                            "id": "edge-2",
                            "condition": "details collected",
                            "destination_node_id": "node-qualification",
                            "transition_condition": {"type": "prompt", "prompt": "user provides specific details"}
                        }
                    ]
                },
                {
                    "id": "node-qualification",
                    "name": "Qualification & Next Steps",
                    "type": "conversation",
                    "response": "Thank you for sharing that information. Let me confirm the best next steps for you.",
                    "instruction": {"type": "prompt", "text": "Summarize details and confirm follow-up."},
                    "intent_triggers": ["provide_info", "qualification", "scheduling"],
                    "edges": []
                }
            ]

        domain_val = "education" if self.agent_type in ("education", "aarohi") else "real_estate"

        return {
            "agent_id": self.id,
            "agent_name": self.name,
            "domain": domain_val,
            "agent_type": self.agent_type,
            "channel": "voice",
            "description": self.description,
            "language": self.language,
            "voice": self.tts.voice,
            "voice_id": self.tts.voice_id or self.tts.voice,
            "stt_provider": self.stt.provider,
            "tts_provider": self.tts.provider,
            "smallest_model": self.tts.model,
            "max_call_duration_ms": self.settings.max_duration_seconds * 1000,
            "max_duration": self.settings.max_duration_seconds,
            "interruption_sensitivity": self.settings.interruption_sensitivity,
            "client_id": self.client_id,
            "status": self.status,
            "certification_status": self.status,
            "is_published": self.status == "Published",
            "global_prompt": global_prompt,
            "conversationFlow": {
                "conversation_flow_id": f"flow_{self.id[:8]}",
                "version": 1,
                "global_prompt": global_prompt,
                "nodes": nodes
            },
            "provider_config": {
                "stt_provider": self.stt.provider,
                "tts_provider": self.tts.provider,
                "smallest_model": self.tts.model,
                "voice": self.tts.voice,
            },
            "tools": [t.model_dump() for t in self.tools.custom_tools],
            "enabled_builtins": self.tools.enabled_builtins,
            "knowledge_base_ids": self.knowledge.knowledge_base_ids,
            "last_modification_timestamp": self.updated_at
        }

    @classmethod
    def from_legacy_dict(cls, data: Dict[str, Any]) -> AgentConfig:
        """
        Constructs a canonical AgentConfig from existing database row or JSON schema dictionary.
        """
        agent_id = str(data.get("agent_id") or data.get("id") or uuid.uuid4())
        name = str(data.get("agent_name") or data.get("name") or "AI Voice Agent")
        desc = str(data.get("description") or "")
        agent_type = str(data.get("agent_type") or ("education" if data.get("domain") == "education" else "real_estate_sales"))
        
        # System prompt extraction
        flow_obj = data.get("conversationFlow") or {}
        sys_prompt = str(
            data.get("global_prompt")
            or flow_obj.get("global_prompt")
            or data.get("script")
            or "You are a helpful AI Voice Assistant."
        )

        # STT config
        stt_prov = str(data.get("stt_provider") or data.get("provider_config", {}).get("stt_provider") or "smallest")
        stt_cfg = STTConfig(provider=stt_prov)

        # TTS config
        tts_prov = str(data.get("tts_provider") or data.get("provider_config", {}).get("tts_provider") or "smallest")
        smallest_m = str(data.get("smallest_model") or data.get("provider_config", {}).get("smallest_model") or "lightning_v3.1")
        voice_val = str(data.get("voice") or data.get("provider_config", {}).get("voice") or "emily")
        tts_cfg = TTSConfig(
            provider=tts_prov,
            model=smallest_m,
            voice=voice_val,
            voice_id=data.get("voice_id") or data.get("cartesia_voice_id")
        )

        # Conversation Settings
        max_dur = int(data.get("max_duration") or (data.get("max_call_duration_ms", 300000) // 1000))
        settings_cfg = ConversationSettings(
            max_duration_seconds=max_dur,
            interruption_sensitivity=float(data.get("interruption_sensitivity", 0.5))
        )

        status_val = str(data.get("status") or data.get("certification_status") or "Draft")

        return cls(
            id=agent_id,
            client_id=data.get("client_id"),
            name=name,
            description=desc,
            agent_type=agent_type,
            status=status_val,
            system_prompt=sys_prompt,
            greeting_response=data.get("response") or (flow_obj.get("nodes", [{}])[0].get("response") if flow_obj.get("nodes") else None),
            language=str(data.get("language") or "en"),
            stt=stt_cfg,
            tts=tts_cfg,
            settings=settings_cfg,
            flow_spec=flow_obj if flow_obj.get("nodes") else None,
            created_at=int(data.get("created_at") or data.get("last_modification_timestamp") or (time.time() * 1000)),
            updated_at=int(data.get("updated_at") or data.get("last_modification_timestamp") or (time.time() * 1000)),
        )


# ── Published Agent Version Snapshot ──────────────────────────────────────────

class AgentVersion(BaseModel):
    version_id: str = Field(default_factory=lambda: f"v_{uuid.uuid4().hex[:12]}")
    agent_id: str
    client_id: Optional[str] = None
    version_number: int = Field(1)
    agent_config: AgentConfig
    flow_spec: Optional[Dict[str, Any]] = None
    status: str = Field("Published")
    created_at: int = Field(default_factory=lambda: int(time.time() * 1000))
    published_by: Optional[str] = None
