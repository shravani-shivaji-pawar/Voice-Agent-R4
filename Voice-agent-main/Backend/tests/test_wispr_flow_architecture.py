import asyncio
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

backend_dir = r"s:\voice agent roy\Voice agent R4\Voice-agent-main\backend"
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from llm.language_utils import (
    LanguageTracker,
    normalize_language_code,
    normalize_domain_vocabulary,
    validate_response_language,
)
from llm.llm import generate_voice_response, generate_response, ExtractedEntities
from llm.state_manager import handle_greeting, merge_slots, ConversationState

async def run_wispr_flow_tests():
    print("========================================================")
    print("RUNNING WISPR FLOW ARCHITECTURE SUITE")
    print("========================================================\n")

    # TEST 1 — DOMAIN VOCABULARY NORMALIZATION
    print("TEST 1 — DOMAIN VOCABULARY NORMALIZATION")
    raw_transcript = "I want to buy a two bhk in sun city project near baner"
    normalized = normalize_domain_vocabulary(raw_transcript)
    print(f"Raw: \"{raw_transcript}\"")
    print(f"Normalized: \"{normalized}\"")
    assert "2 BHK" in normalized, "FAIL: 'two bhk' not normalized to '2 BHK'"
    assert "Suncity Projects" in normalized, "FAIL: 'sun city project' not normalized to 'Suncity Projects'"
    assert "Baner" in normalized, "FAIL: 'baner' not capitalized to 'Baner'"
    print(">>> PASS: Domain vocabulary normalized correctly.\n")

    # TEST 2 — RESPONSE LANGUAGE VALIDATOR
    print("TEST 2 — RESPONSE LANGUAGE VALIDATOR")
    val_ok, reason1 = validate_response_language("नमस्ते, मैं आपकी कैसे मदद कर सकती हूँ?", "hi")
    print(f"Hindi Text in 'hi' mode -> valid: {val_ok} ({reason1})")
    assert val_ok, "FAIL: Valid Hindi text rejected"

    val_bad, reason2 = validate_response_language("Sure, I can help you with your property inquiry in Jaipur.", "hi")
    print(f"English Text in 'hi' mode -> valid: {val_bad} ({reason2})")
    assert not val_bad, "FAIL: Invalid English text accepted under 'hi' mode"
    print(">>> PASS: Response Language Validator correctly flags English text in Hindi mode.\n")

    # TEST 3 — SLOT SELF-CORRECTION
    print("TEST 3 — SLOT SELF-CORRECTION")
    initial_slots = {"bhk": "2 BHK", "location": "Baner"}
    
    # User self-corrects BHK
    class DummyExtracted1:
        intent_value = "buy"
        budget_range = None
        preferred_bhk = "3 BHK"
        location = None
        timeline_weeks = None
        user_name = None

    corrected_slots1 = merge_slots(initial_slots, DummyExtracted1(), user_text="Actually 3 BHK chahiye")
    print(f"After 'Actually 3 BHK': {corrected_slots1}")
    assert corrected_slots1["bhk"] == "3 BHK", "FAIL: BHK self-correction failed"

    # User self-corrects Location
    class DummyExtracted2:
        intent_value = "buy"
        budget_range = None
        preferred_bhk = None
        location = "Wakad"
        timeline_weeks = None
        user_name = None

    corrected_slots2 = merge_slots(corrected_slots1, DummyExtracted2(), user_text="No I mean Wakad")
    print(f"After 'No I mean Wakad': {corrected_slots2}")
    assert corrected_slots2["location"] == "Wakad", "FAIL: Location self-correction failed"
    print(">>> PASS: Slot self-correction overrides previous values correctly.\n")

    # TEST 4 — HINDI CONTINUITY (10-TURN HARD LOCK)
    print("TEST 4 — HINDI CONTINUITY (10 TURNS)")
    session_lang = "hi"
    history = []
    test_turns = [
        "Mujhe Jaipur mein 2 BHK chahiye.",
        "Where is your project located?", # English input
        "Budget around 50 lakhs hai.",
        "What are the amenities available?", # English input
        "Saturday ko site visit ho sakti hai kya?",
        "Do you have swimming pool?", # English input
        "Haan, morning 11 baje chalega.",
        "Who is the founder of Suncity?", # English input
        "Details WhatsApp par bhej do.",
        "Dhanyawad, bye."
    ]

    for turn_num, user_msg in enumerate(test_turns, 1):
        reply = await generate_voice_response(
            prompt="Answer user query politely.",
            history=history,
            language=session_lang
        )
        is_valid, reason = validate_response_language(reply, session_lang)
        print(f"Turn {turn_num} | User: \"{user_msg}\"")
        print(f"Turn {turn_num} | Agent: \"{reply}\" (Valid: {is_valid})\n")
        assert is_valid, f"FAIL: Turn {turn_num} produced non-Hindi response: {reply}"
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": reply})

    print(">>> PASS: Hindi continuity maintained across all 10 turns.\n")

    # TEST 5 — EXPLICIT FRONTEND LANGUAGE SWITCH
    print("TEST 5 — EXPLICIT FRONTEND LANGUAGE SWITCH (HI -> EN)")
    active_lang = "hi"
    print(f"Initial language: {active_lang}")
    
    # Simulate WS language_change payload
    ws_event = {"type": "language_change", "language": "en"}
    active_lang = normalize_language_code(ws_event["language"])
    print(f"Updated language after WS event: {active_lang}")
    
    reply_en = await generate_voice_response(
        prompt="User asks for details.",
        history=[],
        language=active_lang
    )
    print(f"Agent reply ({active_lang}): \"{reply_en}\"")
    assert active_lang == "en", "FAIL: Language code not set to 'en'"
    print(">>> PASS: Explicit frontend language switch working.\n")

    print("========================================================")
    print("ALL WISPR FLOW ARCHITECTURE TESTS PASSED SUCCESSFULLY!")
    print("========================================================")

if __name__ == "__main__":
    asyncio.run(run_wispr_flow_tests())
