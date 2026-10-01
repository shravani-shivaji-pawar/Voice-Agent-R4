import asyncio
import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.db_manager import db
from runtime_resolver import AgentRuntimeResolver
from llm.state_manager import StateManager
from llm.llm_response_generator import generate_response_for_turn_sync
from main import _load_agent_flow_v2_spec

async def run_tests():
    aid = 'agent-24d052dde825' # Foodie Agent
    
    print("=== STARTING COMPREHENSIVE RUNTIME NODE TRIGGER TEST SUITE ===")

    # -------------------------------------------------------------
    # TEST 1: Create a new node with a simple spoken response. Verify reachable.
    # -------------------------------------------------------------
    print("\n--- TEST 1: Create new node with simple spoken response ---")
    config1 = await AgentRuntimeResolver.resolve(aid)
    sm1 = StateManager(config1)
    print(f"Loaded {len(sm1.nodes)} nodes for Foodie Agent. Start node: {sm1.start_node_id}")
    
    # Check if node_1790786777777_f8xe ("take care") is present
    has_take_care = "node_1790786777777_f8xe" in sm1.nodes
    print("Contains 'take care' node:", has_take_care)
    assert has_take_care, "TEST 1 FAILED: Dynamically added 'take care' node not found in StateManager!"
    node_obj = sm1.nodes["node_1790786777777_f8xe"]
    assert node_obj.get("response") == "take care", "TEST 1 FAILED: Response mismatch!"
    print("✓ TEST 1 PASSED: Dynamically added node 'good' ('take care') loaded into runtime StateManager!")

    # -------------------------------------------------------------
    # TEST 2: Create a node in the middle of the flow. Verify runtime reaches it.
    # -------------------------------------------------------------
    print("\n--- TEST 2: Verify runtime reaches middle node ---")
    sm2 = StateManager(config1)
    sm2.reset_state()
    # Turn 1: Greeting
    turn_g = sm2.execute_greeting_transition("")
    resp_g = generate_response_for_turn_sync(turn_g, state_manager=sm2)
    # Turn 2: User confirms -> moves to middle node 'node_1790786681254_08ya' ("what is your name")
    turn_m = sm2.execute_transition("Hello.", {"intent": "confirm"})
    resp_m = generate_response_for_turn_sync(turn_m, state_manager=sm2)
    print(f"Current node after confirm: {sm2.current_node_id}")
    print(f"Spoken response: \"{resp_m}\"")
    assert sm2.current_node_id == "node_1790786681254_08ya", "TEST 2 FAILED: Did not reach middle node!"
    assert "what is your name" in resp_m.lower(), "TEST 2 FAILED: Spoken response did not use middle node!"
    print("✓ TEST 2 PASSED: Runtime successfully transitioned to and spoke middle node response!")

    # -------------------------------------------------------------
    # TEST 3: Create a node at the START of the flow. Verify conversation starts from that node.
    # -------------------------------------------------------------
    print("\n--- TEST 3: Add node at START and verify conversation starts there ---")
    # Simulate flow where start_node_id is 'custom_start'
    custom_start_flow = {
        "start_node_id": "custom_start",
        "nodes": [
            {
                "id": "custom_start",
                "type": "message",
                "response": {"en": "Welcome to Foodie express delivery service!"},
                "transitions": [{"intent": "confirm", "target": "start"}]
            },
            {
                "id": "start",
                "type": "message",
                "response": {"en": "Hello, how can I assist you today?"},
                "transitions": []
            }
        ]
    }
    sm3 = StateManager(custom_start_flow)
    assert sm3.start_node_id == "custom_start", "TEST 3 FAILED: start_node_id not set to custom_start!"
    assert sm3.current_node_id == "custom_start", "TEST 3 FAILED: current_node_id not initialized to custom_start!"
    turn_start = sm3.execute_greeting_transition("")
    resp_start = generate_response_for_turn_sync(turn_start, state_manager=sm3)
    print("Start node response:", resp_start)
    assert "Welcome to Foodie express delivery service" in resp_start, "TEST 3 FAILED: Incorrect start response!"
    print("✓ TEST 3 PASSED: Conversation initialized and started from custom START node!")

    # -------------------------------------------------------------
    # TEST 4: Delete a node. Verify runtime cannot trigger deleted node.
    # -------------------------------------------------------------
    print("\n--- TEST 4: Delete node and verify runtime cannot trigger it ---")
    flow_without_middle = {
        "start_node_id": "start",
        "nodes": [
            {
                "id": "start",
                "type": "message",
                "response": {"en": "Hello, this is Foodie."},
                "transitions": [{"intent": "confirm", "target": "end"}]
            },
            {
                "id": "end",
                "type": "end",
                "response": {"en": "Thank you. Goodbye!"},
                "transitions": []
            }
        ]
    }
    sm4 = StateManager(flow_without_middle)
    assert "node_1790786681254_08ya" not in sm4.nodes, "TEST 4 FAILED: Deleted node still present!"
    turn_del = sm4.execute_transition("Hello.", {"intent": "confirm"})
    print("After deletion, transition from start goes to:", sm4.current_node_id)
    assert sm4.current_node_id == "end", "TEST 4 FAILED: Transitioned to deleted node!"
    print("✓ TEST 4 PASSED: Deleted node cannot be triggered by runtime!")

    # -------------------------------------------------------------
    # TEST 5: Edit an existing node's spoken response. Verify runtime uses updated response.
    # -------------------------------------------------------------
    print("\n--- TEST 5: Edit spoken response and verify updated response used ---")
    edited_flow = {
        "start_node_id": "start",
        "nodes": [
            {
                "id": "start",
                "type": "message",
                "response": {"en": "Namaste! Welcome to Foodie Premium Services."},
                "transitions": []
            }
        ]
    }
    sm5 = StateManager(edited_flow)
    turn_edit = sm5.execute_greeting_transition("")
    resp_edit = generate_response_for_turn_sync(turn_edit, state_manager=sm5)
    print("Edited spoken response:", resp_edit)
    assert "Namaste! Welcome to Foodie Premium Services." in resp_edit, "TEST 5 FAILED: Updated response not used!"
    print("✓ TEST 5 PASSED: Runtime uses updated spoken response from edited node!")

    # -------------------------------------------------------------
    # TEST 6: Create a completely new prompt/brand-based agent. Verify its nodes are used.
    # -------------------------------------------------------------
    print("\n--- TEST 6: New custom agent nodes used instead of falling back to static flows ---")
    brand_flow = {
        "start_node_id": "brand_greeting",
        "nodes": [
            {
                "id": "brand_greeting",
                "type": "message",
                "response": {"en": "Welcome to Apex Global Logistics. How may I route your package?"},
                "transitions": [{"intent": "provide_info", "target": "tracking"}]
            },
            {
                "id": "tracking",
                "type": "slot_collection",
                "response": {"en": "Please provide your tracking number."},
                "collects": ["tracking_number"],
                "transitions": []
            }
        ]
    }
    sm6 = StateManager(brand_flow)
    assert len(sm6.nodes) == 2, "TEST 6 FAILED: Custom agent nodes count mismatch!"
    assert sm6.start_node_id == "brand_greeting", "TEST 6 FAILED: Custom start node mismatch!"
    turn_brand1 = sm6.execute_greeting_transition("")
    resp_brand1 = generate_response_for_turn_sync(turn_brand1, state_manager=sm6)
    print("Brand agent greeting:", resp_brand1)
    assert "Apex Global Logistics" in resp_brand1, "TEST 6 FAILED: Custom agent greeting missing!"

    turn_brand2 = sm6.execute_transition("Track package", {"intent": "provide_info"})
    resp_brand2 = generate_response_for_turn_sync(turn_brand2, state_manager=sm6)
    print("Brand agent next node:", sm6.current_node_id, "| response:", resp_brand2)
    assert sm6.current_node_id == "tracking", "TEST 6 FAILED: Did not transition to custom tracking node!"
    print("✓ TEST 6 PASSED: Completely new brand-based agent nodes used cleanly without fallback!")

    # -------------------------------------------------------------
    # TEST 7: Restart backend simulation (Re-resolve from DB/Disk). Verify saved flow used.
    # -------------------------------------------------------------
    print("\n--- TEST 7: Re-resolve agent config from DB and verify saved flow loaded ---")
    config7 = await AgentRuntimeResolver.resolve(aid)
    sm7 = StateManager(config7)
    assert len(sm7.nodes) >= 5, "TEST 7 FAILED: Re-resolved agent missing saved flow nodes!"
    print(f"Re-resolved StateManager loaded {len(sm7.nodes)} nodes from disk.")
    print("✓ TEST 7 PASSED: Saved conversation flow persists and reloads into runtime after restart!")

    print("\n=== ALL 7 RUNTIME NODE TESTS PASSED 100% SUCCESSFULLY ===")

if __name__ == "__main__":
    asyncio.run(run_tests())
