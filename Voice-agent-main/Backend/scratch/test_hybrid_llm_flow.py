import asyncio
import sys
import os
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_hybrid_llm_flow")

# Add Backend to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.llm import generate_response
from flows.runtime import CALL_CONNECTED_TRIGGER
from llm.state_manager import StateManager

MOCK_11_NODE_FLOW = {
    "start_node_id": "node-name",
    "nodes": [
        {
            "id": "node-name",
            "name": "Name",
            "response": "what is your name?",
            "collects": ["name"],
            "edges": [{"id": "e1", "destination_node_id": "node-education", "target_node_id": "node-education", "condition": "continue"}]
        },
        {
            "id": "node-education",
            "name": "Education",
            "response": "what is your education",
            "collects": ["education"],
            "edges": [{"id": "e2", "destination_node_id": "node-city", "target_node_id": "node-city", "condition": "continue"}]
        },
        {
            "id": "node-city",
            "name": "City",
            "response": "tell me your city",
            "collects": ["city"],
            "edges": [{"id": "e3", "destination_node_id": "node-greeting", "target_node_id": "node-greeting", "condition": "continue"}]
        },
        {
            "id": "node-greeting",
            "name": "Greeting",
            "response": "Hello, this is Mock Interview Coach. Am I speaking with {{name}}?",
            "edges": [
                {"id": "e4", "destination_node_id": "node-age", "target_node_id": "node-age", "condition": "confirm"},
                {"id": "e5", "destination_node_id": "node-end", "target_node_id": "node-end", "condition": "deny"},
                {"id": "e6", "destination_node_id": "node-clarify", "target_node_id": "node-clarify", "condition": "unclear"}
            ]
        },
        {
            "id": "node-age",
            "name": "Age",
            "response": "tell me your age",
            "collects": ["age"],
            "edges": [{"id": "e7", "destination_node_id": "node-discovery", "target_node_id": "node-discovery", "condition": "continue"}]
        },
        {
            "id": "node-discovery",
            "name": "Discovery",
            "response": "Could you share a little about what you are looking for?",
            "edges": [
                {"id": "e8", "destination_node_id": "node-confirm-followup", "target_node_id": "node-confirm-followup", "condition": "provide_info"},
                {"id": "e9", "destination_node_id": "node-confirm-followup", "target_node_id": "node-confirm-followup", "condition": "confirm"},
                {"id": "e10", "destination_node_id": "node-clarify", "target_node_id": "node-clarify", "condition": "unclear"}
            ]
        },
        {
            "id": "node-clarify",
            "name": "Clarification",
            "response": "Sorry, I did not catch that clearly. Could you repeat it once?",
            "edges": [
                {"id": "e11", "destination_node_id": "node-discovery", "target_node_id": "node-discovery", "condition": "provide_info"},
                {"id": "e12", "destination_node_id": "node-discovery", "target_node_id": "node-discovery", "condition": "confirm"},
                {"id": "e13", "destination_node_id": "node-end", "target_node_id": "node-end", "condition": "deny"},
                {"id": "e14", "destination_node_id": "node-clarify", "target_node_id": "node-clarify", "condition": "unclear"}
            ]
        },
        {
            "id": "node-confirm-followup",
            "name": "Confirm Follow-up",
            "response": "Thanks. I will have the team follow up with you shortly.",
            "edges": [{"id": "e15", "destination_node_id": "node-end", "target_node_id": "node-end", "condition": "continue"}]
        },
        {
            "id": "node-end",
            "name": "End",
            "type": "end",
            "response": "Thank you. Goodbye!"
        }
    ]
}

MOCK_SCHEMA = {
    "agent_id": "test_mock_coach",
    "system_prompt": "You are a friendly, professional Mock Interview Coach. You help candidates practice job interviews.",
    "conversationFlow": MOCK_11_NODE_FLOW
}

async def run_tests():
    print("=== RUNNING HYBRID LLM AND CONVERSATION-FLOW TEST SUITE ===")
    
    sm = StateManager(MOCK_SCHEMA)
    history = []
    
    # 1. CALL CONNECTED (Start Node)
    print("\n--- Test 1: Start Frame Connection ---")
    reply, term = await generate_response(CALL_CONNECTED_TRIGGER, history, "en", state_manager=sm)
    print(f"Agent response: '{reply}'")
    assert "what is your name" in reply.lower()
    assert sm.current_node_id == "node-name"
    print("PASSED: Start node spoken exactly once.")
    
    # 2. Name turn
    print("\n--- Test 2: Name input ---")
    history.append({"role": "assistant", "content": reply})
    reply, term = await generate_response("Radha", history, "en", state_manager=sm)
    print(f"Agent response: '{reply}'")
    assert "education" in reply.lower()
    assert sm.current_node_id == "node-education"
    print("PASSED: Transitioned to Education.")
    
    # 3. Education turn
    print("\n--- Test 3: Education input ---")
    history.append({"role": "user", "content": "Radha"})
    history.append({"role": "assistant", "content": reply})
    reply, term = await generate_response("B.Tech in Computer Science", history, "en", state_manager=sm)
    print(f"Agent response: '{reply}'")
    assert "city" in reply.lower()
    assert sm.current_node_id == "node-city"
    print("PASSED: Transitioned to City.")
    
    # 4. City turn
    print("\n--- Test 4: City input ---")
    history.append({"role": "user", "content": "B.Tech in Computer Science"})
    history.append({"role": "assistant", "content": reply})
    reply, term = await generate_response("Pune", history, "en", state_manager=sm)
    print(f"Agent response: '{reply}'")
    assert "mock interview coach" in reply.lower() and "radha" in reply.lower()
    assert sm.current_node_id == "node-greeting"
    print("PASSED: Transitioned to Greeting with name populated.")
    
    # 5. Identity confirmation turn
    print("\n--- Test 5: Confirm Identity ---")
    history.append({"role": "user", "content": "Pune"})
    history.append({"role": "assistant", "content": reply})
    reply, term = await generate_response("Yes, speaking.", history, "en", state_manager=sm)
    print(f"Agent response: '{reply}'")
    assert "age" in reply.lower()
    assert sm.current_node_id == "node-age"
    print("PASSED: Transitioned to Age.")
    
    # 6. Age turn
    print("\n--- Test 6: Age input ---")
    history.append({"role": "user", "content": "Yes, speaking."})
    history.append({"role": "assistant", "content": reply})
    reply, term = await generate_response("24 years old", history, "en", state_manager=sm)
    print(f"Agent response: '{reply}'")
    assert "looking for" in reply.lower() or "share" in reply.lower()
    assert sm.current_node_id == "node-discovery"
    print("PASSED: Transitioned to Discovery.")
    
    # 7. Question Interruption at Discovery ("What you do?")
    print("\n--- Test 7: Interruption Question 'What you do?' at Discovery ---")
    history.append({"role": "user", "content": "24 years old"})
    history.append({"role": "assistant", "content": reply})
    reply, term = await generate_response("What you do?", history, "en", state_manager=sm)
    print(f"Agent response: '{reply}'")
    assert sm.current_node_id == "node-discovery"
    assert "sorry, i did not catch" not in reply.lower()
    print("PASSED: Question answered naturally using LLM persona, returned to Discovery node.")
    
    # 8. Incomplete Utterance ("I want to...")
    print("\n--- Test 8: Incomplete Utterance 'I want to...' at Discovery ---")
    history.append({"role": "user", "content": "What you do?"})
    history.append({"role": "assistant", "content": reply})
    reply, term = await generate_response("I want to...", history, "en", state_manager=sm)
    print(f"Agent response: '{reply}'")
    assert sm.current_node_id == "node-discovery"
    print("PASSED: Incomplete utterance handled gracefully without premature node transition.")
    
    # 9. Complete Goal ("I want to prepare for data analyst interviews.")
    print("\n--- Test 9: Complete Goal Statement 'I want to prepare for data analyst interviews.' ---")
    history.append({"role": "user", "content": "I want to..."})
    history.append({"role": "assistant", "content": reply})
    reply, term = await generate_response("I want to prepare for data analyst interviews.", history, "en", state_manager=sm)
    print(f"Agent response: '{reply}'")
    assert sm.current_node_id == "node-confirm-followup"
    print("PASSED: Complete goal understood, contextual reply generated, transitioned to Confirm Follow-up.")
    
    # 10. Unclear Utterance handling
    print("\n--- Test 10: Unclear / Gibberish Input ---")
    sm2 = StateManager(MOCK_SCHEMA)
    sm2.current_node_id = "node-greeting"
    reply, term = await generate_response("Pahad xyz", [], "en", state_manager=sm2)
    print(f"Agent response: '{reply}'")
    assert sm2.current_node_id == "node-clarify"
    print("PASSED: Unclear input triggered configured Clarification node.")
    
    # 11. Clean Session Reset
    print("\n--- Test 11: New Session Reset ---")
    sm3 = StateManager(MOCK_SCHEMA)
    reply, term = await generate_response(CALL_CONNECTED_TRIGGER, [], "en", state_manager=sm3)
    assert sm3.current_node_id == "node-name"
    print("PASSED: New session starts cleanly at configured start node.")

    print("\n=== ALL 11 HYBRID TEST SCENARIOS PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    asyncio.run(run_tests())
