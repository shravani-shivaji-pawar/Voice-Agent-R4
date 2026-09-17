import json
import asyncio
import re
import math
from collections import Counter
from llm import config as cfg

import logging
import os
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from groq import AsyncGroq, RateLimitError, APITimeoutError, APIError
import time
import random as _random

logger = logging.getLogger(__name__)

try:
    from openai import AsyncOpenAI
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False

# Dynamic LLM Client Selection (OpenAI / Groq / Llama)
def get_llm_client():
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    llama_key = os.getenv("LLAMA_API_KEY", "").strip()
    llama_url = os.getenv("LLAMA_BASE_URL", "").strip() or "https://openrouter.ai/api/v1"

    if provider == "llama" and llama_key and _HAS_OPENAI:
        return AsyncOpenAI(api_key=llama_key, base_url=llama_url)
    if (provider == "openai" or (openai_key and not groq_key and provider != "groq")) and _HAS_OPENAI:
        return AsyncOpenAI(api_key=openai_key)
    return AsyncGroq(api_key=groq_key)

_client = get_llm_client()

class ExtractedEntities(BaseModel):
    # Real Estate fields
    location: Optional[str] = Field(None, description="location or city e.g. Wakad, Baner, Hinjewadi, Pune")
    budget: Optional[str] = Field(None, description="property or education budget e.g. 50 lakhs, 2 crores, 2 to 3 lakhs")
    bhk: Optional[str] = Field(None, description="BHK configuration e.g. 1 BHK, 2 BHK, 3 BHK")
    property_type: Optional[str] = Field(None, description="property type e.g. apartment, villa, plot, commercial")
    intent_value: Optional[str] = Field(None, description="purpose e.g. buy, rent, invest, sell")
    timeline: Optional[str] = Field(None, description="timeline e.g. immediate, weekend, 2 months")
    
    # Education fields
    current_qualification: Optional[str] = Field(None, description="user's current education level e.g. BCA, 12th science, B.Tech, B.Com")
    preferred_course: Optional[str] = Field(None, description="course user wants to pursue e.g. MCA, MBA, B.Tech, M.Tech, MBBS")
    preferred_specialization: Optional[str] = Field(None, description="specialization e.g. AI, Computer Science, Data Science, Finance")
    preferred_city: Optional[str] = Field(None, description="preferred study city e.g. Pune, Jaipur, Delhi, Mumbai, Bangalore")
    preferred_country: Optional[str] = Field(None, description="preferred study country e.g. USA, UK, Canada, Germany, Australia")
    study_abroad: Optional[bool] = Field(None, description="whether student wants to study abroad")
    percentage: Optional[str] = Field(None, description="academic percentage or GPA e.g. 78%, 85%")
    budget_range: Optional[str] = Field(None, description="budget range e.g. 2 to 3 lakhs, 10 lakhs")
    entrance_exam: Optional[str] = Field(None, description="entrance exam taken or preparing e.g. MAH MCA CET, JEE Main, CAT, IELTS")
    career_goal: Optional[str] = Field(None, description="career goal or interests e.g. software development, programming, AI")
    
    # Common fields
    user_name: Optional[str] = Field(None, description="user's first name if provided")
    phone: Optional[str] = Field(None, description="phone number if provided")

class IntentAnalysis(BaseModel):
    intent: str = Field(
        ...,
        description="GREETING, DISCOVERY, QUALIFICATION, LIVE_SEARCH, OBJECTION_HANDLING, SCHEDULING, CLOSING"
    )
    confidence_score: float = Field(1.0, description="Confidence score between 0.0 and 1.0")
    entities: ExtractedEntities

INTENT_EXTRACTION_PROMPT = """You are an expert education intent classifier and student profile slot extractor.
Analyze the user's latest message and conversation history. Map it to one of the following node intents:
- GREETING: User saying hello, asking who is speaking, or general initial greeting.
- DISCOVERY: User sharing general career interests, or asking what courses or options are available.
- QUALIFICATION: User providing specific details about their education, degree, percentage, city, or budget.
- LIVE_SEARCH: User asking specific questions about courses, exams, fees, scholarships, or college guidance.
- OBJECTION_HANDLING: User raising concerns (too expensive, wrong city, not sure what to study).
- SCHEDULING: User requesting to speak with an education counsellor or schedule a callback.
- CLOSING: User winding down, saying goodbye, or finalizing the call.

Also extract the following student profile entities if present:
- current_qualification: e.g. "BCA", "12th science", "B.Tech"
- preferred_course: e.g. "MCA", "MBA", "M.Tech", "B.Tech"
- preferred_specialization: e.g. "AI", "Computer Science", "Data Science"
- preferred_city: e.g. "Pune", "Jaipur", "Bangalore", "Delhi"
- preferred_country: e.g. "USA", "UK", "Canada", "Germany", "Australia"
- study_abroad: set to true if user mentions studying abroad or foreign countries
- percentage: e.g. "78%", "85%"
- budget_range: e.g. "2 to 3 lakhs", "5 lakhs"
- entrance_exam: e.g. "MAH MCA CET", "JEE Main", "IELTS"
- career_goal: e.g. "software development", "AI engineer"
- user_name: extract first name if explicitly given
- phone: extract phone number if provided

Respond ONLY with a valid JSON object matching this schema:
{
  "intent": "GREETING | DISCOVERY | QUALIFICATION | LIVE_SEARCH | OBJECTION_HANDLING | SCHEDULING | CLOSING",
  "confidence_score": 0.0 to 1.0,
  "entities": {
    "current_qualification": "string | null",
    "preferred_course": "string | null",
    "preferred_specialization": "string | null",
    "preferred_city": "string | null",
    "preferred_country": "string | null",
    "study_abroad": boolean | null,
    "percentage": "string | null",
    "budget_range": "string | null",
    "entrance_exam": "string | null",
    "career_goal": "string | null",
    "user_name": "string | null",
    "phone": "string | null"
  }
}
Do not return markdown, ticks, or text explanations.
"""

async def analyze_user_intent(user_input: str, history: List[Dict[str, str]]) -> IntentAnalysis:
    """
    Queries Groq using llama-3.1-8b-instant to classify intent and extract slots,
    with 0ms local bypass for deterministic inputs.
    """
    try:
        from llm.state_manager import is_hard_out
        if is_hard_out(user_input):
            return IntentAnalysis(
                intent="CLOSING",
                confidence_score=1.0,
                entities=ExtractedEntities()
            )
            
        local_info = _classify_local_intent(user_input)
        if local_info and local_info.get("intent") and local_info.get("intent") not in {"unclear", "user_question"}:
            loc_intent = local_info.get("intent")
            ents = local_info.get("entities", {})
            target_intent = "QUALIFICATION" if loc_intent in {"provide_location", "provide_budget", "provide_info", "provide_intent", "confirm"} else "DISCOVERY"
            
            return IntentAnalysis(
                intent=target_intent,
                confidence_score=0.95,
                entities=ExtractedEntities(
                    current_qualification=ents.get("current_qualification"),
                    preferred_course=ents.get("preferred_course"),
                    preferred_specialization=ents.get("preferred_specialization"),
                    preferred_city=ents.get("preferred_city") or ents.get("location"),
                    preferred_country=ents.get("preferred_country"),
                    study_abroad=ents.get("study_abroad"),
                    percentage=ents.get("percentage"),
                    budget_range=ents.get("budget"),
                    entrance_exam=ents.get("entrance_exam"),
                    career_goal=ents.get("career_goal"),
                    user_name=ents.get("user_name"),
                    phone=ents.get("phone"),
                )
            )
    except Exception:
        pass

    messages = [
        {"role": "system", "content": INTENT_EXTRACTION_PROMPT}
    ]
    
    # Append brief history context for conversational coherence
    for msg in history[-5:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
        
    messages.append({"role": "user", "content": user_input})
    
    try:
        response = await _client.chat.completions.create(
            model=getattr(cfg, "FAST_MODEL_NAME", cfg.MODEL_NAME),
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=256
        )
        
        raw_json = response.choices[0].message.content
        data = json.loads(raw_json)
        return IntentAnalysis(**data)
    except Exception as e:
        logger.error(f"Failed to extract intent via Groq: {e}. Defaulting to DISCOVERY.")
        return IntentAnalysis(
            intent="DISCOVERY",
            confidence_score=0.0,
            entities=ExtractedEntities()
        )

class CombinedResponseAnalysis(BaseModel):
    intent_analysis: IntentAnalysis
    spoken_reply_text: str

COMBINED_EXTRACTION_PROMPT = """You are Aarohi, an AI Education Counsellor on a live phone call.

Perform two tasks in a single turn:
1. Extract the student's intent and profile entities based on their latest message.
2. Generate your spoken reply text naturally in the SAME language as the user (English, Hindi, or Hinglish).

Use the same INTENT classes: GREETING, DISCOVERY, QUALIFICATION, LIVE_SEARCH, OBJECTION_HANDLING, SCHEDULING, CLOSING.
Extract entities: current_qualification, preferred_course, preferred_specialization, preferred_city, preferred_country, study_abroad, percentage, budget_range, entrance_exam, career_goal, user_name, phone.

Spoken Response Rules:
- Match the user's language: If the user speaks Hindi or Hinglish, respond in natural spoken Hindi/Hinglish.
- NEVER invent factual details about specific colleges, cutoffs, rankings, placement stats, scholarships, or exact fees. State clearly that details vary by university.
- Keep responses to 15-25 words. Plain spoken sentences. NEVER use bullet points, tables, lists, or markdown formatting.

Respond ONLY with a valid JSON object matching this schema:
{
  "intent_analysis": {
    "intent": "GREETING | DISCOVERY | QUALIFICATION | LIVE_SEARCH | OBJECTION_HANDLING | SCHEDULING | CLOSING",
    "confidence_score": 0.0 to 1.0,
    "entities": {
      "current_qualification": "string | null",
      "preferred_course": "string | null",
      "preferred_specialization": "string | null",
      "preferred_city": "string | null",
      "preferred_country": "string | null",
      "study_abroad": boolean | null,
      "percentage": "string | null",
      "budget_range": "string | null",
      "entrance_exam": "string | null",
      "career_goal": "string | null",
      "user_name": "string | null",
      "phone": "string | null"
    }
  },
  "spoken_reply_text": "Your natural spoken response here"
}
"""

async def generate_combined_intent_and_response(user_input: str, history: List[Dict[str, str]], context: str = "") -> CombinedResponseAnalysis:
    """
    Fast path: queries Groq using llama-3.3-70b-versatile to extract slots AND generate the response in one shot.
    """
    messages = [
        {"role": "system", "content": COMBINED_EXTRACTION_PROMPT + (f"\n\nLive Context: {context}" if context else "")}
    ]
    
    for msg in history[-8:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
        
    messages.append({"role": "user", "content": user_input})
    
    try:
        response = await _client.chat.completions.create(
            model=getattr(cfg, "VERSATILE_MODEL_NAME", cfg.MODEL_NAME),
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.65,
            max_tokens=800
        )
        
        raw_json = response.choices[0].message.content or "{}"
        data = json.loads(raw_json)
        if "spoken_reply_text" in data and data["spoken_reply_text"]:
            data["spoken_reply_text"] = _sanitize_llm_text(data["spoken_reply_text"])
        return CombinedResponseAnalysis(**data)
    except Exception as e:
        logger.error(f"Failed to generate combined response: {e}")
        return CombinedResponseAnalysis(
            intent_analysis=IntentAnalysis(intent="DISCOVERY", confidence_score=0.0, entities=ExtractedEntities()),
            spoken_reply_text="Give me just one moment..."
        )

_NEHA_PERSONA = (
    "Role & Core Identity:\n"
    "You are Priya (or Neha), a polite, professional, and persuasive Senior Real Estate Sales Advisor at Suncity Apartments. "
    "You speak naturally over the phone like a real human sales executive — friendly, helpful, concise, and focused on property discovery and scheduling a site visit.\n\n"

    "CRITICAL REAL ESTATE RULES:\n"
    "1. Name: Priya (or Neha), Real Estate Sales Executive at Suncity Apartments.\n"
    "2. Scope: Real Estate property search (1 BHK, 2 BHK, 3 BHK, apartments, villas, location, budget, site visit scheduling).\n"
    "3. CONVERSATIONAL STYLE: Keep responses short (1-2 spoken sentences, max 25 words). Ask at most ONE question per turn. No markdown, bullet points, or tables.\n"
    "4. Match the user's language: Respond in clear, natural English, Hindi, or Hinglish as spoken by the user.\n"
)

_AAROHI_PERSONA = (
    "Role & Core Identity:\n"
    "You are Aarohi, a warm, polite, supportive, and professional AI Education Counsellor. "
    "You speak naturally like a helpful human counsellor over the phone — friendly, patient, grounded, and concise (1-2 short spoken sentences).\n\n"

    "CRITICAL COUNSELLING & NO-HALLUCINATION RULES:\n"
    "1. Name: Aarohi, AI Education Counsellor.\n"
    "2. Scope: Courses (BCA, MCA, B.Tech, MBA, etc.), Colleges, Entrance Exams, Admission Process, Fees, Scholarships, Education Loans, and Study Abroad.\n"
    "3. STRICT NO-HALLUCINATION: NEVER invent or fabricate specific college rankings, cutoffs, exact fees, placement packages, admission deadlines, or scholarship amounts. State clearly that exact criteria vary by university.\n"
    "4. NO REPETITION: Verified student state is authoritative. Never re-ask for course, city, qualification, or budget if already captured in state.\n"
    "5. CONVERSATIONAL STYLE: Keep responses short (15-25 words max per turn). Ask at most ONE question per turn. No bullet points, markdown, or tables.\n"
    "6. Match the user's language: Respond in clear, natural English, Hindi, or Hinglish as spoken by the user.\n"
)


def _sanitize_llm_text(text: str | None) -> str:
    if not text:
        return ""
    replacements = {
        "\u202f": " ",
        "\xa0": " ",
        "\u2011": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "—": "-",
        "–": "-",
        "₹": "Rs. ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.strip()


async def _call_groq_with_retry(
    messages: list[dict[str, str]],
    model_name: str,
    max_tokens: int = 400,
    temperature: float = 0.45,
    max_attempts: int = 2,
) -> str:
    """Bounded retry helper for Groq API calls to handle 429 Rate Limits & Timeouts."""
    for attempt in range(1, max_attempts + 1):
        try:
            t0 = time.time()
            completion = await _client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            latency = time.time() - t0
            logger.info("Groq LLM call succeeded in %.3fs (attempt %d/%d)", latency, attempt, max_attempts)
            return completion.choices[0].message.content or ""
        except RateLimitError as rle:
            wait = 1.0 * attempt
            logger.warning("Groq 429 rate limit hit (attempt %d/%d) — retrying in %.1fs", attempt, max_attempts, wait)
            if attempt < max_attempts:
                await asyncio.sleep(wait)
        except APITimeoutError:
            logger.warning("Groq API timeout (attempt %d/%d)", attempt, max_attempts)
            if attempt < max_attempts:
                await asyncio.sleep(0.5)
        except APIError as exc:
            logger.error("Groq API error (attempt %d/%d): %s", attempt, max_attempts, exc)
            if attempt < max_attempts:
                await asyncio.sleep(0.5)
        except Exception as exc:
            logger.error("Groq call exception (attempt %d/%d): %s", attempt, max_attempts, exc)
            break
    return ""


def _get_contextual_fallback(
    language: str,
    prompt: str = "",
    is_greeting: bool = False,
    history: Optional[List[Dict[str, str]]] = None,
    slots: Optional[Dict[str, Any]] = None,
    domain: str = "real_estate",
) -> str:
    """Generate dynamic, context-aware fallback response based on missing slots and language, avoiding repetition."""
    from llm.language_utils import normalize_language_code
    lang = normalize_language_code(language)

    last_assistant_msg = ""
    if history:
        for msg in reversed(history):
            if msg.get("role") in ("assistant", "agent", "bot"):
                last_assistant_msg = (msg.get("content") or "").strip()
                break

    def _select_candidate(candidates: list[str]) -> str:
        if not candidates:
            return ""
        for cand in candidates:
            if cand.strip() != last_assistant_msg:
                return cand
        return candidates[0]

    if domain == "education":
        if is_greeting:
            if lang in ("hi", "hinglish"):
                return _select_candidate([
                    "नमस्ते! मैं आरोही बोल रही हूँ, आपकी एजुकेशन काउंसलर। आप अभी क्या पढ़ाई कर रहे हैं या आगे क्या पढ़ना चाहते हैं?",
                    "Hi! Main Aarohi baat kar rahi hoon, aapki education counsellor. Aap aage kya padhna chahte hain?"
                ])
            return _select_candidate([
                "Hi, I'm Aarohi, your education counsellor. What are you currently studying or planning to study?",
                "Hello, I'm Aarohi. I can help you with course options, colleges, or study abroad plans. What are you preparing for?"
            ])

        s = slots or {}
        has_course = bool(s.get("preferred_course") or s.get("current_qualification"))
        has_city = bool(s.get("preferred_city") or s.get("preferred_country"))

        if not has_course:
            if lang in ("hi", "hinglish"):
                return _select_candidate([
                    "समझ गई! आप कौन सा कोर्स या डिग्री प्रेफर कर रहे हैं?",
                    "जी, आप आगे BCA, MCA, B.Tech या MBA में से क्या प्लान कर रहे हैं?"
                ])
            return _select_candidate([
                "Understood! Which degree or course are you planning to pursue?",
                "Got it! Are you looking for undergraduate or postgraduate courses?"
            ])

        if not has_city:
            if lang in ("hi", "hinglish"):
                return _select_candidate([
                    "जी, आप किस शहर या देश में स्टडी करना चाहते हैं?",
                    "समझ गई! आपकी प्रेफर्ड लोकेशन पुणे, जयपुर, बैंगलोर या स्टडी एब्रॉड है?"
                ])
            return _select_candidate([
                "Got it! Which city or country do you prefer for your education?",
                "Understood! Are you looking for colleges in India or studying abroad?"
            ])

        if lang in ("hi", "hinglish"):
            return _select_candidate([
                "समझ गई! क्या आप विस्तृत काउंसलिंग के लिए हमारे एक्सपर्ट काउंसलर से बात करना चाहेंगे?",
                "जी धन्यवाद! हमारी टीम आपको जल्द ही कोर्स और एडमिशन डिटेल्स भेजेगी।"
            ])
        return _select_candidate([
            "Understood! Would you like me to connect you with an expert education counsellor?",
            "Got it! Our counselling team will guide you on admission details shortly."
        ])

    if is_greeting:
        if lang in ("hi", "hinglish"):
            return _select_candidate([
                "नमस्ते, मैं सनसिटी अपार्टमेंट्स से प्रिया बोल रही हूँ। क्या आप प्रॉपर्टी खरीदना या किराए पर लेना चाहते हैं?",
                "नमस्ते, मैं सनसिटी अपार्टमेंट्स से प्रिया। मैं आपकी प्रॉपर्टी खोज में मदद करने के लिए कॉल कर रही हूँ।"
            ])
        elif lang == "mr":
            return _select_candidate([
                "नमस्कार, मी सनसिटी अपार्टमेंट्सकडून प्रिया बोलत आहे. तुम्ही प्रॉपर्टी खरेदी करू इच्छिता की भाड्याने घेऊ इच्छिता?",
                "नमस्कार! मी सनसिटी अपार्टमेंट्सकडून प्रिया. मी तुमच्या प्रॉपर्टी शोधत मदत करण्यासाठी कॉल केला आहे."
            ])
        return _select_candidate([
            "Hi, this is Priya from Suncity Apartments. Are you looking to buy or rent a property?",
            "Hello! This is Priya from Suncity Apartments. How can I assist with your property search today?"
        ])

    if domain == "education":
        if is_greeting:
            if lang in ("hi", "hinglish"):
                return "नमस्ते! मैं आरोही बोल रही हूँ, आपकी एजुकेशन काउंसलर। आप अभी क्या पढ़ाई कर रहे हैं या आगे क्या पढ़ना चाहते हैं?"
            return "Hi, I'm Aarohi, your education counsellor. What are you currently studying or planning to study?"
        
        has_course = bool(s.get("preferred_course") or s.get("current_qualification"))
        has_location = bool(s.get("preferred_city") or s.get("preferred_country") or s.get("study_abroad") is not None)
        has_budget = bool(s.get("budget"))

        if not has_course:
            if lang in ("hi", "hinglish"):
                return "जी! आप अभी क्या पढ़ाई कर रहे हैं या कौन सा कोर्स करने की सोच रहे हैं?"
            return "Got it! Which course or degree are you looking to pursue?"
        if not has_location:
            if lang in ("hi", "hinglish"):
                return "समझ गई! आप किस शहर में या स्टडी एब्रॉड में पढ़ना चाहते हैं?"
            return "Understood! Which city or country are you considering for your studies?"
        if not has_budget:
            if lang in ("hi", "hinglish"):
                return "जी, आपका कोर्स फीस के लिए बजट क्या रहेगा?"
            return "Understood! What budget range do you have in mind for your course?"

        if lang in ("hi", "hinglish"):
            return "बहुत बढ़िया! क्या आप हमारे एक्सपर्ट काउंसलर से सेशन कनेक्ट करना चाहेंगे?"
        return "Great! Would you like me to connect you with an expert counsellor for detailed guidance?"

    s = slots or {}
    has_location = bool(s.get("location"))
    has_bhk = bool(s.get("bhk") or s.get("preferred_bhk"))
    has_budget = bool(s.get("budget") or s.get("budget_range"))

    p_lower = (prompt or "").lower()
    if not has_location and ("location:" in p_lower or "location already" in p_lower):
        has_location = True
    if not has_bhk and ("bhk preference:" in p_lower or "bhk:" in p_lower):
        has_bhk = True
    if not has_budget and ("budget:" in p_lower or "budget range:" in p_lower):
        has_budget = True
    logger.info("[FALLBACK DEBUG] slots=%s, has_loc=%s, has_bhk=%s, has_budget=%s", s, has_location, has_bhk, has_budget)

    if not has_location:
        if lang in ("hi", "hinglish"):
            return _select_candidate([
                "समझ गई! आप किस शहर या क्षेत्र में प्रॉपर्टी देख रहे हैं?",
                "जी, मुझे बताएँ कि आपकी पसंद का कौन सा शहर या एरिया है?"
            ])
        elif lang == "mr":
            return _select_candidate([
                "समजले! तुम्ही कोणत्या शहरात किंवा भागात प्रॉपर्टी पाहत आहात?",
                "समजले! तुमची पसंतीचे शहर किंवा भाग कोणता आहे?"
            ])
        return _select_candidate([
            "Understood! Which city or area are you considering?",
            "Got it! What location do you have in mind?"
        ])

    if not has_bhk:
        if lang in ("hi", "hinglish"):
            return _select_candidate([
                "समझ गई! आप कितने BHK का फ्लैट देखना चाहते हैं?",
                "जी, आपकी क्या preference है — 2 BHK या 3 BHK?"
            ])
        elif lang == "mr":
            return _select_candidate([
                "समजले! तुम्हाला किती BHK चा फ्लॅट हवा आहे?",
                "समजले! तुमची पसंती 2 BHK आहे की 3 BHK?"
            ])
        return _select_candidate([
            "Got it! What apartment size (like 2 BHK or 3 BHK) are you looking for?",
            "Understood! Are you looking for a 2 BHK or 3 BHK flat?"
        ])

    if not has_budget:
        if lang in ("hi", "hinglish"):
            return _select_candidate([
                "समझ गई! आपका बजट लगभग कितना रहेगा?",
                "जी, आपके दिमाग में क्या बजट रेंज है?"
            ])
        elif lang == "mr":
            return _select_candidate([
                "समजले! तुमचे बजेट अंदाजे किती आहे?",
                "समजले! तुमची अपेक्षित किंमत मर्यादा काय आहे?"
            ])
        return _select_candidate([
            "Got it! What budget range do you have in mind?",
            "Understood! Could you share your expected price range?"
        ])

    if lang in ("hi", "hinglish"):
        return _select_candidate([
            "समझ गई! आपकी आवश्यकताएँ नोट कर ली हैं। क्या आप इस वीकेंड साइट विजिट करना चाहेंगे?",
            "जी, धन्यवाद! हमारी टीम आपको जल्द ही प्रॉपर्टी की जानकारी भेजेगी।"
        ])
    elif lang == "mr":
        return _select_candidate([
            "समजले! सर्व माहिती नोंदवली आहे. तुम्ही या विकेंडला साईट व्हिजिट करणार का?",
            "समजले! आमची टीम तुम्हाला लवकरच अधिक माहिती पाठवेल."
        ])
    return _select_candidate([
        "Understood! I've noted down your preferences. Would you be open for a site visit this weekend?",
        "Got it! Our team will send over the property options shortly."
    ])


async def generate_voice_response(
    prompt: str,
    history: List[Dict[str, str]],
    context: str = "",
    language: str = "en",
    is_greeting: bool = False,
    slots: Optional[Dict[str, Any]] = None,
    domain: str = "real_estate",
) -> str:
    """
    Generates a speech-optimized, human-like response using Llama 3 / GPT-OSS.
    Language-aware: strict session language lock with bounded Groq retry.
    """
    from llm.language_utils import get_language_instruction, normalize_language_code
    session_lang = normalize_language_code(language)
    lang_directive = get_language_instruction(session_lang)

    active_persona = _AAROHI_PERSONA if domain == "education" else _NEHA_PERSONA

    verified_state_str = ""
    if slots:
        verified_items = []
        if domain == "education":
            qual = slots.get("current_qualification")
            if qual: verified_items.append(f"Current Qualification: {qual}")
            course = slots.get("preferred_course")
            if course: verified_items.append(f"Preferred Course: {course}")
            city = slots.get("preferred_city")
            if city: verified_items.append(f"Preferred City: {city}")
            country = slots.get("preferred_country")
            if country: verified_items.append(f"Preferred Country: {country}")
            pct = slots.get("percentage")
            if pct: verified_items.append(f"Percentage/Score: {pct}")
            bdg = slots.get("budget") or slots.get("budget_range")
            if bdg: verified_items.append(f"Budget: {bdg}")
        else:
            loc = slots.get("location")
            if loc: verified_items.append(f"Location: {loc}")
            bhk = slots.get("bhk") or slots.get("preferred_bhk")
            if bhk: verified_items.append(f"Property/BHK: {bhk}")
            bdg = slots.get("budget") or slots.get("budget_range")
            if bdg: verified_items.append(f"Budget: {bdg}")
            intent_val = slots.get("intent") or slots.get("intent_value")
            if intent_val: verified_items.append(f"Intent: {intent_val}")
            tml = slots.get("timeline") or slots.get("timeline_weeks")
            if tml: verified_items.append(f"Timeline: {tml}")

        if verified_items:
            verified_state_str = (
                "\n\nCURRENT VERIFIED STATE (FACTUAL TRUTH — DO NOT OVERWRITE OR RE-ASK):\n"
                + "\n".join(f"- {item}" for item in verified_items)
                + "\nSTRICT INSTRUCTIONS ON VERIFIED STATE:\n"
                "1. Treat all fields in Verified State as absolute fact.\n"
                "2. NEVER ask the user for a field that is already present in Verified State.\n"
                "3. Ask ONLY for the next missing required slot, or proceed to next steps if all criteria are filled.\n"
            )

    system_prompt = (
        f"{active_persona}\n\n"
        f"HARD SESSION LANGUAGE LOCK DIRECTIVE:\n"
        f"{lang_directive}\n"
        f"The active session language is '{session_lang}'. You MUST respond ONLY in this active session language.\n"
        f"Do NOT automatically switch language based on the user's detected language, words, or input.\n"
        f"Even if the user speaks English, Hindi, or Hinglish, your reply MUST remain strictly in '{session_lang}'.\n"
        f"{verified_state_str}\n\n"
        f"{prompt}"
    )
    if context:
        system_prompt += f"\n\nLive Context: {context}"

    messages = [{"role": "system", "content": system_prompt}]
    
    for msg in history[-8:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
        
    if not messages or messages[-1]["role"] != "user":
        messages.append({"role": "user", "content": prompt if prompt else "Hello"})
        
    try:
        model_name = getattr(cfg, "VERSATILE_MODEL_NAME", cfg.MODEL_NAME) if is_greeting else getattr(cfg, "FAST_MODEL_NAME", cfg.MODEL_NAME)
        max_t = getattr(cfg, "MAX_TOKENS", 400)
        
        # Bounded retry call to Groq API to handle HTTP 429 / Timeouts
        content = await _call_groq_with_retry(messages, model_name, max_tokens=max_t, temperature=0.45, max_attempts=2)
        clean_text = _sanitize_llm_text(content)
        if not clean_text or len(clean_text.strip()) < 2:
            return _get_contextual_fallback(session_lang, prompt, is_greeting, history, slots=slots, domain=domain)

        # Response Language Validation before TTS Handoff (0ms Fallback, 0 extra LLM calls)
        from llm.language_utils import validate_response_language
        is_valid, reason = validate_response_language(clean_text, session_lang)
        if not is_valid:
            logger.warning("[RESPONSE VALIDATOR] Language mismatch detected: %s. Returning locked contextual fallback.", reason)
            return _get_contextual_fallback(session_lang, prompt, is_greeting, history, slots=slots, domain=domain)

        return clean_text
    except Exception as e:
        logger.error(f"Groq voice generation exception: {e}")
        return _get_contextual_fallback(session_lang, prompt, is_greeting, history, slots=slots, domain=domain)

_COMPANY_QUESTION_PATTERNS = re.compile(
    r"\b(?:what does (?:this|your) company do|what do you do|who is your CEO|who is the CEO|who founded|who created|who is the owner|where is your office|where are you located|tell me about your company|company details|company profile|what is suncity|what is this company|about suncity|suncity apartments|tell me about suncity|who are you|who are you calling from|which company are you calling from|headquarters|headquarter|head office|ऑफिस|मुख्यालय|कंपनी क्या करती है|सनसिटी क्या है|प्रोजेक्ट क्या है)\b",
    re.IGNORECASE,
)


def _quick_is_company_question(text: str) -> bool:
    if not text:
        return False
    return bool(_COMPANY_QUESTION_PATTERNS.search(text))


# Legacy backward-compatible RAG wrapper for Pipecat demo sessions
async def generate_response(
    user_text: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    language: str = "en",
    state_manager: Optional[Any] = None,
    allow_transition: bool = True,
    runtime_context: Optional[Dict[str, Any]] = None,
) -> tuple[str, bool]:
    """
    Translates legacy Pipecat LLM calls to execute our StateGraph under the hood,
    synchronizing extracted slots back to the legacy state_manager instance.
    """
    # ── Pre-Transition Interruption Check ─────────────────────────────────────
    if state_manager:
        current_node = state_manager.get_current_node() if hasattr(state_manager, "get_current_node") else None
        current_node_id = state_manager.current_node_id if hasattr(state_manager, "current_node_id") else "GREETING"
        global_prompt = getattr(state_manager, "global_prompt", "") or (state_manager.schema.get("global_prompt", "") if (hasattr(state_manager, "schema") and state_manager.schema) else "")
        summary_markdown = _extract_summary_from_prompt(global_prompt)
        
        # Fast path classification without extra LLM call on every turn
        classification = "node_response"
        if user_text and user_text.strip():
            if _quick_is_company_question(user_text):
                classification = "company_question"

        if classification == "company_question":
            domain = state_manager.schema.get("domain", "real_estate") if (hasattr(state_manager, "schema") and state_manager.schema) else "real_estate"
            nodes = state_manager.schema.get("conversationFlow", {}).get("nodes", []) if (hasattr(state_manager, "schema") and state_manager.schema) else []
            
            # 1. JSON Lookup
            json_answer = _search_json_knowledge(user_text, nodes, language=language, domain=domain)
            json_matched = bool(json_answer)
            
            answer = ""
            answer_source = "Unknown"
            retrieved_headings = []
            retrieved_chunks = []
            retrieved_scores = []
            llm_called = False
            context_len = 0
            
            if json_matched:
                answer = json_answer
                answer_source = "JSON"
            else:
                # 2. Semantic retrieval on summary
                if summary_markdown:
                    retrieved_headings, retrieved_chunks, retrieved_scores = _retrieve_semantic_chunks_tfidf(
                        user_text, summary_markdown
                    )
                
                if retrieved_chunks:
                    llm_called = True
                    answer = await _generate_answer_from_chunks(user_text, retrieved_chunks, language, domain=domain)
                    answer_source = "Summary"
                    context_len = sum(len(c) for c in retrieved_chunks)
                else:
                    # 3. LLM fallback
                    llm_called = True
                    answer = await _generate_llm_fallback_answer(user_text, summary_markdown or "", language, domain=domain)
                    answer_source = "LLM"
                    context_len = len(summary_markdown) if summary_markdown else 0

            if any(k in user_text.lower() for k in ["who are you", "who is this", "kon ho", "kaun ho", "कौन हो", "आपका नाम"]):
                domain = "real_estate"
                if state_manager and hasattr(state_manager, "schema") and state_manager.schema:
                    domain = state_manager.schema.get("domain", "real_estate")
                if domain == "education":
                    if language == "hi":
                        answer = "नमस्ते! मैं आरोही बोल रही हूँ, आपकी एजुकेशन काउंसलर। मैं आपको कोर्स, कॉलेज, एंट्रेंस एग्जाम और एडमिशन प्रोसेस के लिए गाइड कर सकती हूँ।"
                    elif language == "hinglish":
                        answer = "Hi! Main Aarohi baat kar rahi hoon, aapki education counsellor. Main aapko courses, colleges, entrance exams aur study abroad ke liye guide kar sakti hoon."
                    else:
                        answer = "Hi, I'm Aarohi, your AI education counsellor. I can help you explore courses, colleges, entrance exams, and study abroad options."
                else:
                    if language == "hi":
                        answer = "नमस्ते! मैं सनसिटी अपार्टमेंट्स से प्रिया बोल रही हूँ। मैं आपको फ्लैट्स और प्रॉपर्टी डिटेल्स के बारे में जानकारी दे सकती हूँ।"
                    elif language == "hinglish":
                        answer = "Hi! Main Suncity Apartments se Priya baat kar rahi hoon. Main aapko property details aur site visit ke liye assist kar sakti hoon."
                    else:
                        answer = "Hello! This is Priya from Suncity Apartments. I'm here to assist you with finding the right property."
                    
            finalized_response = answer

            # Detailed runtime logs matching the user checklist exactly
            logger.info(
                "[INTERRUPTION LAYER]\n"
                f"  - Incoming User Query: \"{user_text}\"\n"
                f"  - Intent Classification: {classification}\n"
                f"  - Current Conversation Node: {current_node_id}\n"
                f"  - JSON Search: Checked {len(nodes)} nodes\n"
                f"  - JSON Match Found?: {json_matched}\n"
                f"  - Company Summary Loaded: {bool(summary_markdown)}\n"
                f"  - Semantic Retrieval Started: True\n"
                f"  - Retrieved Chunks: {retrieved_headings}\n"
                f"  - Similarity Scores: {retrieved_scores}\n"
                f"  - LLM Invoked?: {llm_called}\n"
                f"  - LLM Context Size: {context_len} chars\n"
                f"  - Final Answer Source: {answer_source}\n"
                f"  - Resume Previous Node: None (Direct Answer)"
            )
            
            # Record response for anti-repetition
            if hasattr(state_manager, "record_response"):
                state_manager.record_response(finalized_response)
                
            # Return answer + resume bridge, is_terminal=False
            return finalized_response, False

    from langchain_core.messages import HumanMessage, AIMessage
    from intelligence.pipeline import langgraph_engine
    from llm.state_manager import process_intent_and_slots

    # 1. Reconstruct graph messages from history
    messages = []
    if conversation_history:
        for msg in conversation_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))

    # 2. Reconstruct slots
    slots = {
        "bhk": None,
        "location": None,
        "property_type": None,
        "preferred_bhk": None,
        "current_qualification": None,
        "preferred_course": None,
        "preferred_specialization": None,
        "preferred_city": None,
        "preferred_country": None,
        "study_abroad": None,
        "percentage": None,
        "budget_range": None,
        "budget": None,
        "entrance_exam": None,
        "career_goal": None,
        "user_name": None,
        "phone": None
    }
    if state_manager and hasattr(state_manager, "conversation_data"):
        data = state_manager.conversation_data
        slots["bhk"] = data.get("bhk") or data.get("property_type")
        slots["location"] = data.get("location") or data.get("preferred_city")
        slots["property_type"] = data.get("property_type") or data.get("bhk")
        slots["preferred_bhk"] = data.get("preferred_bhk") or data.get("bhk")
        slots["current_qualification"] = data.get("current_qualification")
        slots["preferred_course"] = data.get("preferred_course")
        slots["preferred_specialization"] = data.get("preferred_specialization")
        slots["preferred_city"] = data.get("preferred_city") or data.get("location")
        slots["preferred_country"] = data.get("preferred_country")
        slots["study_abroad"] = data.get("study_abroad")
        slots["percentage"] = data.get("percentage")
        slots["budget"] = data.get("budget")
        slots["budget_range"] = data.get("budget")
        slots["entrance_exam"] = data.get("entrance_exam")
        slots["career_goal"] = data.get("career_goal")
        slots["user_name"] = data.get("user_name")
        slots["phone"] = data.get("phone")

    # 3. Create active Graph state
    domain = "real_estate"
    if state_manager and hasattr(state_manager, "schema") and state_manager.schema:
        domain = state_manager.schema.get("domain", "real_estate")

    graph_state = {
        "messages": messages,
        "extracted_slots": slots,
        "current_node": getattr(state_manager, "current_node_id", "GREETING") if state_manager else "GREETING",
        "pending_filler_action": None,
        "rag_context": None,
        "retry_count": 0,
        "user_input": user_text,
        "language": language,   # ← pass active session language to all node handlers
        "domain": domain,       # ← pass active domain to all node handlers
    }

    # 4. Handle start greeting vs subsequent turns
    _SYSTEM_TRIGGERS = {"__CONNECTED__", "[System:"}
    is_system_trigger = user_text == "__CONNECTED__" or user_text.startswith("[System:")
    if is_system_trigger:
        graph_state["current_node"] = "GREETING"
        graph_state["user_input"] = ""
    else:
        # Check single-call fast path eligibility
        is_first_turn = not bool(conversation_history and any(m.get("role") == "user" for m in conversation_history))
        last_confidence = getattr(state_manager, "last_intent_confidence", 1.0) if state_manager else 1.0
        word_count = len(user_text.split())
        
        if cfg.ENABLE_SINGLE_CALL_FAST_PATH and not is_first_turn and word_count <= 15 and last_confidence > 0.8:
            logger.info("Taking single-call fast path for LLM response.")
            global_prompt = ""
            if state_manager:
                global_prompt = getattr(state_manager, "global_prompt", "") or (state_manager.schema.get("global_prompt", "") if hasattr(state_manager, "schema") else "")
                
            combined = await generate_combined_intent_and_response(user_text, conversation_history or [], global_prompt)
            if combined and combined.spoken_reply_text and combined.spoken_reply_text != "Give me just one moment...":
                # Sync back state
                es = combined.intent_analysis.entities
                if state_manager and hasattr(state_manager, "conversation_data"):
                    state_manager.current_node_id = combined.intent_analysis.intent
                    if es.current_qualification: state_manager.conversation_data["current_qualification"] = es.current_qualification
                    if es.preferred_course: state_manager.conversation_data["preferred_course"] = es.preferred_course
                    if es.preferred_specialization: state_manager.conversation_data["preferred_specialization"] = es.preferred_specialization
                    if es.preferred_city: state_manager.conversation_data["preferred_city"] = es.preferred_city
                    if es.preferred_country: state_manager.conversation_data["preferred_country"] = es.preferred_country
                    if es.study_abroad is not None: state_manager.conversation_data["study_abroad"] = es.study_abroad
                    if es.percentage: state_manager.conversation_data["percentage"] = es.percentage
                    if es.budget_range: state_manager.conversation_data["budget"] = es.budget_range
                    if es.entrance_exam: state_manager.conversation_data["entrance_exam"] = es.entrance_exam
                    if es.career_goal: state_manager.conversation_data["career_goal"] = es.career_goal
                    state_manager.last_intent_confidence = combined.intent_analysis.confidence_score
                
                # Record response
                if hasattr(state_manager, "record_response"):
                    state_manager.record_response(combined.spoken_reply_text)
                    
                return combined.spoken_reply_text, (combined.intent_analysis.intent == "CLOSING")
            else:
                logger.info("Fast path JSON generation failed. Continuing with standard pipeline.")

        graph_state["messages"].append(HumanMessage(content=user_text))
        # Update slots and resolve transitions
        graph_state = await process_intent_and_slots(graph_state)
        if state_manager:
            state_manager.last_intent_confidence = graph_state.get("last_intent_confidence", 1.0)

    # 5. Invoke LangGraph
    graph_state = await langgraph_engine.ainvoke(graph_state)
    
    # If it is a live search, execute the crawl sequentially in this single turn
    if graph_state.get("pending_filler_action"):
        graph_state["pending_filler_action"] = None
        graph_state = await langgraph_engine.ainvoke(graph_state)

    # 6. Extract final response
    reply = "Let me look into this."
    if graph_state["messages"]:
        last_msg = graph_state["messages"][-1]
        if isinstance(last_msg, AIMessage):
            reply = last_msg.content

    # 7. Sync slots back to legacy state manager safely
    if state_manager and hasattr(state_manager, "conversation_data"):
        state_manager.current_node_id = graph_state["current_node"]
        es = graph_state["extracted_slots"]
        val_qual = es.get("current_qualification")
        val_course = es.get("preferred_course")
        val_spec = es.get("preferred_specialization")
        val_city = es.get("preferred_city") or es.get("location")
        val_country = es.get("preferred_country")
        val_abroad = es.get("study_abroad")
        val_pct = es.get("percentage")
        val_budget = es.get("budget") or es.get("budget_range")
        val_exam = es.get("entrance_exam")
        val_goal = es.get("career_goal")
        
        if val_qual: state_manager.conversation_data["current_qualification"] = val_qual
        if val_course: state_manager.conversation_data["preferred_course"] = val_course
        if val_spec: state_manager.conversation_data["preferred_specialization"] = val_spec
        if val_city: state_manager.conversation_data["preferred_city"] = val_city
        if val_country: state_manager.conversation_data["preferred_country"] = val_country
        if val_abroad is not None: state_manager.conversation_data["study_abroad"] = val_abroad
        if val_pct: state_manager.conversation_data["percentage"] = val_pct
        if val_budget: state_manager.conversation_data["budget"] = val_budget
        if val_exam: state_manager.conversation_data["entrance_exam"] = val_exam
        if val_goal: state_manager.conversation_data["career_goal"] = val_goal
        if graph_state.get("_session_ended") or graph_state["current_node"] == "CLOSING":
            state_manager._session_ended = True

    is_terminal = (graph_state["current_node"] == "CLOSING") or bool(graph_state.get("_session_ended"))
    return reply, is_terminal

# ── RAG HINTS, PATTERNS, CONSTANTS ────────────────────────────────────────────
_BUDGET_PATTERN = re.compile(
    r"\b(?:budget|price|fee|fees|cost|range|around|approx|approximately|mera budget|budget hai|budget is)?\s*"
    r"(\d+(?:[.,]\d+)*(?:\s*(?:to|-|से)\s*\d+(?:[.,]\d+)*)?)\s*"
    r"(crore|crores|cr|lakh|lakhs|lac|lacs|thousand|k|करोड़|करोड|लाख|लख|हज़ार|हजार)?\b",
    re.IGNORECASE,
)

def _normalize_budget_unit(unit: str) -> str:
    unit = unit.lower()
    if unit in {"crores", "cr", "करोड़", "करोड"}:
        return "crore"
    if unit in {"lakhs", "lac", "lacs", "लाख", "लख"}:
        return "lakh"
    if unit in {"k", "हज़ार", "हजार"}:
        return "thousand"
    return unit

def _extract_budget_entity(user_text: str) -> str | None:
    text = (user_text or "").strip()
    if not text:
        return None
        
    clean_num_text = text.replace(",", "").replace("-", "").replace(" ", "")
    # Phone numbers (10 digits) should NOT be extracted as budget
    if re.search(r"\b[6-9]\d{9}\b", clean_num_text) or re.search(r"\b\d{10}\b", clean_num_text):
        return None

    # Check for raw numbers e.g. 50,000,000 or 50000000 or 5000000
    num_match = re.search(r"\b(\d{6,9})\b", clean_num_text)
    if num_match:
        val = int(num_match.group(1))
        if val >= 10000000:
            cr = val / 10000000
            return f"{int(cr) if cr.is_integer() else round(cr, 2)} crore"
        elif val >= 100000:
            lk = val / 100000
            return f"{int(lk) if lk.is_integer() else round(lk, 2)} lakh"

    # Pre-normalize phrases like "50 lakhs to 70 lakhs" -> "50 to 70 lakhs"
    normalized_text = re.sub(
        r"(\d+)\s*(?:lakh|lakhs|lac|lacs|crore|crores|cr|लाख)\s*(?:to|-|से)\s*(\d+)",
        r"\1 to \2",
        text,
        flags=re.IGNORECASE,
    )

    match = _BUDGET_PATTERN.search(normalized_text)
    if not match:
        return None
    val_str = match.group(1).strip()
    unit_str = match.group(2)
    
    if not unit_str:
        raw_val = val_str.replace(",", "")
        if raw_val.isdigit():
            val = int(raw_val)
            if val >= 10000000:
                return f"{val // 10000000} crore"
            elif val >= 100000:
                return f"{val // 100000} lakh"
        return None

    unit = _normalize_budget_unit(unit_str)
    if any(sep in val_str for sep in ["-", "to", "से"]):
        parts = re.split(r"\s*(?:-|to|से)\s*", val_str)
        if len(parts) == 2:
            return f"{parts[0]}-{parts[1]} {unit}"
            
    return f"{val_str} {unit}"

def _extract_course_entity(user_text: str) -> str | None:
    text = (user_text or "").strip().lower()
    if not text:
        return None
    courses_map = {
        "MCA": [r"\bmca\b", r"\bm\.c\.a\.\b", r"\bmaster of computer applications?\b"],
        "BCA": [r"\bbca\b", r"\bb\.c\.a\.\b", r"\bbachelor of computer applications?\b"],
        "B.Tech": [r"\bbtech\b", r"\bb\.tech\b", r"\bb\.e\.\b", r"\bbe\b", r"\bbachelor of technology\b"],
        "M.Tech": [r"\bmtech\b", r"\bm\.tech\b", r"\bm\.e\.\b", r"\bme\b", r"\bmaster of technology\b"],
        "MBA": [r"\bmba\b", r"\bm\.b\.a\.\b", r"\bmaster of business administration\b"],
        "B.Com": [r"\bbcom\b", r"\bb\.com\b"],
        "B.Sc": [r"\bbsc\b", r"\bb\.sc\b"],
        "M.Sc": [r"\bmsc\b", r"\bm\.sc\b"],
        "MBBS": [r"\bmbbs\b", r"\bm\.b\.b\.s\.\b"],
        "BBA": [r"\bbba\b", r"\bb\.b\.a\.\b"],
        "LLB": [r"\bllb\b", r"\bl\.l\.b\.\b"],
        "LLM": [r"\bllm\b", r"\bl\.l\.m\.\b"],
    }
    for canonical, patterns in courses_map.items():
        for pat in patterns:
            if re.search(pat, text):
                return canonical
    return None

def _extract_qualification_entity(user_text: str) -> str | None:
    text = (user_text or "").strip().lower()
    if not text:
        return None
    if re.search(r"\b(12th|12\s*th|hsc|intermediate|senior\s*secondary)\b", text):
        return "12th"
    doing_match = re.search(r"\b(?:doing|completed|passed|from|in|studied|studying)\s+(bca|mca|btech|mtech|mba|bcom|bsc|msc|mbbs|bba|llb|llm)\b", text)
    if doing_match:
        val = doing_match.group(1).upper()
        norm_map = {"BTECH": "B.Tech", "MTECH": "M.Tech", "BCOM": "B.Com", "BSC": "B.Sc", "MSC": "M.Sc"}
        return norm_map.get(val, val)
    return _extract_course_entity(user_text)

def _extract_city_entity(user_text: str) -> str | None:
    text = (user_text or "").strip().lower()
    if not text:
        return None
    cities = {
        "Pune": ["pune", "पुणे"],
        "Jaipur": ["jaipur", "जयपुर"],
        "Jodhpur": ["jodhpur", "जोधपुर"],
        "Mumbai": ["mumbai", "मुंबई", "bombay"],
        "Delhi": ["delhi", "new delhi", "दिल्ली"],
        "Bangalore": ["bangalore", "bengaluru", "बेंगलुरु"],
        "Hyderabad": ["hyderabad", "हैदराबाद"],
        "Chennai": ["chennai", "चेन्नई"],
        "Kolkata": ["kolkata", "calcutta"],
        "Ahmedabad": ["ahmedabad"],
    }
    for canonical, variants in cities.items():
        if any(v in text for v in variants):
            return canonical
    return None

def _extract_country_entity(user_text: str) -> str | None:
    text = (user_text or "").strip().lower()
    if not text:
        return None
    countries = {
        "USA": ["usa", "united states", "america"],
        "UK": ["uk", "united kingdom", "england"],
        "Canada": ["canada"],
        "Germany": ["germany"],
        "Australia": ["australia"],
        "India": ["india", "भारत"],
    }
    for canonical, variants in countries.items():
        if any(v in text for v in variants):
            return canonical
    return None

def _extract_study_abroad_entity(user_text: str) -> bool | None:
    text = (user_text or "").strip().lower()
    abroad_terms = ["study abroad", "abroad", "foreign", "outside india", "usa", "uk", "canada", "germany", "australia"]
    if any(term in text for term in abroad_terms):
        return True
    return None

def _extract_percentage_entity(user_text: str) -> str | None:
    text = (user_text or "").strip().lower()
    match = re.search(r"\b(\d{2}(?:\.\d{1,2})?)\s*(?:%|percent|pratisat|प्रतिशत)?\b", text)
    if match and ("%" in text or "percent" in text or "प्रतिशत" in text or "marks" in text or "gpa" in text or "score" in text or "got" in text or "received" in text or "aaya" in text or "aaye" in text):
        val = float(match.group(1))
        if 35.0 <= val <= 100.0:
            return f"{int(val) if val.is_integer() else val}%"
    return None

_CONFIRMATION_TEXTS = {"yes", "yeah", "yep", "sure", "ok", "okay", "haan", "ha", "haanji", "haji", "bilkul", "thik hai", "thik", "sahi hai", "हाँ", "ठीक है"}
_DENIAL_TEXTS = {"no", "nope", "nah", "na", "nahi", "nahin", "nhi", "नहीं"}

def _classify_local_intent(user_text: str) -> dict[str, Any] | None:
    clean_text = re.sub(r"[^\w\s'?]", " ", (user_text or "").strip().lower())
    clean_text = re.sub(r"\s+", " ", clean_text).strip()
    if not clean_text:
        return None

    entities: dict[str, Any] = {
        "current_qualification": None,
        "preferred_course": None,
        "preferred_specialization": None,
        "preferred_city": None,
        "preferred_country": None,
        "study_abroad": None,
        "percentage": None,
        "budget": None,
        "entrance_exam": None,
        "career_goal": None,
        "confirmation": None,
    }

    qual = _extract_qualification_entity(user_text)
    course = _extract_course_entity(user_text)
    city = _extract_city_entity(user_text)
    country = _extract_country_entity(user_text)
    abroad = _extract_study_abroad_entity(user_text)
    pct = _extract_percentage_entity(user_text)
    budget = _extract_budget_entity(user_text)

    # If user says "doing BCA and want MCA"
    multi_match = re.search(r"\b(?:doing|in|completed|passed)\s+([a-z0-9.]+)\s+.*(?:want|planning|looking for|pursue)\s+([a-z0-9.]+)\b", clean_text)
    if multi_match:
        q_candidate = _extract_course_entity(multi_match.group(1))
        c_candidate = _extract_course_entity(multi_match.group(2))
        if q_candidate: qual = q_candidate
        if c_candidate: course = c_candidate

    if qual: entities["current_qualification"] = qual
    if course: entities["preferred_course"] = course
    if city: entities["preferred_city"] = city
    if country: entities["preferred_country"] = country
    if abroad is not None: entities["study_abroad"] = abroad
    if pct: entities["percentage"] = pct
    if budget: entities["budget"] = budget

    if any(k in clean_text for k in ["bca", "mca", "btech", "mba", "mtech", "12th"]):
        if qual and course and qual != course:
            entities["current_qualification"] = qual
            entities["preferred_course"] = course
        elif course and not qual:
            entities["preferred_course"] = course

    if any(val is not None for val in entities.values()):
        return {"intent": "provide_info", "entities": entities}

    if clean_text in _CONFIRMATION_TEXTS:
        entities["confirmation"] = "yes"
        return {"intent": "confirm", "entities": entities}
    if clean_text in _DENIAL_TEXTS:
        entities["confirmation"] = "no"
        return {"intent": "deny", "entities": entities}

    return None

def _enrich_intent_entities(user_text: str, intent: str, entities: dict[str, Any], state_manager: Optional[Any] = None) -> tuple[str, dict[str, Any]]:
    entities = dict(entities)
    qual = _extract_qualification_entity(user_text)
    course = _extract_course_entity(user_text)
    city = _extract_city_entity(user_text)
    country = _extract_country_entity(user_text)
    abroad = _extract_study_abroad_entity(user_text)
    pct = _extract_percentage_entity(user_text)
    budget = _extract_budget_entity(user_text)

    if qual and not entities.get("current_qualification"): entities["current_qualification"] = qual
    if course and not entities.get("preferred_course"): entities["preferred_course"] = course
    if city and not entities.get("preferred_city"): entities["preferred_city"] = city
    if country and not entities.get("preferred_country"): entities["preferred_country"] = country
    if abroad is not None and entities.get("study_abroad") is None: entities["study_abroad"] = abroad
    if pct and not entities.get("percentage"): entities["percentage"] = pct
    if budget and not entities.get("budget"): entities["budget"] = budget

    if any(val is not None for val in entities.values()) and intent in {"unclear", "provide_info"}:
        intent = "provide_info"

    return intent, entities

def _extract_summary_from_prompt(global_prompt: str) -> str:
    """Extract complete company knowledge summary from global prompt template."""
    match = re.search(r"Complete Company Knowledge Summary:\n(.*)", global_prompt, re.DOTALL)
    if match:
        return match.group(1).strip()
    return global_prompt

async def _classify_message(
    user_text: str,
    current_node: Optional[dict[str, Any]],
    language: str,
) -> str:
    """Classify user text as node_response, company_question, general_query, small_talk, or unknown."""
    node_info = ""
    if current_node:
        node_response = current_node.get("response") or ""
        node_instruction = (current_node.get("instruction") or {}).get("text") or ""
        node_info = (
            f"Active Node Name: {current_node.get('name')}\n"
            f"Active Node Question/Prompt: {node_response}\n"
            f"Active Node Goal: {node_instruction}\n"
            f"Expected Slots to fill: {current_node.get('collects', [])}"
        )
    
    system_prompt = (
        "You are an expert intent classifier for a voice calling assistant.\n"
        "Analyze the user's message and the active node's context, and classify the user's intent into exactly one of these categories:\n\n"
        "1. \"node_response\": The user is answering the active node's question or providing details (like location, budget, name, availability, or preferences) related to the current sales/advisory flow.\n"
        "2. \"company_question\": The user is asking a factual question about the company itself, its products, services, CEO, founders, office location, contact info, support/helpdesk, pricing details, or general capabilities.\n"
        "3. \"general_query\": A standard conversational greeting, acknowledgment, or simple polite phrase (e.g. 'hello', 'ok', 'yes', 'no problem', 'thanks').\n"
        "4. \"small_talk\": Conversational chitchat unrelated to the company or current flow (e.g., 'how are you', 'what is your name', 'are you a robot').\n"
        "5. \"unknown\": The user's input is garbled, unclear, or does not fit any of the above categories.\n\n"
        "Format your response as a valid JSON object matching this schema:\n"
        "{\n"
        "  \"classification\": \"node_response\" | \"company_question\" | \"general_query\" | \"small_talk\" | \"unknown\",\n"
        "  \"reason\": \"A brief explanation of why this classification was chosen.\"\n"
        "}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": (
            f"Active Node Context:\n{node_info}\n\n"
            f"User Message: \"{user_text}\"\n"
            f"Language: {language}"
        )}
    ]

    try:
        completion = await _client.chat.completions.create(
            model=cfg.MODEL_NAME,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=100
        )
        raw_res = completion.choices[0].message.content or ""
        res_data = json.loads(raw_res)
        val = str(res_data.get("classification") or "node_response").strip().lower()
        if val in {"node_response", "company_question", "general_query", "small_talk", "unknown"}:
            return val
        return "node_response"
    except Exception as exc:
        logger.warning("Failed to classify user message: %s", exc)
        return "node_response"

def _pure_python_tfidf_similarity(query: str, docs: list[str]) -> list[float]:
    """Calculate TF-IDF Cosine Similarity in pure python. No sklearn needed!"""
    def tokenize(text: str) -> list[str]:
        return re.findall(r'\b\w+\b', text.lower())

    query_tokens = tokenize(query)
    doc_tokens_list = [tokenize(d) for d in docs]
    
    all_terms = set(query_tokens)
    for doc_tokens in doc_tokens_list:
        all_terms.update(doc_tokens)
        
    df = {}
    N = len(docs)
    for term in all_terms:
        df[term] = sum(1 for doc_tokens in doc_tokens_list if term in doc_tokens)
        
    idf = {}
    for term, doc_count in df.items():
        idf[term] = math.log((1 + N) / (1 + doc_count)) + 1.0

    doc_vectors = []
    for doc_tokens in doc_tokens_list:
        tf = Counter(doc_tokens)
        vec = {}
        for term in all_terms:
            if term in tf:
                vec[term] = tf[term] * idf[term]
        doc_vectors.append(vec)
        
    q_tf = Counter(query_tokens)
    q_vec = {}
    for term in all_terms:
        if term in q_tf:
            q_vec[term] = q_tf[term] * idf[term]
            
    def magnitude(vec: dict[str, float]) -> float:
        return math.sqrt(sum(v*v for v in vec.values()))
        
    q_mag = magnitude(q_vec)
    if q_mag == 0:
        return [0.0] * N
        
    similarities = []
    for d_vec in doc_vectors:
        d_mag = magnitude(d_vec)
        if d_mag == 0:
            similarities.append(0.0)
            continue
        dot_product = sum(q_vec.get(term, 0.0) * d_vec.get(term, 0.0) for term in q_vec)
        similarities.append(dot_product / (q_mag * d_mag))
        
    return similarities

def _retrieve_semantic_chunks_tfidf(query: str, summary_markdown: str) -> tuple[list[str], list[str], list[float]]:
    """Parse Markdown by H2 headers and use scikit-learn or pure python TF-IDF Cosine Similarity to retrieve chunks."""
    if not summary_markdown or not summary_markdown.strip():
        return [], [], []

    sections = re.split(r'\n(?=## )', "\n" + summary_markdown.strip())
    sections = [s.strip() for s in sections if s.strip()]
    if not sections:
        return [], [], []

    SYNONYMS = {
        "support": ["customer care", "helpdesk", "contact", "support", "complaint", "phone", "email", "address", "office", "location", "reach", "hours"],
        "contact": ["phone", "email", "address", "office", "location", "reach", "contact", "connect", "call", "map", "hours"],
        "ceo": ["ceo", "founder", "leadership", "owner", "president", "chief executive", "management", "head", "team"],
        "founder": ["ceo", "founder", "leadership", "owner", "president", "chief executive", "management", "head", "team"],
        "product": ["product", "project", "apartment", "flat", "villa", "plot", "pricing", "price", "cost", "offer", "luxury", "amenities", "rera"],
        "pricing": ["price", "cost", "pricing", "rate", "fee", "payment", "subscription", "offer", "discount"],
        "feature": ["feature", "amenity", "amenities", "specifications", "benefits", "technologies"],
        "security": ["security", "compliance", "privacy", "gdpr", "safe", "data protection"],
        "careers": ["careers", "job", "hiring", "culture", "employee", "work"],
        "headquarters": ["headquarters", "hq", "corporate office", "office", "location", "address", "contact"],
        "unique": ["unique", "differentiator", "why choose", "mission", "vision", "values", "core values", "advantages"],
    }

    query_words = re.findall(r'\b\w+\b', query.lower())
    expanded_words = set(query_words)
    for word in query_words:
        if word in SYNONYMS:
            expanded_words.update(SYNONYMS[word])
    expanded_query = " ".join(expanded_words)

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(sections)
        query_vec = vectorizer.transform([expanded_query])
        
        similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
    except Exception as exc:
        similarities = _pure_python_tfidf_similarity(expanded_query, sections)

    scored_sections = []
    for idx, score in enumerate(similarities):
        if score > 0.05:
            sec = sections[idx]
            lines = sec.split("\n")
            heading = lines[0].replace("#", "").strip() if lines else "Section"
            scored_sections.append((float(score), heading, sec))

    scored_sections.sort(key=lambda x: x[0], reverse=True)
    top_sections = scored_sections[:3]

    headings = [heading for score, heading, sec in top_sections]
    chunks = [sec for score, heading, sec in top_sections]
    scores = [score for score, heading, sec in top_sections]

    if not chunks and sections:
        for idx, sec in enumerate(sections):
            lines = sec.split("\n")
            heading = lines[0].replace("#", "").strip() if lines else "Section"
            if "overview" in heading.lower() or "about" in heading.lower():
                return [heading], [sec], [1.0]
        first_lines = sections[0].split("\n")
        first_heading = first_lines[0].replace("#", "").strip() if first_lines else "Overview"
        return [first_heading], [sections[0]], [1.0]

    return headings, chunks, scores

def _search_json_knowledge(user_text: str, nodes: list[dict[str, Any]], language: str = "en", domain: str = "real_estate") -> Optional[str]:
    """Check if the user's query can be answered directly by predefined company facts or JSON nodes."""
    query_clean = user_text.lower().strip().rstrip("?").strip()
    
    # 0ms Direct Lookup for General Company Overview Questions
    company_overview_triggers = [
        "what company is this",
        "who are you",
        "what do you do",
        "tell me about your company",
        "which company are you calling from"
    ]
    if any(trigger in query_clean for trigger in company_overview_triggers):
        if domain == "education":
            if language in ("hi", "hinglish"):
                return "हम एक एजुकेशन काउंसलिंग प्लेटफॉर्म हैं जो स्टूडेंट्स को सही कोर्स, कॉलेज, एंट्रेंस एग्जाम और स्टडी एब्रॉड के लिए गाइड करते हैं।"
            elif language == "mr":
                return "आम्ही एक एज्युकेशन कौन्सिलिंग प्लॅटफॉर्म आहोत जो विद्यार्थ्यांना योग्य कोर्स, कॉलेज आणि अभ्यासासाठी मार्गदर्शन करतो."
            return "We are an AI Education Counselling platform helping students discover suitable courses, colleges, entrance exams, and study abroad options."
        else:
            if language in ("hi", "hinglish"):
                return "सनसिटी अपार्टमेंट्स जयपुर, जोधपुर और मदुरै में स्थित एक अग्रणी रियल एस्टेट डेवलपर है।"
            return "Suncity Apartments is a premier real estate developer operating in Jaipur, Jodhpur, and Madurai."

    for node in nodes:
        node_name = (node.get("name") or "").lower()
        node_resp = (node.get("response") or "").lower()
        if "ceo" in query_clean and "ceo" in node_name:
            if node.get("response"):
                return node.get("response")
        if "headquarters" in query_clean or "hq" in query_clean or "office" in query_clean:
            if "office" in node_name or "headquarter" in node_name:
                if node.get("response"):
                    return node.get("response")
            if domain == "real_estate":
                if language in ("hi", "hinglish"):
                    return "सनसिटी अपार्टमेंट्स का headquarters जयपुर में स्थित है।"
                return "Suncity Apartments headquarters is located in Jaipur."
            elif domain == "education":
                if language in ("hi", "hinglish"):
                    return "हमारा मुख्य कार्यालय पुणे में स्थित है।"
                return "Our headquarters is located in Pune."
        if "support" in query_clean or "contact" in query_clean or "help" in query_clean:
            if "support" in node_name or "contact" in node_name:
                if node.get("response"):
                    return node.get("response")
    for node in nodes:
        node_name = (node.get("name") or "").lower()
        if node_name and node_name in query_clean:
            if node.get("response"):
                return node.get("response")
    return None

async def _generate_answer_from_chunks(user_text: str, retrieved_chunks: list[str], language: str, domain: str = "real_estate") -> str:
    """Generate dynamic response based on retrieved semantic chunks."""
    context = "\n\n".join(retrieved_chunks)
    active_persona = _AAROHI_PERSONA if domain == "education" else _NEHA_PERSONA
    system_prompt = (
        f"{active_persona}\n"
        "Answer the user's question using ONLY verified facts from the context below.\n\n"
        "Verified Context:\n"
        f"{context}\n\n"
        "Constraints:\n"
        "- Do not assume, guess, or hallucinate any details. If the exact answer is not present in the verified facts, say: "
        "'I don't have that detail right now, but I can check and get back to you.'\n"
        "- Keep response to 1 to 2 spoken sentences (max 25 words).\n"
        f"- Respond in the requested active language: {language}."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text}
    ]
    try:
        completion = await _call_groq_with_retry(messages, cfg.MODEL_NAME, max_tokens=80, temperature=0.2, max_attempts=2)
        clean = (completion or "").strip()
        if clean:
            return clean
    except Exception as exc:
        logger.error("Failed generating LLM answer from chunks: %s", exc)
    
    if domain == "education":
        if language in ("hi", "hinglish"):
            return "हम स्टूडेंट्स को सही कोर्स, कॉलेज और स्टडी एब्रॉड चुनने में मदद करते हैं।"
        return "We help students discover suitable courses, colleges, and study abroad options."
    else:
        if language in ("hi", "hinglish"):
            return "सनसिटी अपार्टमेंट्स जयपुर, जोधपुर और मदुरै में स्थित एक अग्रणी रियल एस्टेट डेवलपर है।"
        return "Suncity Apartments is a premier real estate developer operating in Jaipur, Jodhpur, and Madurai."

async def _generate_llm_fallback_answer(user_text: str, summary_markdown: str, language: str, domain: str = "real_estate") -> str:
    """Fallback LLM call when no specific chunks are retrieved, using the whole summary context."""
    active_persona = _AAROHI_PERSONA if domain == "education" else _NEHA_PERSONA
    system_prompt = (
        f"{active_persona}\n"
        "Answer the user's question using ONLY the company summary context below.\n\n"
        "Company Summary Context:\n"
        f"{summary_markdown}\n\n"
        "Constraints:\n"
        "- Do not assume, guess, or hallucinate any details. If the answer is not explicitly in the summary context, say: "
        "'I don't have that detail right now, but I can check and get back to you.'\n"
        "- Keep response to 1 to 2 spoken sentences (max 25 words).\n"
        f"- Respond in the requested active language: {language}."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text}
    ]
    try:
        completion = await _call_groq_with_retry(messages, cfg.MODEL_NAME, max_tokens=80, temperature=0.2, max_attempts=2)
        clean = (completion or "").strip()
        if clean:
            return clean
    except Exception as exc:
        logger.error("Failed generating LLM fallback answer: %s", exc)
    
    if domain == "education":
        if language in ("hi", "hinglish"):
            return "हम स्टूडेंट्स को सही कोर्स, कॉलेज और स्टडी एब्रॉड चुनने में मदद करते हैं।"
        return "We help students discover suitable courses, colleges, and study abroad options."
    else:
        if language in ("hi", "hinglish"):
            return "सनसिटी अपार्टमेंट्स जयपुर, जोधपुर और मदुरै में स्थित एक अग्रणी रियल एस्टेट डेवलपर है।"
        return "Suncity Apartments is a premier real estate developer operating in Jaipur, Jodhpur, and Madurai."

def _get_resume_bridge(
    current_node: Optional[dict[str, Any]],
    context: dict[str, Any],
    language: str,
) -> tuple[str, str]:
    """Returns (resume_question, combined_bridge_text) to return to previous flow node."""
    if not current_node or not isinstance(current_node, dict):
        return "", ""
    from .llm_response_generator import _resolve_template_response
    
    resume_question = _resolve_template_response(current_node, context, language)
    if not resume_question:
        return "", ""

    resume_question_clean = resume_question.strip().rstrip("?").rstrip()
    if not resume_question_clean:
        return "", ""

    if language in ("hi", "hinglish"):
        prefix = "Toh, hamari baat-cheet par waapas aate hain, "
    elif language == "mr":
        prefix = "तर, आपल्या संभाषणाकडे परत येत, "
    else:
        prefix = "Now, coming back to our discussion, "

    combined = f"{prefix}{resume_question_clean}?"
    return resume_question_clean, combined

generate_informational_response = _generate_answer_from_chunks
generate_phrase_constrained_response = _generate_answer_from_chunks

async def _async_call_groq_api(
    messages: list[dict[str, str]],
    *,
    max_tokens: int,
    temperature: float,
    response_format: Optional[dict[str, str]] = None,
) -> str:
    """Call Groq with retry + exponential backoff. Returns raw content string.

    Issue 13 fix: backoff uses asyncio.sleep instead of time.sleep to avoid blocking worker threads.
    """
    for attempt in range(1, cfg.MAX_RETRIES + 1):
        try:
            t0 = time.time()
            completion = await _client.chat.completions.create(
                model=cfg.MODEL_NAME,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=cfg.TOP_P,
                response_format=response_format,
            )
            latency = time.time() - t0
            logger.info("LLM request completed in %.3fs (attempt %d/%d)", latency, attempt, cfg.MAX_RETRIES)
            return completion.choices[0].message.content or ""
        except RateLimitError:
            wait = (2 ** attempt) + _random.uniform(0, 0.5)   # jitter
            logger.warning("Groq rate limit hit (attempt %d/%d) — retrying in %.1fs", attempt, cfg.MAX_RETRIES, wait)
            if attempt < cfg.MAX_RETRIES:
                await asyncio.sleep(wait)
        except APITimeoutError:
            logger.error("Groq request timed out (attempt %d/%d)", attempt, cfg.MAX_RETRIES)
            if attempt == cfg.MAX_RETRIES:
                return ""
            await asyncio.sleep(1.0)
        except APIError as exc:
            logger.error("Groq API error (attempt %d/%d): %s", attempt, cfg.MAX_RETRIES, exc)
            return ""
    return ""

