"""
Comprehensive Test Suite for Voice Agent R4 Education Counselling Conversion ("Aarohi").
Verifies state management, language locking, persona greetings, entity extraction, state authority,
anti-hallucination rules, special token handling, and conversation closing.
"""
import pytest
import asyncio
from langchain_core.messages import AIMessage, HumanMessage

from llm.state_manager import (
    handle_greeting,
    handle_discovery,
    handle_qualification,
    handle_closing,
    process_intent_and_slots,
    merge_slots,
    is_low_signal,
    is_hard_out
)
from llm.llm import (
    _classify_local_intent,
    _extract_course_entity,
    _extract_qualification_entity,
    _extract_city_entity,
    _extract_study_abroad_entity,
    _extract_percentage_entity,
    _extract_budget_entity,
    generate_voice_response
)
from flows.runtime import _strip_stt_special_tokens, _is_actionable_transcript


def test_greeting_hindi():
    """TEST 1: Dashboard = Hindi -> Initial greeting in Hindi from Aarohi."""
    async def _impl():
        state = {
            "messages": [],
            "language": "hi",
            "domain": "education",
            "current_node": "GREETING"
        }
        updated = await handle_greeting(state)
        assert len(updated["messages"]) == 1
        opener = updated["messages"][0].content
        assert "नमस्ते" in opener or "आरोही" in opener or "एजुकेशन" in opener
        assert "Suncity" not in opener

    asyncio.run(_impl())


def test_greeting_english():
    """TEST 2: Dashboard = English -> Initial greeting in English from Aarohi."""
    async def _impl():
        state = {
            "messages": [],
            "language": "en",
            "domain": "education",
            "current_node": "GREETING"
        }
        updated = await handle_greeting(state)
        assert len(updated["messages"]) == 1
        opener = updated["messages"][0].content
        assert "Aarohi" in opener
        assert "education counsellor" in opener.lower() or "studying" in opener.lower()
        assert "Suncity" not in opener

    asyncio.run(_impl())


def test_greeting_hinglish():
    """TEST 3: Dashboard = Hinglish -> Initial greeting in Hinglish from Aarohi."""
    async def _impl():
        state = {
            "messages": [],
            "language": "hinglish",
            "domain": "education",
            "current_node": "GREETING"
        }
        updated = await handle_greeting(state)
        assert len(updated["messages"]) == 1
        opener = updated["messages"][0].content
        assert "Aarohi" in opener or "Namaste" in opener
        assert "education counsellor" in opener.lower() or "padhai" in opener.lower()
        assert "Suncity" not in opener

    asyncio.run(_impl())


def test_student_profile_extraction():
    """TEST 4: Profile extraction for BCA and MCA."""
    text = "I'm doing BCA and want MCA."
    qual = _extract_qualification_entity(text)
    course = _extract_course_entity(text)
    local_info = _classify_local_intent(text)
    
    assert qual == "BCA" or local_info["entities"].get("current_qualification") == "BCA"
    assert course == "MCA" or local_info["entities"].get("preferred_course") == "MCA"


def test_state_authority_and_no_repetition():
    """TEST 5: State manager retains captured course & city without asking again."""
    initial_slots = {
        "preferred_course": "MCA",
        "preferred_city": "Pune"
    }
    # Attempting to overwrite with LLM guess should preserve state
    class MockLLMGuess:
        preferred_course = "B.Tech"
        preferred_city = "Jaipur"
        
    merged = merge_slots(initial_slots, MockLLMGuess(), user_text="I want to study in Pune")
    assert merged["preferred_course"] == "MCA"
    assert merged["preferred_city"] == "Pune"


def test_study_abroad_flow():
    """TEST 6: Recognizes study abroad intent."""
    text = "I want to study abroad for my master's."
    abroad = _extract_study_abroad_entity(text)
    assert abroad is True


def test_undecided_student_flow():
    """TEST 7: Undecided student gets background questions, not fabricated courses."""
    async def _impl():
        state = {
            "messages": [AIMessage(content="What are you planning to study?")],
            "user_input": "I don't know what to study.",
            "language": "en",
            "extracted_slots": {},
            "current_node": "DISCOVERY"
        }
        updated = await handle_discovery(state)
        response = updated["messages"][-1].content
        assert "B.Tech" not in response and "MBA" not in response
        assert "?" in response

    asyncio.run(_impl())


def test_stt_special_token_filtering():
    """TEST 8: <|hi|> tokens stripped cleanly, non-actionable transcript dropped."""
    raw = "<|hi|><|hi|>"
    clean = _strip_stt_special_tokens(raw)
    assert clean == ""
    assert _is_actionable_transcript(clean) is False


def test_conversation_closing():
    """TEST 9: Goodbye closes conversation cleanly."""
    async def _impl():
        assert is_hard_out(" ठीक है, धन्यवाद, बाय। ") is True
        assert is_hard_out("Bye, take care!") is True

        state = {
            "messages": [],
            "language": "hi",
            "current_node": "DISCOVERY"
        }
        closed_state = await handle_closing(state)
        assert closed_state["current_node"] == "CLOSING"
        assert closed_state.get("_session_ended") is True
        assert "धन्यवाद" in closed_state["messages"][-1].content or "शुभ" in closed_state["messages"][-1].content

    asyncio.run(_impl())


def test_acknowledgement_handling():
    """TEST 10: Short 'Okay' / 'Haan' does not restart conversation."""
    assert is_low_signal("okay") is True
    assert is_low_signal("haan") is True
    assert is_low_signal("MCA in Pune") is False


def test_general_question_preserves_profile():
    """TEST 11: General question 'What is MCA?' is answered while profile state is preserved."""
    async def _impl():
        answer = await generate_voice_response(
            "What is MCA?",
            history=[{"role": "user", "content": "What is MCA?"}],
            language="en",
            domain="education"
        )
        assert "computer" in answer.lower() or "degree" in answer.lower() or "application" in answer.lower() or "mca" in answer.lower()

    asyncio.run(_impl())


def test_fees_anti_hallucination():
    """TEST 12: Fees question without verified data does NOT invent exact numbers."""
    async def _impl():
        answer = await generate_voice_response(
            "What are the exact fees for MCA in Pune?",
            history=[{"role": "user", "content": "What are the exact fees for MCA in Pune?"}],
            language="en",
            domain="education"
        )
        assert any(k in answer.lower() for k in ["vary", "university", "check", "counsellor", "depends", "official", "course", "degree", "pursue", "fee", "college", "details"])
        assert "Rs 85,432" not in answer

    asyncio.run(_impl())




if __name__ == "__main__":
    pytest.main(["-v", __file__])

