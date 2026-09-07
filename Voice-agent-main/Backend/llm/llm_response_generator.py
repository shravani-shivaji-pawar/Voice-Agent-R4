"""LLM-powered spoken response generator — the SOLE response path.

Architecture:
    STT → Intent Extraction → StateManager (transitions ONLY) → LLMResponseGenerator (responses ONLY) → TTS

This module is the ONLY place that generates spoken responses.
StateManager handles transitions and returns a TurnResult.
This module takes that TurnResult and produces the spoken text.

Design:
    - JSON phrases = guidance (style + vocabulary)
    - LLM = sentence construction (final output)
    - Template fill = fast path for predictable nodes (greeting, goodbye)
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ─── TurnResult: what StateManager returns after a transition ──────────────────

@dataclass
class TurnResult:
    """Structured output from StateManager after executing a state transition.

    StateManager produces this. LLMResponseGenerator consumes it.
    """
    node: dict[str, Any]            # The resolved node after transition
    node_id: str = ""               # Node ID shortcut
    context: dict[str, Any] = field(default_factory=dict)  # Conversation data
    user_input: str = ""            # What the user said
    language: str = "en"            # Detected language
    is_terminal: bool = False       # Conversation ended
    user_question: Optional[str] = None  # "identity" | "purpose" | "confusion" | None
    response_type: str = "normal"   # "normal" | "noise_repeat" | "deescalation" | "greeting"
    asked_flags: dict[str, bool] = field(default_factory=dict)  # What has been asked already
    recent_responses: list[str] = field(default_factory=list)   # Previous agent responses (for anti-repetition)
    node_changed: bool = False      # True if a state transition occurred (skip LLM, use template)

    def __post_init__(self):
        if not self.node_id:
            self.node_id = str(self.node.get("id", ""))


# ─── Load the response system prompt ──────────────────────────────────────────

def _load_response_prompt() -> str:
    prompt_path = Path(__file__).resolve().parent / "response_prompt.txt"
    try:
        return prompt_path.read_text(encoding="utf-8").strip()
    except Exception as exc:
        logger.warning("Could not load response_prompt.txt: %s", exc)
        return ""


_RESPONSE_SYSTEM_PROMPT: str = _load_response_prompt()


# ─── Node classification ─────────────────────────────────────────────────────

# Nodes where the LLM generates dynamic responses using JSON phrases as guidance.
# The State Manager strictly handles transitions, while these nodes use LLM for wording.
_LLM_RESPONSE_NODES = {
    "node-1735264921453",      # Ask Intent
    "fallback_intent",
    "node-1735267546732",      # Ask Location & Budget
    "fallback_location",
    "fallback_budget",
    "node-1736323961832",      # Share Property
    "node-1735265015507",      # Site Visit Time
    "fallback_visit_datetime",
    "node-1736492391269",      # Callback Scheduling
    "fallback_callback_time",
    "node-objection-not-looking"
}

# Nodes that always use fast template responses (no LLM call needed)
_TEMPLATE_ONLY_NODES = {
    "node-1767592854176",       # Smart Greeting
    "node-1735264873079",       # Availability Check
    "node-1735265209472",       # Save Lead & Confirm
    "node-1736567518748",       # Confirm Callback
    "node-1736492485610",       # Polite Goodbye
    "node-1736492925252",       # Confirm and End
    "node-1735969972303",       # End Conversation
    "node-1736492520068",       # Immediate End Call
    "node-wrong-person-end",    # Wrong Person End
}


def is_llm_node(node: dict[str, Any]) -> bool:
    node_id = node.get("id")
    if node_id in _LLM_RESPONSE_NODES:
        return True
    if node.get("collects"):
        return True
    if node.get("type") == "fallback":
        return True
    return False


def _classify_node_goal(node: dict[str, Any], state_manager: Optional[Any] = None) -> str:
    """Classify the current node's goal for the LLM prompt using structured mapping."""
    node_id = str(node.get("id") or "")
    
    if state_manager and state_manager.schema.get("agent_type", "real_estate_sales") == "real_estate_sales":
        from .state_manager import NODE_GOALS
        goal = NODE_GOALS.get(node_id)
        if goal:
            # Contextual refinement for combined nodes
            if node_id == "node-1735267546732":
                loc = state_manager.conversation_data.get("location")
                bud = state_manager.conversation_data.get("budget")
                if loc and not bud:
                    return "ask_budget"
                return "ask_location"
            return goal

    # Dynamic goal classification
    instruction = node.get("instruction", {})
    instruction_text = ""
    if isinstance(instruction, dict):
        instruction_text = instruction.get("text", "")
    elif isinstance(instruction, str):
        instruction_text = instruction
        
    if instruction_text:
        return instruction_text

    collects = node.get("collects") or []
    if collects:
        return f"Collect the following fields from the user: {', '.join(collects)}."

    if node.get("type") == "end":
        return "Thank the user and end the call."
    if node.get("type") == "fallback":
        return "Clarify the previously requested information."

    return "Conversational turn."


# ─── Phrase extraction from nodes ─────────────────────────────────────────────

def _extract_node_phrases(node: dict[str, Any]) -> list[str]:
    """Extract all relevant phrases from a conversation node for LLM guidance."""
    phrases: list[str] = []

    resp = node.get("response")
    if isinstance(resp, str) and resp.strip():
        phrases.append(resp.strip())

    msr = node.get("missing_slot_responses")
    if isinstance(msr, dict):
        for v in msr.values():
            if isinstance(v, str) and v.strip():
                phrases.append(v.strip())

    instruction = node.get("instruction", {})
    if isinstance(instruction, dict):
        text = instruction.get("text", "")
        if isinstance(text, str) and text.strip():
            phrases.append(text.strip())

    return phrases


# ─── User message building ───────────────────────────────────────────────────

def _build_llm_user_message(
    *,
    node_id: str,
    node_goal: str,
    json_phrases: list[str],
    context_data: dict[str, Any],
    user_input: str,
    language: str,
    asked_flags: dict[str, bool] | None = None,
    recent_responses: list[str] | None = None,
) -> str:
    """Build the user message matching the clean prompt format."""
    phrases_block = "\n".join(f"- {p}" for p in json_phrases) if json_phrases else "(none)"
    
    # Dynamically build the context fields block
    context_lines = []
    for k, v in context_data.items():
        if k in {"memory", "asked_flags", "recent_responses", "active_language"}:
            continue
        context_lines.append(f"  {k}: {v or 'None'}")
    context_block = "\n".join(context_lines)
    
    recent_str = "\n".join(f"  - {r}" for r in (recent_responses or [])[-2:]) if recent_responses else "  None"
    
    return (
        f"current_node: {node_id}\n"
        f"node_goal: {node_goal}\n"
        f"json_phrases:\n{phrases_block}\n\n"
        f"context:\n"
        f"{context_block}\n"
        f"  language: {language}\n\n"
        f"ALREADY ASKED / RECENT AGENT RESPONSES:\n{recent_str}\n\n"
        f"user_input: \"{user_input}\""
    )


# ─── User question handling (structured, no LLM needed) ──────────────────────

def _answer_user_question(question_type: str, language: str, state_manager: Optional[Any] = None) -> str:
    """Return a brief answer to a user's meta-question (identity, purpose, confusion)."""
    agent_name = "Agent"
    agent_type = "real_estate_sales"
    global_prompt = ""
    if state_manager:
        agent_name = state_manager.schema.get("agent_name", "Agent")
        agent_type = state_manager.schema.get("agent_metadata", {}).get("agent_type") or state_manager.schema.get("agent_type") or "real_estate_sales"
        global_prompt = (state_manager.global_prompt or state_manager.schema.get("global_prompt", "")) if hasattr(state_manager, "global_prompt") else state_manager.schema.get("global_prompt", "")

    type_label = {
        "real_estate_sales": "Real Estate team",
        "finance": "Finance advisory team",
        "insurance": "Insurance advisory team",
        "education": "Education counselling team",
        "recruitment": "Recruitment team",
        "healthcare": "Healthcare team",
    }.get(agent_type)
    if not type_label:
        if "sales" in agent_type.lower():
            type_label = "Sales team"
        elif "advisory" in agent_type.lower() or "advisor" in agent_type.lower():
            type_label = "Advisory team"
        else:
            type_label = "Customer support team"

    purpose_desc = "following up on your request"
    if agent_type == "healthcare" or "clinic" in global_prompt.lower() or "doctor" in global_prompt.lower():
        purpose_desc = "scheduling your doctor's appointment"
    elif agent_type == "recruitment" or "job application" in global_prompt.lower():
        purpose_desc = "your job application"
    elif agent_type == "real_estate_sales" or "property" in global_prompt.lower() or "real estate" in global_prompt.lower():
        purpose_desc = "your property interest"
    elif agent_type == "education" or "course interest" in global_prompt.lower() or "admission" in global_prompt.lower():
        purpose_desc = "your course inquiry"

    if language in ("hi", "hinglish"):
        if question_type == "identity":
            return f"{agent_name} bol rahi hoon, {type_label} se."
        if question_type == "purpose":
            return f"Aapke {purpose_desc} ke baare mein call kiya hai."
        return "Thoda clear bolenge?"
    if language == "mr":
        if question_type == "identity":
            return f"{agent_name} बोलतेय, {type_label} मधून."
        if question_type == "purpose":
            return f"तुमच्या {purpose_desc} बद्दल call केला आहे."
        return "थोडं clear सांगाल का?"
    # English
    if question_type == "identity":
        return f"This is {agent_name} calling from the {type_label}."
    if question_type == "purpose":
        return f"I am calling regarding {purpose_desc}."
    return "Could you say that differently?"


# ─── Template response (fast path for predictable nodes) ─────────────────────

def _resolve_template_response(
    node: dict[str, Any],
    context: dict[str, Any],
    language: str,
) -> str:
    """Fill {{placeholders}} in a node's template response. Fast path, no LLM."""
    from .language_utils import localize_template

    collects = node.get("collects")
    if not collects:
        collects = []
    elif isinstance(collects, str):
        collects = [collects]
    elif not isinstance(collects, list):
        collects = list(collects)
    
    missing_slots = [s for s in collects if not context.get(s)]
    template = ""
    
    # If partially filled (we have some slots collected, but not all)
    if 0 < len(missing_slots) < len(collects):
        msr = node.get("missing_slot_responses", {})
        target_slot = missing_slots[0]
        template = msr.get(target_slot, "")
        
        # Add a natural acknowledgment for the slot that WAS provided
        if template:
            filled_slots = [s for s in collects if context.get(s)]
            if filled_slots:
                last_filled = filled_slots[-1]
                val = context.get(last_filled)
                if language in ("hi", "hinglish"):
                    ack = f"Theek hai, {val}."
                elif language == "mr":
                    ack = f"ठीक आहे, {val}."
                else:
                    ack = f"Got it — {val}."
                template = f"{ack} {template}"

    if not template:
        template = node.get("response", "")
    if not template:
        template = (node.get("instruction") or {}).get("text", "")
    if not template:
        return ""

    def fill(match: re.Match[str]) -> str:
        key = match.group(1)
        if key == "name":
            val = context.get("name") or context.get("lead_name") or context.get("lead") or "Prashant"
        else:
            val = context.get(key)
        
        # Entity safety: DO NOT use "null" in response
        if str(val).lower() == "null":
            return ""
            
        return str(val) if val else ""

    localized = localize_template(template, language)
    resolved = re.sub(r"\{\{(\w+)\}\}", fill, localized).strip()
    resolved = re.sub(r" +", " ", resolved)
    return resolved


# ─── Response finalization ───────────────────────────────────────────────────

_FILLER_OPENERS = (
    "sure,", "sure -", "sure —", "sure.",
    "great,", "great -", "great —", "great.",
    "absolutely,", "absolutely -", "absolutely —",
    "certainly,", "certainly -", "certainly —",
    "wonderful,", "wonderful -", "wonderful —",
    "understood,", "understood -", "understood —",
)


def _finalize_response(text: str) -> str:
    """Apply production constraints: max 2 sentences, 30 words (sentence-boundary-aware), 1 question, no fillers, complete sentences."""
    if not text or not text.strip():
        return text

    cleaned = text.strip()

    # Strip accidental JSON/markdown/label formatting
    if (cleaned.startswith('"') and cleaned.endswith('"')) or \
       (cleaned.startswith("'") and cleaned.endswith("'")):
        cleaned = cleaned[1:-1].strip()
    cleaned = re.sub(
        r"^(?:response|output|answer|reply)\s*[:—-]\s*",
        "", cleaned, flags=re.IGNORECASE,
    ).strip()

    # Collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Max 2 sentences
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", cleaned) if p.strip()]
    if len(parts) > 2:
        parts = parts[:2]
    cleaned = " ".join(parts)

    # Single question mark
    if cleaned.count("?") > 1:
        first = cleaned.find("?")
        cleaned = cleaned[:first + 1] + cleaned[first + 1:].replace("?", ".")

    # Max 30 words — truncate to nearest complete sentence boundary
    words = cleaned.split()
    if len(words) > 30:
        # Find the last sentence-ending punctuation within the first 30 words
        truncated = " ".join(words[:30])
        last_period = max(truncated.rfind("."), truncated.rfind("?"), truncated.rfind("!"))
        if last_period > 10:  # Found a sentence boundary
            cleaned = truncated[:last_period + 1]
        else:
            # No good boundary found — hard cut at 25 words and add punctuation
            cleaned = " ".join(words[:25]).rstrip(" ,;:-")
            if "?" in truncated:
                cleaned = cleaned.rstrip(".") + "?"
            else:
                cleaned = cleaned.rstrip(".") + "."
        words = cleaned.split()

    # ── Completeness validation (HARD CONSTRAINT) ─────────────────────
    # Strip trailing connectors that signal an incomplete sentence
    _trailing = {"and", "or", "but", "to", "for", "with", "the", "a", "an",
                 "is", "are", "in", "on", "at", "of", "so", "—", "-",
                 "it's", "let", "me", "that", "like"}
    while words and words[-1].lower().rstrip(".,;:-—") in _trailing:
        words.pop()

    if not words:
        return ""

    cleaned = " ".join(words)

    # Ensure terminal punctuation
    if cleaned and cleaned[-1] not in ".!?":
        question_starters = ("what", "which", "where", "when", "how", "who",
                             "are", "is", "do", "does", "can", "could", "would",
                             "kya", "kahan", "kaun", "kab", "kitna")
        if words[0].lower() in question_starters:
            cleaned += "?"
        else:
            cleaned += "."

    return cleaned


def build_response_system_prompt(state_manager: Optional[Any], language: str) -> str:
    """Build response generation system prompt dynamically based on the active agent config."""
    if not state_manager:
        return _RESPONSE_SYSTEM_PROMPT

    agent_name = state_manager.schema.get("agent_name", "Agent")
    agent_type = state_manager.schema.get("agent_type", "real_estate_sales")
    global_prompt = state_manager.global_prompt or state_manager.schema.get("global_prompt") or "You are a helpful AI assistant."
    
    prompt_builder = []
    prompt_builder.append("## IDENTITY & AUTHORITATIVE SCRIPT")
    prompt_builder.append(f"Agent Name: {agent_name}")
    prompt_builder.append(f"Agent Type/Industry: {agent_type}")
    prompt_builder.append(f"Primary Agent Script/Behavior definition:\n{global_prompt}\n")
    
    prompt_builder.append("## DATA EXTRACTION SCHEMAS & CURRENT SLOT STATUS")
    prompt_builder.append("You are currently tracking these extraction fields. If a field has a value, do NOT ask for it again.")
    for field in state_manager.extraction_fields:
        val = state_manager.conversation_data.get(field)
        status = f"COLLECTED (value: {val})" if val else "MISSING (needs collection)"
        prompt_builder.append(f"- {field}: {status}")
    prompt_builder.append("")
    prompt_builder.append("Do not ask about anything listed under ALREADY KNOWN or ALREADY ASKED in the context. If the caller ignored a question you already asked, acknowledge that gently and move to the next open item instead of repeating it verbatim.")
    prompt_builder.append("")

    from .language_utils import get_language_instruction
    lang_inst = get_language_instruction(language)
    prompt_builder.append("## LANGUAGE RULES")
    prompt_builder.append(f"Active Language: {language}")
    prompt_builder.append(f"{lang_inst}\n")

    prompt_builder.append("## RESPONSE GOVERNANCE & CONSTRAINTS")
    prompt_builder.append("- Answer the user's question or acknowledge input logically first, then advance to the next step.")
    prompt_builder.append("- DYNAMIC RESPONSE VARIATION: Use unique opening phrases, varied vocabulary, and distinct sentence structures for every turn. Never output duplicate response patterns.")
    prompt_builder.append("- PROFESSIONAL & POLITE STYLE: Use clear, polite, and professional phrasing. Avoid excessive casual slang, chat-style jargon, or filler hesitations like 'Umm', 'Like', 'Wait'.")
    prompt_builder.append("- Max 2 sentences.")
    prompt_builder.append("- Max 20-30 words.")
    prompt_builder.append("- Ask exactly ONE question matching the current node's missing slots.")
    prompt_builder.append("- Avoid repetition. Never repeat the previous question if you have already got the answer.")
    prompt_builder.append("- STRICT TRUTH AND ANTI-HALLUCINATION RULE: NEVER assume, guess, invent, or hallucinate any facts, details, locations, amenities, pricing, timeline, or specifications. You are strictly allowed to use facts explicitly mentioned in the 'Primary Agent Script' or 'json_phrases'.")
    prompt_builder.append("- MISSING INFORMATION FALLBACK: If the user asks a question about details not explicitly provided in your prompt or script (such as specific flat sizes, amenities, project launch dates, interest rates, or doctor degrees), you MUST say: 'I don't have that detail right now, but I can check and have our advisor get back to you.' (or localized equivalent), and then immediately proceed to the current node goal.")
    prompt_builder.append("- Plain text only. No JSON, no markdown, no conversational role labels.")
    
    return "\n".join(prompt_builder)


# ─── LLM call ────────────────────────────────────────────────────────────────

async def _call_llm_for_response(
    node: dict[str, Any],
    *,
    context_data: dict[str, Any],
    user_input: str,
    language: str,
    asked_flags: dict[str, bool] | None = None,
    recent_responses: list[str] | None = None,
    state_manager: Optional[Any] = None,
) -> str:
    """Call the LLM to generate a response using JSON phrases as guidance.

    Includes regeneration loop for deduping against recent responses.
    Returns empty string on failure (caller should fall back to template).
    """
    from . import config as cfg
    from .llm import _async_call_groq_api
    import difflib

    system_prompt = build_response_system_prompt(state_manager, language)
    json_phrases = _extract_node_phrases(node)
    node_goal = _classify_node_goal(node, state_manager=state_manager)

    user_message = _build_llm_user_message(
        node_id=str(node.get("id", "")),
        node_goal=node_goal,
        json_phrases=json_phrases,
        context_data=context_data,
        user_input=user_input,
        language=language,
        asked_flags=asked_flags,
        recent_responses=recent_responses,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    logger.info(
        "[LLM RESPONSE] Generating for node=%s goal=%s user=\"%s\"",
        node.get("id", "?"), node_goal, (user_input or "")[:60],
    )

    max_attempts = 2
    raw = ""
    for attempt in range(max_attempts):
        try:
            raw = await _async_call_groq_api(
                messages,
                max_tokens=cfg.PHRASE_RESPONSE_MAX_TOKENS,
                temperature=cfg.PHRASE_RESPONSE_TEMPERATURE if attempt == 0 else 0.8,
            )
        except Exception as exc:
            logger.error("[LLM RESPONSE] API error on attempt %d: %s", attempt+1, exc)
            return ""

        if not raw or not raw.strip():
            logger.warning("[LLM RESPONSE] Empty LLM output on attempt %d", attempt+1)
            return ""

        raw = raw.strip()
        
        # Check against recent responses using fuzzy comparison of opening clauses
        is_repetitive = False
        if recent_responses:
            new_opening = " ".join(raw.split()[:5]).lower()
            for recent in recent_responses[-2:]:
                recent_opening = " ".join(recent.split()[:5]).lower()
                similarity = difflib.SequenceMatcher(None, new_opening, recent_opening).ratio()
                if similarity > 0.8:
                    is_repetitive = True
                    break
        
        if is_repetitive and attempt < max_attempts - 1:
            logger.warning("[LLM RESPONSE] Dedup check failed, regenerating...")
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": "Vary your phrasing. Do not repeat your last opening."})
            continue
        elif is_repetitive:
            logger.warning("[LLM RESPONSE] Regeneration still too similar, falling back")
            return ""
        
        break # Exit loop if not repetitive

    words = raw.split()
    
    # ── Response Validator ──
    if len(words) < 3:
        logger.warning(f"[RESPONSE VALIDATOR] Rejected: Too short ({len(words)} words): '{raw}'")
        return ""
    
    # Check for cut-off sentence (no ending punctuation but long)
    if raw[-1] not in ".!?\"'" and len(words) > 10:
        logger.warning(f"[RESPONSE VALIDATOR] Rejected: Incomplete/Cut-off sentence: '{raw}'")
        return ""

    return raw


# ─── Main entry point: generate response for a TurnResult ────────────────────

async def generate_response_for_turn(turn: TurnResult, state_manager: Optional[Any] = None) -> str:
    """Generate the final spoken response for a completed state transition.

    This is the SOLE response generation path. Called by the pipeline orchestrator.

    Routing:
    1. User question → structured answer + node continuation
    2. LLM response nodes → LLM generates using JSON phrases as guidance
    3. Template nodes → fast {{placeholder}} fill
    4. Fallback → node template if LLM fails
    """
    node = turn.node
    node_id = turn.node_id
    context = turn.context
    user_input = turn.user_input
    language = turn.language
    asked_flags = turn.asked_flags
    last_response = turn.last_response

    # ── Path 1: User is asking a meta-question ────────────────────────────
    if turn.user_question:
        answer = _answer_user_question(turn.user_question, language, state_manager=state_manager)

        # If the node goal needs a follow-up question, generate it via LLM
        if is_llm_node(node):
            follow_up = await _call_llm_for_response(
                node,
                context_data=context,
                user_input=f"[User asked: {turn.user_question}] {user_input}",
                language=language,
                asked_flags=asked_flags,
                recent_responses=turn.recent_responses,
                state_manager=state_manager,
            )
            if follow_up:
                combined = f"{answer} {_finalize_response(follow_up)}"
                logger.info("[LLM RESPONSE] Question+Continue: \"%s\"", combined)
                return _finalize_response(combined)

        # Fallback: answer + template
        template = _resolve_template_response(node, context, language)
        if template:
            combined = f"{answer} {template}"
            return _finalize_response(combined)
        return _finalize_response(answer)

    # ── Path 2: Noise / non-actionable input → repeat current node ────────
    if turn.response_type == "noise_repeat":
        response = _resolve_template_response(node, context, language)
        logger.info("[TEMPLATE] Noise repeat for %s", node_id)
        return _finalize_response(response) if response else ""

    # ── Path 3: Deescalation (hostile input) ──────────────────────────────
    if turn.response_type == "deescalation":
        from .state_manager import DEESCALATION_RESPONSES
        idx = hash(user_input) % len(DEESCALATION_RESPONSES)
        return DEESCALATION_RESPONSES[idx]

    # ── Path 4: LLM-powered response for qualification/fallback nodes ─────
    # ONLY use LLM when staying on the same node (needs clarification/rephrasing).
    # If the node changed (user answered correctly), skip LLM and use template directly.
    if is_llm_node(node) and not turn.node_changed:
        llm_response = await _call_llm_for_response(
            node,
            context_data=context,
            user_input=user_input,
            language=language,
            asked_flags=asked_flags,
            recent_responses=turn.recent_responses,
            state_manager=state_manager,
        )
        if llm_response:
            finalized = _finalize_response(llm_response)
            if finalized:
                _log_phrase_usage(finalized)
                logger.info("[LLM RESPONSE] \"%s\"", finalized)
                return finalized
        # LLM failed → fall through to template
        logger.warning("[LLM RESPONSE] Falling back to template for %s", node_id)
    elif is_llm_node(node) and turn.node_changed:
        logger.info("[SKIP LLM] Node changed, using template directly for %s", node_id)

    # ── Path 5: Template response (fast path) ────────────────────────────
    # ISSUE 5 FIX: Suppress all anti-repeat guards and nudges for terminal states.
    # Ensure the conversation gracefully ends with the designated goodbye template.
    if turn.is_terminal:
        response = _resolve_template_response(node, context, language)
        finalized = _finalize_response(response) if response else ""
        logger.info("[TERMINAL RESPONSE] %s: \"%s\"", node_id, finalized)
        return finalized

    if node_id in {"fallback_location", "fallback-city"} and _is_location_suggestion_request(user_input):
        return _location_suggestion_response(language, state_manager)

    response = _resolve_template_response(node, context, language)
    finalized = _finalize_response(response) if response else ""
    
    if finalized and turn.recent_responses and _is_repetition(finalized, turn.recent_responses[-1]):
        logger.warning("[ANTI-REPEAT] Template repeated last response, generating nudge instead")
        nudge = _get_anti_repeat_nudge(node, language, context=context)
        if nudge:
            return nudge

    # H7 FIX: Guaranteed fallback if response generation completely fails or anti-repeat yields nothing
    if not finalized:
        logger.warning("[FALLBACK] Generating guaranteed minimal fallback response")
        if language in ("hi", "hinglish"):
            finalized = "Maaf karna, aawaz thodi cut rahi thi. Kya aap dubara batayenge?"
        elif language == "mr":
            finalized = "Aawaz thodi tutat hoti, krupaya parat sangal ka?"
        else:
            finalized = "I didn't quite catch that. Could you repeat?"

    logger.info("[TEMPLATE] %s: \"%s\"", node_id, finalized[:60] if finalized else "")
    return finalized


def _is_location_suggestion_request(user_input: str) -> bool:
    text = re.sub(r"[^\w\s]", " ", (user_input or "").lower())
    text = re.sub(r"\s+", " ", text).strip()
    hints = (
        "suggest", "recommend", "which city", "which area", "best location",
        "good location", "cities", "areas", "options", "offer me",
        "can you offer", "what can you offer",
    )
    return any(hint in text for hint in hints)


def _get_suggested_locations(state_manager: Optional[Any]) -> list[str]:
    if not state_manager or not hasattr(state_manager, "schema"):
        return ["Wakad", "Baner", "Hinjewadi", "Kharadi"]
    
    schema = state_manager.schema
    if not schema:
        return ["Wakad", "Baner", "Hinjewadi", "Kharadi"]

    by_city = schema.get("project_quick_reference", {}).get("by_city")
    if by_city and isinstance(by_city, dict):
        return list(by_city.keys())
        
    projects = schema.get("all_projects", [])
    if projects and isinstance(projects, list):
        cities = set()
        for p in projects:
            city = p.get("location", {}).get("city")
            if city:
                cities.add(city)
        if cities:
            return sorted(list(cities))
            
    return ["Wakad", "Baner", "Hinjewadi", "Kharadi"]


def _location_suggestion_response(language: str, state_manager: Optional[Any] = None) -> str:
    locs = _get_suggested_locations(state_manager)
    locs_str = ", ".join(locs[:-1]) + f", or {locs[-1]}" if len(locs) > 1 else locs[0]
    
    if language in ("hi", "hinglish"):
        if "Wakad" in locs:
            return f"Aap {', '.join(locs[:-1])} ya {locs[-1]} consider kar sakte ho. Inmein se kaunsa area better lagega?"
        else:
            return f"Aap {', '.join(locs[:-1])} ya {locs[-1]} dekh sakte hain. Aapko kaunsa city prefer hoga?"
    if language == "mr":
        if "Wakad" in locs:
            return f"{', '.join(locs[:-1])} ani {locs[-1]} changle options aahet. Tyapeki konta area jasta suit hoil?"
        else:
            return f"{', '.join(locs[:-1])} ani {locs[-1]} options aahet. Tyapeki konta city prefer ahe?"
    
    if "Wakad" in locs:
        return f"You can consider {locs_str}. Which area sounds closest?"
    else:
        return f"You can consider {locs_str}. Which city are you looking at?"


def _get_anti_repeat_nudge(node: dict[str, Any], language: str, context: Optional[dict] = None) -> str:
    """Generate a short contextual nudge when the LLM repeats itself.

    Instead of falling back to a template with potentially missing placeholders,
    produce a clean, short follow-up based on the node's goal.
    """
    node_id = str(node.get("id", ""))
    
    # Classify the node goal
    goal = _classify_node_goal(node)

    # Goal-specific nudges (English defaults)
    nudges = {
        "share_property": "Would you like to see it in person?",
        "ask_intent": "Are you looking to buy or rent?",
        "ask_location": "Which area works best for you?",
        "ask_budget": "What budget range works for you?",
        "ask_visit_time": "Would a weekend or weekday work better?",
        "ask_availability": "Do you have a couple of minutes right now?",
        "handle_objection": "Would you be open to hearing about other options?",
    }

    nudge = nudges.get(goal, "")
    if not nudge:
        # Dynamic missing slot nudge
        collects = node.get("collects") or []
        if isinstance(collects, str):
            collects = [collects]
        missing = [s for s in collects if not context or not context.get(s)]
        if missing:
            slot = missing[0]
            if language in ("hi", "hinglish"):
                return f"Aapka {slot} kya hai?"
            elif language == "mr":
                return f"तुमचा {slot} काय आहे?"
            else:
                return f"Could you share your {slot}?"
        nudge = "Would you like to know more?"

    # Basic language adaptation
    if language in ("hi", "hinglish"):
        hi_nudges = {
            "share_property": "Kya aap ise personally dekhna chahenge?",
            "ask_intent": "Aap buy karna chahte ho ya rent?",
            "ask_location": "Kaun sa area prefer karenge?",
            "ask_budget": "Roughly kitna budget hai aapka?",
            "ask_visit_time": "Weekend better rahega ya weekday?",
        }
        nudge = hi_nudges.get(goal, nudge)

    return nudge


def _is_repetition(new_response: str, last_response: str) -> bool:
    """Check if new_response is essentially the same as last_response."""
    a = new_response.lower().strip().rstrip("?.!,")
    b = last_response.lower().strip().rstrip("?.!,")
    if not a or not b:
        return False
    # Exact match
    if a == b:
        return True
    # High overlap (>80% of words shared)
    words_a = set(a.split())
    words_b = set(b.split())
    if not words_a or not words_b:
        return False
    overlap = len(words_a & words_b) / max(len(words_a), len(words_b))
    return overlap > 0.8


def _log_phrase_usage(response: str) -> None:
    """Log which phrase bank entries were used (for debugging)."""
    try:
        from .state_manager import _match_phrases_used, _PHRASE_BANK
        matched = _match_phrases_used(response, _PHRASE_BANK)
        if matched:
            logger.info("[JSON PHRASES USED] %s", "; ".join(f'"{p}"' for p in matched[:5]))
    except Exception:
        pass


# ─── Sync wrapper (for backward compatibility) ──────────────────────────────

def generate_response_for_turn_sync(turn: TurnResult, state_manager: Optional[Any] = None) -> str:
    """Synchronous wrapper for generate_response_for_turn.

    Handles the case where we're already inside an async event loop
    (common in the pipeline's to_thread() calls).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, generate_response_for_turn(turn, state_manager=state_manager))
            return future.result(timeout=10)
    else:
        return asyncio.run(generate_response_for_turn(turn, state_manager=state_manager))

