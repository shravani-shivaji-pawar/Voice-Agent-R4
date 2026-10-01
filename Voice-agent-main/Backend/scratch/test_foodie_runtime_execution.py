import asyncio
import logging
import json
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from runtime_resolver import AgentRuntimeResolver
from llm.state_manager import StateManager
from llm.llm import generate_response

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("test_foodie_execution")

async def test_foodie_flow():
    agent_id = "agent-24d052dde825"
    logger.info("Resolving agent config for agent_id=%s...", agent_id)
    agent_config = await AgentRuntimeResolver.resolve(agent_id)
    
    flow_data = (agent_config.get("conversationFlow") or agent_config.get("flow_v2") or agent_config.get("flow") or {}) if isinstance(agent_config, dict) else {}
    if flow_data and isinstance(flow_data, dict) and flow_data.get("nodes"):
        schema_to_use = agent_config
    else:
        schema_to_use = agent_config
        
    state_mgr = StateManager(schema_to_use)
    state_mgr.reset_state()
    state_mgr.conversation_data["name"] = "Prashant"
    
    print("\n" + "="*80)
    print(f"INITIALIZED STATE MANAGER FOR FOODIE AGENT (Loaded {len(state_mgr.nodes)} nodes)")
    print(f"Start Node ID: '{state_mgr.start_node_id}' ({state_mgr.nodes.get(state_mgr.start_node_id, {}).get('name') or state_mgr.nodes.get(state_mgr.start_node_id, {}).get('label')})")
    print("="*80 + "\n")
    
    turns = [
        "Yes, speaking!",                             # Turn 1: start -> ask_name
        "My name is Prashant",                        # Turn 2: ask_name -> ask_phone
        "My phone number is 9876543210",              # Turn 3: ask_phone -> ask_city
        "I am from Mumbai",                           # Turn 4: ask_city -> discovery
        "I want food delivery options for dinner",   # Turn 5: discovery -> confirm_followup
        "Yes, please follow up",                      # Turn 6: confirm_followup -> end
    ]
    
    history = []
    
    for i, user_text in enumerate(turns, 1):
        print(f"\n--- TURN {i}: User says: \"{user_text}\" ---")
        reply, is_terminal = await generate_response(
            user_text=user_text,
            conversation_history=history,
            language="en",
            state_manager=state_mgr
        )
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply})
        
        current_node_obj = state_mgr.nodes.get(state_mgr.current_node_id, {})
        current_node_label = current_node_obj.get("name") or current_node_obj.get("label") or state_mgr.current_node_id
        
        print(f"Agent Spoken Reply : \"{reply}\"")
        print(f"Current Active Node: {state_mgr.current_node_id} ({current_node_label})")
        print(f"Is Terminal        : {is_terminal}")
        print("-" * 50)
        
        if is_terminal:
            print("\nSUCCESS: Conversation flow reached terminal END node successfully!")
            break


if __name__ == "__main__":
    asyncio.run(test_foodie_flow())
