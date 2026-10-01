import asyncio
import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.db_manager import db
from runtime_resolver import AgentRuntimeResolver
from llm.state_manager import StateManager
from llm.llm_response_generator import generate_response_for_turn_sync
from main import _load_agent_flow_v2_spec

def normalize_flow_spec_to_state_manager(flow_spec: dict) -> dict:
    """Normalizes FlowSpec v2 dictionary so StateManager and LLMResponseGenerator recognize all dynamic nodes, edges, and responses."""
    if not isinstance(flow_spec, dict):
        return {}

    # Extract nodes list from flow_spec or flow_spec["flow"] or flow_spec["conversationFlow"]
    raw_nodes = flow_spec.get("nodes")
    if not raw_nodes and isinstance(flow_spec.get("flow"), dict):
        raw_nodes = flow_spec["flow"].get("nodes")
    if not raw_nodes and isinstance(flow_spec.get("conversationFlow"), dict):
        raw_nodes = flow_spec["conversationFlow"].get("nodes")
    if not isinstance(raw_nodes, list):
        raw_nodes = []

    start_node_id = flow_spec.get("start_node_id") or (flow_spec.get("flow") or {}).get("start_node_id") or (raw_nodes[0].get("id") if raw_nodes else "")

    normalized_nodes = []
    for node in raw_nodes:
        if not isinstance(node, dict) or not node.get("id"):
            continue
        n_copy = dict(node)
        nid = n_copy["id"]

        # 1. Normalize response to string if it's localized dict {"en": "..."}
        resp = n_copy.get("response")
        if isinstance(resp, dict):
            resp_str = resp.get("en") or next((v for v in resp.values() if str(v).strip()), "")
            n_copy["response"] = resp_str
        elif not resp and n_copy.get("response_en"):
            n_copy["response"] = n_copy["response_en"]

        # 2. Normalize transitions to edges & intent_triggers
        transitions = n_copy.get("transitions") or []
        edges = list(n_copy.get("edges") or [])
        intent_triggers = list(n_copy.get("intent_triggers") or [])

        for t in transitions:
            if not isinstance(t, dict):
                continue
            intent = t.get("intent") or "confirm"
            target = t.get("target")
            if intent and intent not in intent_triggers:
                intent_triggers.append(intent)
            if target and not any(e.get("destination_node_id") == target for e in edges):
                edges.append({
                    "id": f"to_{target}",
                    "condition": intent,
                    "destination_node_id": target
                })

        n_copy["edges"] = edges
        n_copy["intent_triggers"] = intent_triggers
        normalized_nodes.append(n_copy)

    return {
        "start_node_id": start_node_id,
        "conversationFlow": {
            "start_node_id": start_node_id,
            "nodes": normalized_nodes
        },
        "nodes": normalized_nodes
    }

async def test():
    aid = 'agent-24d052dde825'
    agent = await db.get_agent(aid)
    flow_v2, source = await _load_agent_flow_v2_spec(agent)
    print("Loaded flow_v2 artifact:", source)

    normalized_schema = normalize_flow_spec_to_state_manager(flow_v2)
    sm = StateManager(normalized_schema)
    print(f"StateManager initialized with {len(sm.nodes)} dynamic nodes. Start node: {sm.start_node_id}")

    # Simulation:
    # 1. Greeting turn
    greeting_turn = sm.execute_greeting_transition("")
    resp_greeting = generate_response_for_turn_sync(greeting_turn, state_manager=sm)
    print("\n[TURN 1 - GREETING]")
    print("Current node:", sm.current_node_id)
    print("Spoken response:", resp_greeting)

    # 2. User says "Hello."
    turn2 = sm.execute_transition("Hello.", {"intent": "confirm"})
    resp2 = generate_response_for_turn_sync(turn2, state_manager=sm)
    print("\n[TURN 2 - USER: 'Hello.']")
    print("Current node:", sm.current_node_id)
    print("Spoken response:", resp2)

    # 3. User gives name "John"
    turn3 = sm.execute_transition("John", {"intent": "provide_info"})
    resp3 = generate_response_for_turn_sync(turn3, state_manager=sm)
    print("\n[TURN 3 - USER: 'John']")
    print("Current node:", sm.current_node_id)
    print("Spoken response:", resp3)

    # 4. Move to confirm_followup -> user says "Okay, thank you."
    sm.current_node_id = "confirm_followup"
    # rewire confirm_followup transition to node_1790786777777_f8xe ("take care")
    sm.nodes["confirm_followup"]["edges"] = [{"id": "to_take_care", "condition": "confirm", "destination_node_id": "node_1790786777777_f8xe"}]
    turn4 = sm.execute_transition("Okay, thank you.", {"intent": "confirm"})
    resp4 = generate_response_for_turn_sync(turn4, state_manager=sm)
    print("\n[TURN 4 - USER: 'Okay, thank you.']")
    print("Current node:", sm.current_node_id)
    print("Spoken response:", resp4)

if __name__ == "__main__":
    asyncio.run(test())
