import asyncio
import logging
import os
import sys

# Add Backend to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from flows.runtime import RealEstateLLMProcessor, VoiceTurnState
from llm.llm import generate_response
from llm.state_manager import StateManager
from runtime_resolver import AgentRuntimeResolver

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_isolation")

async def run_tests():
    print("\n=======================================================")
    print("STARTING COMPLETE MULTI-AGENT NODE & PROMPT ISOLATION TESTS")
    print("=======================================================\n")

    # ─────────────────────────────────────────────────────────────────
    # Test A: Mock Interview Coach
    # ─────────────────────────────────────────────────────────────────
    print("--- Test A: Mock Interview Coach Agent ---")
    mock_config = {
        "id": "mock_interview_coach",
        "agent_id": "mock_interview_coach",
        "name": "Mock Interview Coach",
        "global_prompt": "You are Mock Interview Coach, an expert technical interview coach. You help candidates practice technical interviews, answer questions, provide instant feedback, and boost candidate confidence for job roles.",
        "greeting_response": "Hello, this is Mock Interview Coach. Am I speaking with Prashant?",
        "conversationFlow": {
            "start_node_id": "greeting",
            "nodes": [
                {
                    "id": "greeting",
                    "name": "Greeting",
                    "response": "Hello, this is Mock Interview Coach. Am I speaking with {{name}}?",
                    "edges": [{"condition": "Confirm", "destination_node_id": "discovery"}]
                },
                {
                    "id": "discovery",
                    "name": "Discovery",
                    "response": "What specific role or industry are you interviewing for today?",
                    "edges": []
                }
            ]
        }
    }
    
    proc_mock = RealEstateLLMProcessor(turn_state=VoiceTurnState(), agent_id="mock_interview_coach", agent_config=mock_config)
    proc_mock.state_manager.conversation_data["name"] = "Prashant"
    
    resp_mock, _ = await generate_response(
        user_text="What do you do?",
        conversation_history=[],
        language="en",
        state_manager=proc_mock.state_manager,
    )
    print(f"Mock Agent Response: '{resp_mock}'")
    assert "Mock Interview Coach" in resp_mock or "interview" in resp_mock.lower() or "prepare" in resp_mock.lower(), f"Expected interview coach persona, got: {resp_mock}"
    assert "real estate" not in resp_mock.lower(), f"Prompt leakage in Mock Agent! Got: {resp_mock}"
    print("[OK] PASS: Mock Interview Coach executes its own persona and nodes.\n")

    # ─────────────────────────────────────────────────────────────────
    # Test B: Real Estate Advisor
    # ─────────────────────────────────────────────────────────────────
    print("--- Test B: SunCity Real Estate Advisor ---")
    suncity_config = {
        "id": "suncity_real_estate",
        "agent_id": "suncity_real_estate",
        "name": "SunCity Real Estate Advisor - Priya",
        "global_prompt": "You are Priya, a senior property consultant at SunCity Real Estate. Assist clients with luxury apartments, property inquiries, pricing, locations, and booking site visits.",
        "greeting_response": "Hello, this is SunCity Real Estate Advisor - Priya from the Real Estate team. Am I speaking with Prashant?",
        "conversationFlow": {
            "start_node_id": "start",
            "nodes": [
                {
                    "id": "start",
                    "name": "Greeting",
                    "response": "Hello, this is SunCity Real Estate Advisor - Priya. Am I speaking with {{name}}?",
                    "edges": [{"condition": "Confirm", "destination_node_id": "discovery"}]
                },
                {
                    "id": "discovery",
                    "name": "Discovery",
                    "response": "Could you share a little about what property type or budget you are looking for?",
                    "edges": []
                }
            ]
        }
    }

    proc_suncity = RealEstateLLMProcessor(turn_state=VoiceTurnState(), agent_id="suncity_real_estate", agent_config=suncity_config)
    proc_suncity.state_manager.conversation_data["name"] = "Prashant"

    resp_re, _ = await generate_response(
        user_text="What do you do?",
        conversation_history=[],
        language="en",
        state_manager=proc_suncity.state_manager,
    )
    print(f"SunCity Agent Response: '{resp_re}'")
    assert "Mock Interview Coach" not in resp_re, f"LEAKAGE DETECTED! SunCity Agent spoke like Mock Interview Coach: {resp_re}"
    assert "interview" not in resp_re.lower(), f"LEAKAGE DETECTED! SunCity Agent mentioned interviews: {resp_re}"
    assert any(k in resp_re.lower() for k in ["priya", "suncity", "real estate", "property", "apartment", "assist"]), f"Expected SunCity Real Estate persona, got: {resp_re}"
    print("[OK] PASS: SunCity Real Estate Advisor responded strictly within its own persona.\n")

    # ─────────────────────────────────────────────────────────────────
    # Test C: Foodie Agent
    # ─────────────────────────────────────────────────────────────────
    print("--- Test C: Foodie Agent ---")
    foodie_config = {
        "id": "foodie_agent",
        "agent_id": "foodie_agent",
        "name": "Foodie Gourmet Advisor",
        "global_prompt": "You are Foodie Gourmet Advisor, an expert culinary concierge. You help users discover top restaurants, curated recipes, dining recommendations, and food pairings.",
        "greeting_response": "Hello! I am Foodie Gourmet Advisor. Looking for restaurant recommendations or recipe ideas today?",
        "conversationFlow": {
            "start_node_id": "greeting",
            "nodes": [
                {
                    "id": "greeting",
                    "name": "Greeting",
                    "response": "Hello! I am Foodie Gourmet Advisor. Looking for restaurant recommendations or recipe ideas today?",
                    "edges": [{"condition": "Confirm", "destination_node_id": "cuisine"}]
                },
                {
                    "id": "cuisine",
                    "name": "Cuisine",
                    "response": "What type of cuisine or dish are you craving today?",
                    "edges": []
                }
            ]
        }
    }

    proc_foodie = RealEstateLLMProcessor(turn_state=VoiceTurnState(), agent_id="foodie_agent", agent_config=foodie_config)
    proc_foodie.state_manager.conversation_data["name"] = "Prashant"

    resp_food, _ = await generate_response(
        user_text="What do you do?",
        conversation_history=[],
        language="en",
        state_manager=proc_foodie.state_manager,
    )
    print(f"Foodie Agent Response: '{resp_food}'")
    assert "Mock Interview Coach" not in resp_food, f"LEAKAGE DETECTED! Foodie Agent spoke like Mock Interview Coach: {resp_food}"
    assert "interview" not in resp_food.lower(), f"LEAKAGE DETECTED! Foodie Agent mentioned interviews: {resp_food}"
    assert any(k in resp_food.lower() for k in ["food", "culinary", "restaurant", "recipe", "dining", "concierge", "foodie"]), f"Expected Foodie persona, got: {resp_food}"
    print("[OK] PASS: Foodie Agent responded strictly within its own culinary persona.\n")

    # ─────────────────────────────────────────────────────────────────
    # Test D: Dynamic Node Addition, Editing, and Deletion
    # ─────────────────────────────────────────────────────────────────
    print("--- Test D: Dynamic Node Addition, Editing, and Deletion ---")
    
    # D1. Initial flow with 2 nodes
    dynamic_flow_1 = {
        "start_node_id": "step1",
        "global_prompt": "You are Fitness Assistant. Guide users with workout routines.",
        "nodes": [
            {"id": "step1", "name": "Step 1", "response": "Welcome to Fitness Assistant! What is your workout goal?"}
        ]
    }
    sm1 = StateManager(dynamic_flow_1)
    assert sm1.start_node_id == "step1"
    assert len(sm1.nodes) == 1
    print("  D1. Loaded initial flow with 1 node: PASS")

    # D2. User ADDS node 'step2'
    dynamic_flow_2 = {
        "start_node_id": "step1",
        "global_prompt": "You are Fitness Assistant. Guide users with workout routines.",
        "nodes": [
            {"id": "step1", "name": "Step 1", "response": "Welcome to Fitness Assistant! What is your workout goal?", "edges": [{"condition": "Continue", "destination_node_id": "step2"}]},
            {"id": "step2", "name": "Step 2", "response": "Got it! How many days a week can you train?"}
        ]
    }
    sm2 = StateManager(dynamic_flow_2)
    assert len(sm2.nodes) == 2
    assert "step2" in sm2.nodes
    print("  D2. Added node 'step2': PASS")

    # D3. User EDITS 'step2' response
    dynamic_flow_3 = {
        "start_node_id": "step1",
        "global_prompt": "You are Fitness Assistant. Guide users with workout routines.",
        "nodes": [
            {"id": "step1", "name": "Step 1", "response": "Welcome to Fitness Assistant! What is your workout goal?", "edges": [{"condition": "Continue", "destination_node_id": "step2"}]},
            {"id": "step2", "name": "Step 2", "response": "Awesome! What is your preferred training schedule per week?"}
        ]
    }
    sm3 = StateManager(dynamic_flow_3)
    assert sm3.nodes["step2"]["response"] == "Awesome! What is your preferred training schedule per week?"
    print("  D3. Edited node 'step2' response: PASS")

    # D4. User DELETES 'step2'
    dynamic_flow_4 = {
        "start_node_id": "step1",
        "global_prompt": "You are Fitness Assistant. Guide users with workout routines.",
        "nodes": [
            {"id": "step1", "name": "Step 1", "response": "Welcome to Fitness Assistant! What is your workout goal?", "edges": []}
        ]
    }
    sm4 = StateManager(dynamic_flow_4)
    assert len(sm4.nodes) == 1
    assert "step2" not in sm4.nodes
    print("  D4. Deleted node 'step2': PASS")
    print("[OK] PASS: Dynamic Node Addition, Editing, and Deletion verified.\n")

    # ─────────────────────────────────────────────────────────────────
    # Test E: Independent Agent Node Flows
    # ─────────────────────────────────────────────────────────────────
    print("--- Test E: Independent Node Flows for Distinct Agents ---")
    flow_agent_a = {
        "start_node_id": "node_a1",
        "global_prompt": "You are Agent Alpha.",
        "nodes": [
            {"id": "node_a1", "name": "Alpha Start", "response": "Alpha greeting", "edges": [{"condition": "Continue", "destination_node_id": "node_a2"}]},
            {"id": "node_a2", "name": "Alpha Step 2", "response": "Alpha details", "edges": []}
        ]
    }
    flow_agent_b = {
        "start_node_id": "node_b1",
        "global_prompt": "You are Agent Beta.",
        "nodes": [
            {"id": "node_b1", "name": "Beta Start", "response": "Beta greeting", "edges": [{"condition": "Continue", "destination_node_id": "node_b2"}]},
            {"id": "node_b2", "name": "Beta Step 2", "response": "Beta details", "edges": []}
        ]
    }

    sm_a = StateManager(flow_agent_a)
    sm_b = StateManager(flow_agent_b)

    assert set(sm_a.nodes.keys()) == {"node_a1", "node_a2"}
    assert set(sm_b.nodes.keys()) == {"node_b1", "node_b2"}
    assert "node_b1" not in sm_a.nodes and "node_a1" not in sm_b.nodes
    print("[OK] PASS: Independent flows strictly isolated per agent.\n")

    # ─────────────────────────────────────────────────────────────────
    # Test F: Sequential Agent Switching
    # ─────────────────────────────────────────────────────────────────
    print("--- Test F: Sequential Agent Switching ---")
    sequence = [
        ("Mock Interview Coach", proc_mock, "What interview questions should I prepare for data analyst?"),
        ("SunCity Real Estate", proc_suncity, "I am looking for a 3 BHK luxury apartment in Pune."),
        ("Foodie Agent", proc_foodie, "Can you recommend a great Italian restaurant for dinner?"),
        ("SunCity Real Estate", proc_suncity, "What is the price range of SunCity apartments?"),
        ("Mock Interview Coach", proc_mock, "Can you conduct a practice mock interview with me?"),
    ]

    for agent_label, proc, query in sequence:
        reply, _ = await generate_response(
            user_text=query,
            conversation_history=[],
            language="en",
            state_manager=proc.state_manager,
        )
        print(f"  [{agent_label}] Query: '{query}' -> Reply: '{reply}'")
        if agent_label == "Mock Interview Coach":
            assert "real estate" not in reply.lower() and "restaurant" not in reply.lower(), f"Leakage in {agent_label}: {reply}"
        elif agent_label == "SunCity Real Estate":
            assert "Mock Interview Coach" not in reply and "interview" not in reply.lower(), f"Leakage in {agent_label}: {reply}"
        elif agent_label == "Foodie Agent":
            assert "Mock Interview Coach" not in reply and "interview" not in reply.lower(), f"Leakage in {agent_label}: {reply}"

    print("\n[OK] PASS: Sequential Agent Switching completed with zero prompt/node leakage!\n")
    print("=======================================================")
    print("ALL MULTI-AGENT ISOLATION & NODE FLOW TESTS PASSED!")
    print("=======================================================\n")

if __name__ == "__main__":
    asyncio.run(run_tests())
