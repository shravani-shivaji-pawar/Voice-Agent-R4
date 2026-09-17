"""
education_agent.py — Main Handler for Aarohi Education Counselling Agent.
Executes education turns with complete domain isolation from Real Estate.
"""

import logging
from typing import Dict, Any, Tuple, List, Optional
from langchain_core.messages import AIMessage, HumanMessage

from .education_prompts import AAROHI_PERSONA, EDUCATION_GREETING_PROMPTS, EDUCATION_FALLBACK_PROMPTS
from .education_entities import extract_education_entities
from .education_intents import classify_education_intent
from .education_state import EducationStateManager
from .education_knowledge import get_education_knowledge_response

logger = logging.getLogger("education_agent")

async def handle_education_greeting(state: Dict[str, Any], language: str = "en") -> Tuple[str, bool]:
    """Generates cold opener for Aarohi Education Counsellor."""
    lang = language.lower() if language else "en"
    if "hi" in lang:
        opener = EDUCATION_GREETING_PROMPTS["hi"]
    elif "hinglish" in lang:
        opener = EDUCATION_GREETING_PROMPTS["hinglish"]
    else:
        opener = EDUCATION_GREETING_PROMPTS["en"]

    logger.info("[AAROHI GREETING] Opener delivered: %s", opener)
    return opener, False

async def handle_education_turn(
    user_text: str,
    conversation_history: List[Dict[str, str]],
    language: str = "en",
    state_manager: Optional[Any] = None
) -> Tuple[str, bool]:
    """
    Main entry point for processing user turns for Aarohi Education Counsellor.
    """
    # 1. Ensure EducationStateManager is active
    if not isinstance(state_manager, EducationStateManager):
        edu_state_mgr = EducationStateManager()
        if state_manager and hasattr(state_manager, "conversation_data"):
            # Copy over any existing slots
            edu_state_mgr.update_profile(state_manager.conversation_data)
        state_manager = edu_state_mgr

    # 2. Extract Education Entities
    entities = extract_education_entities(user_text)
    state_manager.update_profile(entities)

    # 3. Classify Education Intent
    intent_info = classify_education_intent(user_text)
    intent = intent_info.get("intent")

    # 4. Check Goodbye / Terminal
    if intent == "goodbye":
        state_manager._session_ended = True
        if language in ("hi", "hinglish"):
            reply = "धन्यवाद! हमारे काउंसलर आपसे जल्द ही संपर्क करेंगे। आपका दिन शुभ हो!"
        else:
            reply = "Thank you! Our expert counsellor will get in touch with you soon. Have a great day!"
        return reply, True

    # 5. Check Knowledge / Anti-Hallucination rules
    knowledge_reply = get_education_knowledge_response(user_text, language=language)
    if knowledge_reply:
        return knowledge_reply, False

    # 6. Specific user response handling (e.g. "I am currently studying")
    clean = user_text.lower().strip()
    if clean in ["i am currently studying", "i am studying", "i'm studying", "currently studying", "main padhai kar raha hoon", "main padhai kar rahi hoon"]:
        qual = state_manager.student_profile.get("current_qualification")
        if qual:
            if language in ("hi", "hinglish"):
                reply = f"बहुत बढ़िया! आप {qual} कर रहे हैं। आगे आप कौन सा कोर्स या करियर ऑप्शन सोच रहे हैं?"
            else:
                reply = f"That's great! Since you're pursuing {qual}, what course or career path are you planning next?"
        else:
            if language in ("hi", "hinglish"):
                reply = "जी बढ़िया! आप अभी कौन सी क्लास या डिग्री में पढ़ाई कर रहे हैं?"
            else:
                reply = "Sure! What degree or course are you currently studying, and what are you planning for next?"
        return reply, False

    # 7. Dynamic Turn Response Generation
    next_goal = state_manager.get_next_question_goal()
    profile = state_manager.student_profile

    context_str = f"Student Profile captured so far: {profile}\nNext question goal: {next_goal}"
    system_prompt = (
        f"{AAROHI_PERSONA}\n\n"
        f"Context:\n{context_str}\n\n"
        "Instructions:\n"
        "1. Read what the student just said. Respond naturally and supportively.\n"
        "2. If they provided a detail (e.g. BCA, 78%, Pune), acknowledge it warmly.\n"
        "3. Ask ONE relevant question to move forward (e.g. course choice, location, budget).\n"
        "4. NEVER ask about real estate, apartments, BHKs, flats, or site visits.\n"
        f"5. Active Language: {language}."
    )

    from llm.llm import _call_groq_with_retry, cfg
    messages = [{"role": "system", "content": system_prompt}]
    for msg in conversation_history[-4:]:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": user_text})

    try:
        completion = await _call_groq_with_retry(messages, cfg.MODEL_NAME, max_tokens=70, temperature=0.3, max_attempts=2)
        if completion and completion.strip():
            reply = completion.strip()
            # Double check fallback anti-leakage
            if "bhk" in reply.lower() or "apartment" in reply.lower() or "flat" in reply.lower():
                logger.warning("[AAROHI FILTER] Filtered real-estate word in LLM reply: %s", reply)
                if language in ("hi", "hinglish"):
                    reply = "बहुत बढ़िया! आप आगे कौन सा कोर्स या यूनिवर्सिटी ऑप्शन देख रहे हैं?"
                else:
                    reply = "Great! What course or university options are you considering next?"
            return reply, False
    except Exception as exc:
        logger.error("[AAROHI LLM] Error calling Groq: %s", exc)

    # Fallback response
    if language in ("hi", "hinglish"):
        fallback = "जी! आप आगे कौन सा कोर्स या कॉलेज एक्सप्लोर करना चाहते हैं?"
    else:
        fallback = "Sure! What course or field of study are you looking to explore next?"

    return fallback, False
