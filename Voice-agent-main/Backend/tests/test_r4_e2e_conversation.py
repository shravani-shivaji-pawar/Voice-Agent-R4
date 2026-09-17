import asyncio
import os
import sys
import io
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

backend_dir = r"s:\voice agent roy\Voice agent R4\Voice-agent-main\backend"
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from llm.language_utils import normalize_language_code, validate_response_language
from llm.llm import generate_response, generate_voice_response
from llm.state_manager import StateManager

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_SCHEMA_PATH = os.path.join(_ROOT, "Updated_Real_Estate_Agent.json")

async def test_initial_greeting_languages():
    print("========================================================")
    print("TESTING PRE-GREETING SESSION LANGUAGE INITIALIZATION")
    print("========================================================\n")

    for lang in ["hi", "hinglish", "en"]:
        state_mgr = StateManager(STATE_SCHEMA_PATH)
        state_mgr.reset_state(language=lang)
        greeting, _ = await generate_response(
            user_text="__CONNECTED__",
            conversation_history=[],
            language=lang,
            state_manager=state_mgr
        )
        print(f"Pre-Greeting [{lang}]: \"{greeting}\"")
        if lang == "hi":
            assert "नमस्ते" in greeting or "प्रिया" in greeting, f"FAIL: Initial greeting for Hindi was not in Hindi script: {greeting}"
        elif lang == "hinglish":
            assert "Namaste" in greeting or "Suncity" in greeting, f"FAIL: Initial greeting for Hinglish was not Hinglish: {greeting}"
        elif lang == "en":
            assert "Hello" in greeting or "Hi" in greeting or "Priya" in greeting, f"FAIL: Initial greeting for English was not English: {greeting}"
        print(f">>> PASS: Initial greeting for '{lang}' verified successfully.\n")


async def test_english_conversation_flow():
    print("========================================================")
    print("TESTING REAL RUNTIME Pipeline — ENGLISH CONVERSATION")
    print("========================================================\n")

    state_mgr = StateManager(STATE_SCHEMA_PATH)
    state_mgr.reset_state(language="en")
    history = []
    session_lang = "en"

    # Turn 1: Initial Greeting
    t0 = time.monotonic()
    greeting_reply, _ = await generate_response(
        user_text="__CONNECTED__",
        conversation_history=history,
        language=session_lang,
        state_manager=state_mgr
    )
    t_llm = time.monotonic() - t0
    print(f"Agent Greeting (LLM: {t_llm*1000:.1f}ms): \"{greeting_reply}\"")
    history.append({"role": "assistant", "content": greeting_reply})

    # Turn 2: User says "Okay."
    t0 = time.monotonic()
    reply2, _ = await generate_response(
        user_text="Okay.",
        conversation_history=history,
        language=session_lang,
        state_manager=state_mgr
    )
    t_llm = time.monotonic() - t0
    print(f"User: \"Okay.\"")
    print(f"Agent (LLM: {t_llm*1000:.1f}ms): \"{reply2}\"")
    history.append({"role": "user", "content": "Okay."})
    history.append({"role": "assistant", "content": reply2})

    # Turn 3: User says "I want a 2 BHK in Baner."
    t0 = time.monotonic()
    reply3, _ = await generate_response(
        user_text="I want a 2 BHK in Baner.",
        conversation_history=history,
        language=session_lang,
        state_manager=state_mgr
    )
    t_llm = time.monotonic() - t0
    print(f"\nUser: \"I want a 2 BHK in Baner.\"")
    print(f"Agent (LLM: {t_llm*1000:.1f}ms): \"{reply3}\"")
    history.append({"role": "user", "content": "I want a 2 BHK in Baner."})
    history.append({"role": "assistant", "content": reply3})

    # Turn 4: User says "My budget is 80 lakh."
    t0 = time.monotonic()
    reply4, _ = await generate_response(
        user_text="My budget is 80 lakh.",
        conversation_history=history,
        language=session_lang,
        state_manager=state_mgr
    )
    t_llm = time.monotonic() - t0
    print(f"\nUser: \"My budget is 80 lakh.\"")
    print(f"Agent (LLM: {t_llm*1000:.1f}ms): \"{reply4}\"")
    history.append({"role": "user", "content": "My budget is 80 lakh."})
    history.append({"role": "assistant", "content": reply4})

    # Turn 5: User says "Thanks, bye"
    reply5, is_terminal = await generate_response(
        user_text="Thanks, bye",
        conversation_history=history,
        language=session_lang,
        state_manager=state_mgr
    )
    print(f"\nUser: \"Thanks, bye\"")
    print(f"Agent: \"{reply5}\" (Terminal: {is_terminal})")
    assert is_terminal or state_mgr.current_node_id == "CLOSING" or state_mgr._session_ended, "FAIL: Goodbye did not close session"

    data = state_mgr.conversation_data
    print(f"\nExtracted State: {data}")
    print(">>> PASS: English E2E conversation completed successfully.\n")


async def test_hindi_full_runtime_flow():
    print("========================================================")
    print("TESTING HINDI E2E FLOW — SLOTS, HQ QUESTION & GOODBYE")
    print("========================================================\n")

    state_mgr = StateManager(STATE_SCHEMA_PATH)
    state_mgr.reset_state(language="hi")
    history = []
    session_lang = "hi"

    # Turn 1: Initial Greeting
    reply1, _ = await generate_response("__CONNECTED__", history, language=session_lang, state_manager=state_mgr)
    history.append({"role": "assistant", "content": reply1})
    print(f"Turn 1 (Greeting) | Agent: '{reply1}'")
    assert "नमस्ते" in reply1, f"FAIL: Initial greeting not in Hindi: {reply1}"

    # Turn 2: User says "मुझे जयपुर में 2 BHK फ्लैट देखना है।"
    reply2, _ = await generate_response("मुझे जयपुर में 2 BHK फ्लैट देखना है।", history, language=session_lang, state_manager=state_mgr)
    history.append({"role": "user", "content": "मुझे जयपुर में 2 BHK फ्लैट देखना है。"})
    history.append({"role": "assistant", "content": reply2})
    print(f"Turn 2 | User: 'मुझे जयपुर में 2 BHK फ्लैट देखना है。'")
    print(f"Turn 2 | Agent: '{reply2}'")
    loc = state_mgr.conversation_data.get("location") or state_mgr.conversation_data.get("preferred_city")
    assert loc == "Jaipur", f"FAIL: Location 'Jaipur' not captured, got {loc}"
    bhk = state_mgr.conversation_data.get("property_type") or state_mgr.conversation_data.get("bhk") or state_mgr.conversation_data.get("preferred_bhk") or state_mgr.conversation_data.get("preferred_course")
    assert (bhk and ("2 BHK" in str(bhk) or "2" in str(bhk))) or "2 BHK" in reply2 or "BHK" in reply2, f"FAIL: BHK '2 BHK' not captured, got {bhk}"

    # Turn 3: User provides numeric budget ("50,000,000 है")
    reply3, _ = await generate_response("50,000,000 है", history, language=session_lang, state_manager=state_mgr)
    history.append({"role": "user", "content": "50,000,000 है"})
    history.append({"role": "assistant", "content": reply3})
    print(f"Turn 3 | User: '50,000,000 है'")
    print(f"Turn 3 | Agent: '{reply3}'")
    assert "5 crore" in str(state_mgr.conversation_data.get("budget")), f"FAIL: Numeric '50,000,000' not normalized to 5 crore. Got: {state_mgr.conversation_data.get('budget')}"

    # Turn 4: User asks HQ question ("इसका headquarters कहाँ है?")
    reply4, _ = await generate_response("इसका headquarters कहाँ है?", history, language=session_lang, state_manager=state_mgr)
    history.append({"role": "user", "content": "इसका headquarters कहाँ है?"})
    history.append({"role": "assistant", "content": reply4})
    print(f"Turn 4 | User: 'इसका headquarters कहाँ है?'")
    print(f"Turn 4 | Agent: '{reply4}'")
    assert "जयपुर" in reply4 or "Jaipur" in reply4, f"FAIL: HQ question not answered correctly: {reply4}"
    assert "Toh, hamari baat-cheet par waapas aate hain" not in reply4, "FAIL: Unnecessary resume bridge appended"

    # Turn 5: User says "ठीक है, धन्यवाद। बाय।"
    reply5, is_term5 = await generate_response("ठीक है, धन्यवाद। बाय。", history, language=session_lang, state_manager=state_mgr)
    print(f"Turn 5 | User: 'ठीक है, धन्यवाद। बाय。'")
    print(f"Turn 5 | Agent: '{reply5}' (Terminal: {is_term5})")
    assert is_term5 or any(term in reply5 for term in ["धन्यवाद", "शुभ", "ज़रूर", "स्वागत", "समझ", "जी", "फिर", "बाय"]), "FAIL: Closing sign-off was not warm Hindi"

    print(">>> PASS: Hindi E2E flow verified successfully.\n")


async def main():
    await test_initial_greeting_languages()
    await test_english_conversation_flow()
    await test_hindi_full_runtime_flow()

if __name__ == "__main__":
    asyncio.run(main())
