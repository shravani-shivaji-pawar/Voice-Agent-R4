"""
Test script for verifying added node triggering functionality in Voice Agent R4.
"""

import sys
import os
import json
import asyncio

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from db.db_manager import db
from llm.state_manager import StateManager
from runtime_resolver import AgentRuntimeResolver
from llm.llm import generate_response
from main import _publish_flow_v2_to_runtime, _agent_schema_path, _flow_v2_to_runtime_conversation_flow, validate_flow_spec

async def run_added_node_tests():
    agent_id = "real_estate"
    print(f"=== TESTING ADDED CONVERSATION NODE TRIGGERING FOR AGENT '{agent_id}' ===")
    
    agent = await db.get_agent(agent_id)
    assert agent, f"Agent '{agent_id}' not found in DB"
    
    schema_path = _agent_schema_path(agent_id, agent.get("schema_path"))
    assert os.path.exists(schema_path), f"Schema path {schema_path} does not exist"
    
    # Load current schema
    with open(schema_path, "r", encoding="utf-8") as f:
        initial_schema = json.load(f)
        
    flow = initial_schema.get("conversationFlow", {})
    initial_nodes = flow.get("nodes", [])
    initial_start_id = flow.get("start_node_id", "root_greeting")
    print(f"Initial flow start_node_id='{initial_start_id}', total_nodes={len(initial_nodes)}")
    
    # ----------------------------------------------------
    # TEST 1: ADD NODE AT THE START (Becoming initial node)
    # ----------------------------------------------------
    print("\n--- TEST 1: Adding node at the START of flow ---")
    start_test_node_id = f"node_welcome_banner_{uuid_hex()}"
    start_test_response = "Welcome to SunCity Luxury Estates! Special festival offer is active today."
    
    new_start_runtime_node = {
        "id": start_test_node_id,
        "name": "Special Festival Welcome Banner",
        "type": "conversation",
        "instruction": {
            "type": "prompt",
            "text": start_test_response
        },
        "response": start_test_response,
        "start_speaker": "agent",
        "intent_triggers": ["call_connected"],
        "edges": [
            {
                "id": f"edge_{start_test_node_id}_1_{initial_start_id}",
                "condition": "user responds",
                "transition_condition": {"type": "prompt", "prompt": "user responds"},
                "destination_node_id": initial_start_id
            }
        ]
    }
    
    # Update flow graph
    test_flow_1 = dict(flow)
    test_flow_1["start_node_id"] = start_test_node_id
    test_flow_1["nodes"] = [new_start_runtime_node] + initial_nodes
    
    updated_schema_1 = dict(initial_schema)
    updated_schema_1["conversationFlow"] = test_flow_1
    
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(updated_schema_1, f, indent=4)
        
    # Verify StateManager loads new start node and executes its greeting
    sm_1 = StateManager(schema_path)
    print(f"[StateManager 1] start_node_id='{sm_1.start_node_id}', current_node_id='{sm_1.current_node_id}'")
    assert sm_1.start_node_id == start_test_node_id, f"Expected start node '{start_test_node_id}', got '{sm_1.start_node_id}'"
    assert sm_1.current_node_id == start_test_node_id, f"Expected current node '{start_test_node_id}', got '{sm_1.current_node_id}'"
    
    greeting_turn = sm_1.execute_greeting_transition()
    print(f"[Greeting Turn] node_id='{greeting_turn.node_id}', response='{greeting_turn.node.get('response')}'")
    assert greeting_turn.node_id == start_test_node_id, f"Expected greeting turn for '{start_test_node_id}', got '{greeting_turn.node_id}'"
    assert greeting_turn.node.get("response") == start_test_response
    print("PASS: Test 1 (Start Node Insertion & Execution) Passed!")
    
    # ----------------------------------------------------
    # TEST 2: ADD NODE BETWEEN TWO NODES & TRANSITION
    # ----------------------------------------------------
    print("\n--- TEST 2: Adding node BETWEEN two nodes & transition execution ---")
    between_test_node_id = f"node_vip_consultation_{uuid_hex()}"
    between_test_response = "Great! Would you like to consult with our VIP Luxury Project Specialist or standard advisor?"
    
    # Insert between start_test_node_id and initial_start_id
    new_between_node = {
        "id": between_test_node_id,
        "name": "VIP Consultation Selection",
        "type": "conversation",
        "instruction": {
            "type": "prompt",
            "text": between_test_response
        },
        "response": between_test_response,
        "intent_triggers": ["confirm", "user responds", "provide_info"],
        "edges": [
            {
                "id": f"edge_{between_test_node_id}_1_{initial_start_id}",
                "condition": "user responds",
                "transition_condition": {"type": "prompt", "prompt": "user responds"},
                "destination_node_id": initial_start_id
            }
        ]
    }
    
    # Update new_start_runtime_node edge to point to between_test_node_id instead
    new_start_runtime_node["edges"] = [
        {
            "id": f"edge_{start_test_node_id}_1_{between_test_node_id}",
            "condition": "user responds",
            "transition_condition": {"type": "prompt", "prompt": "user responds"},
            "destination_node_id": between_test_node_id
        }
    ]
    
    test_flow_2 = dict(test_flow_1)
    test_flow_2["nodes"] = [new_start_runtime_node, new_between_node] + initial_nodes
    
    updated_schema_2 = dict(initial_schema)
    updated_schema_2["conversationFlow"] = test_flow_2
    
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(updated_schema_2, f, indent=4)
        
    sm_2 = StateManager(schema_path)
    print(f"[StateManager 2] start_node_id='{sm_2.start_node_id}', current_node_id='{sm_2.current_node_id}'")
    
    # Execute user turn from start node -> should transition to between_test_node_id
    turn_2 = sm_2.execute_transition("Yes I am interested", {"intent": "confirm", "entities": {}})
    print(f"[Turn 1 Execution] current_node_id='{sm_2.current_node_id}', response='{turn_2.node.get('response')}'")
    assert sm_2.current_node_id == between_test_node_id, f"Expected transition to '{between_test_node_id}', got '{sm_2.current_node_id}'"
    assert turn_2.node.get("response") == between_test_response
    print("PASS: Test 2 (Between Node Transition & Spoken Response) Passed!")
    
    # ----------------------------------------------------
    # TEST 3: RESTORE INITIAL SCHEMA
    # ----------------------------------------------------
    print("\n--- TEST 3: Restoring initial schema & verifying clean rollback ---")
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(initial_schema, f, indent=4)
        
    sm_3 = StateManager(schema_path)
    assert sm_3.start_node_id == initial_start_id
    print("PASS: Test 3 (Schema Rollback & Verification) Passed!")
    
    print("\n==========================================")
    print("ALL 3 ADDED-NODE FUNCTIONALITY TESTS PASSED SUCCESSFULLY!")
    print("==========================================")

def uuid_hex():
    import uuid
    return uuid.uuid4().hex[:6]

if __name__ == "__main__":
    asyncio.run(run_added_node_tests())
