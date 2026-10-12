import sys
import os
import json
import asyncio

sys.path.insert(0, r"s:\voice agent roy\Voice agent R4\Voice-agent-main\Backend")

from flows.v2 import validate_flow_spec
from main import _flow_v2_to_runtime_conversation_flow
from llm.state_manager import StateManager
from llm.llm import generate_response

flow_spec = {
    "schema_version": "2.0",
    "id": "mock_interview_coach_flow",
    "name": "Mock Interview Coach",
    "start_node_id": "node_1",
    "default_locale": "en",
    "runtime_mode": "live",
    "status": "published",
    "nodes": [
        {
            "id": "node_1",
            "type": "message",
            "label": "Spoken Question",
            "response": {"en": "what is your name ??"},
            "transitions": [
                {"intent": "confirm", "label": "Continue", "target": "greeting"}
            ]
        },
        {
            "id": "greeting",
            "type": "message",
            "label": "Greeting",
            "response": {"en": "Hello, this is Mock Interview Coach. Am I speaking with {{name}}?"},
            "transitions": [
                {"intent": "confirm", "label": "Confirm", "target": "discovery"},
                {"intent": "deny", "label": "Deny", "target": "end_node"},
                {"intent": "unclear", "label": "Unclear", "target": "clarify"}
            ]
        },
        {
            "id": "discovery",
            "type": "message",
            "label": "Discovery",
            "response": {"en": "Could you share a little about what you are looking for?"},
            "transitions": [
                {"intent": "provide_info", "label": "Provide Info", "target": "confirm_follow_up"},
                {"intent": "confirm", "label": "Confirm", "target": "confirm_follow_up"},
                {"intent": "unclear", "label": "Unclear", "target": "clarify"}
            ]
        },
        {
            "id": "clarify",
            "type": "fallback",
            "label": "Clarification / Fallback",
            "response": {"en": "Sorry, I did not catch that clearly. Could you repeat it once?"},
            "transitions": [
                {"intent": "provide_info", "label": "Provide Info", "target": "discovery"},
                {"intent": "confirm", "label": "Confirm", "target": "discovery"},
                {"intent": "deny", "label": "Deny", "target": "end_node"},
                {"intent": "unclear", "label": "Unclear", "target": "clarify"}
            ]
        },
        {
            "id": "confirm_follow_up",
            "type": "message",
            "label": "Confirm Follow-up",
            "response": {"en": "Thanks. I will have the team follow up with the right details."},
            "transitions": [
                {"intent": "confirm", "label": "Confirm", "target": "end_node"},
                {"intent": "deny", "label": "Deny", "target": "end_node"},
                {"intent": "unclear", "label": "Unclear", "target": "clarify"}
            ]
        },
        {
            "id": "end_node",
            "type": "end",
            "label": "Conversation End",
            "response": {"en": "Thank you. Have a good day."},
            "transitions": []
        }
    ]
}

mock_interview_system_prompt = (
    "You are an expert AI Mock Interview Coach. "
    "Your job is to assist users in preparing for job interviews, conduct realistic interactive mock interviews, "
    "generate relevant technical and behavioral interview questions and answers, and evaluate user responses. "
    "Always maintain a encouraging, professional tone as a Mock Interview Coach."
)

def create_state_manager():
    validated = validate_flow_spec(flow_spec)
    runtime_flow = _flow_v2_to_runtime_conversation_flow(validated)
    schema = {
        "agent_name": "Mock Interview Coach",
        "system_prompt": mock_interview_system_prompt,
        "start_node_id": runtime_flow["start_node_id"],
        "conversationFlow": runtime_flow
    }
    return StateManager(schema)

async def test_llm_restoration():
    print("=============================================================")
    print("TESTING RESTORED MOCK INTERVIEW COACH LLM INTELLIGENCE & FLOW")
    print("=============================================================")

    sm = create_state_manager()
    history = []

    # 1. Connected start node
    r0, _ = await generate_response("__CONNECTED__", history, language="en", state_manager=sm)
    print(f"\n[Turn 0 - Start Node]: '{r0}'")
    assert r0 == "what is your name ??", f"FAIL Turn 0: '{r0}'"

    # 2. Provide Name
    history.append({"role": "assistant", "content": r0})
    r1, _ = await generate_response("Radha", history, language="en", state_manager=sm)
    print(f"[Turn 1 - Name -> Greeting]: '{r1}'")
    assert "Am I speaking with Radha?" in r1, f"FAIL Turn 1: '{r1}'"

    # 3. Confirm Identity
    history.append({"role": "user", "content": "Radha"})
    history.append({"role": "assistant", "content": r1})
    r2, _ = await generate_response("Yes", history, language="en", state_manager=sm)
    print(f"[Turn 2 - Confirm Identity -> Discovery]: '{r2}'")
    assert "what you are looking for" in r2.lower() or "discovery" in sm.current_node_id, f"FAIL Turn 2: '{r2}'"

    # 4. User asks persona question: "What do you do?"
    history.append({"role": "user", "content": "Yes"})
    history.append({"role": "assistant", "content": r2})
    r3, _ = await generate_response("What do you do?", history, language="en", state_manager=sm)
    print(f"[Turn 3 - Persona Question]: '{r3}'")
    assert sm.current_node_id == "discovery", f"FAIL Turn 3: Should stay on discovery, got node {sm.current_node_id}"
    assert any(w in r3.lower() for w in ["interview", "coach", "prepare", "help"]), f"FAIL Turn 3: Persona response weak: '{r3}'"

    # 5. User requests data analyst interview Q&A
    history.append({"role": "user", "content": "What do you do?"})
    history.append({"role": "assistant", "content": r3})
    r4, _ = await generate_response("I want to prepare for data analyst interviews. Can you give me some questions and answers?", history, language="en", state_manager=sm)
    print(f"[Turn 4 - Request Data Analyst Q&A]: '{r4}'")
    assert sm.current_node_id == "discovery", f"FAIL Turn 4: Should stay on discovery during Q&A request, got {sm.current_node_id}"
    assert len(r4) > 20, "FAIL Turn 4: Response should contain LLM generated interview Q&A content"

    # 6. User requests interactive mock interview
    history.append({"role": "user", "content": "I want to prepare for data analyst interviews. Can you give me some questions and answers?"})
    history.append({"role": "assistant", "content": r4})
    r5, _ = await generate_response("Please conduct a mock interview for a data analyst role.", history, language="en", state_manager=sm)
    print(f"[Turn 5 - Request Interactive Mock Interview]: '{r5}'")
    assert any(w in r5.lower() for w in ["question", "interview", "data", "analyst", "sql", "python", "tell", "walk"]), f"FAIL Turn 5: '{r5}'"

    # 7. Incomplete response
    history.append({"role": "user", "content": "Please conduct a mock interview for a data analyst role."})
    history.append({"role": "assistant", "content": r5})
    r6, _ = await generate_response("I want to...", history, language="en", state_manager=sm)
    print(f"[Turn 6 - Incomplete Utterance]: '{r6}'")
    assert "complete your thought" in r6.lower() or "goals" in r6.lower(), f"FAIL Turn 6: '{r6}'"

    # 8. User completes session and requests follow up
    history.append({"role": "user", "content": "I want to..."})
    history.append({"role": "assistant", "content": r6})
    r7, _ = await generate_response("Thanks, that is all. Please have your team follow up.", history, language="en", state_manager=sm)
    print(f"[Turn 7 - Confirm Follow up]: '{r7}'")
    assert sm.current_node_id in {"confirm_follow_up", "end_node"}, f"FAIL Turn 7: expected confirm_follow_up, got {sm.current_node_id}"

    # 9. Terminal end
    history.append({"role": "user", "content": "Thanks, that is all. Please have your team follow up."})
    history.append({"role": "assistant", "content": r7})
    r8, is_term = await generate_response("Yes, thank you.", history, language="en", state_manager=sm)
    print(f"[Turn 8 - Terminal End]: '{r8}' (terminal={is_term})")
    assert is_term == True, "FAIL Turn 8: session should terminate"

    print("\n✓ ALL RESTORED MOCK INTERVIEW COACH INTELLIGENCE & FLOW TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_llm_restoration())
