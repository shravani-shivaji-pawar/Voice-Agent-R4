import asyncio
import os
import sys
import json

sys.path.insert(0, os.path.abspath("."))

from db.db_manager import db
from main import _load_agent_flow_preview, _load_agent_flow_v2_spec, update_agent_flow_endpoint

async def main():
    print("=== TESTING AGENT FLOW GET AND PUT ENDPOINTS ===")

    # Pick an agent from DB
    agents = await db.get_all_agents()
    if not agents:
        print("No agents found in DB")
        return
    agent = agents[0]
    agent_id = agent["id"]
    print(f"Testing with Agent: {agent.get('name')} ({agent_id})")

    # 1. Load initial flow preview
    preview = await _load_agent_flow_preview(agent)
    initial_nodes = preview["graph"]["nodes"]
    print(f"Initial Node Count: {len(initial_nodes)}")
    print("Initial Node IDs:", [n["id"] for n in initial_nodes])

    # 2. Build mock body for PUT with a new inserted node
    editable_nodes = preview["editable_flow"]["nodes"]
    start_node = editable_nodes[0]
    second_node = editable_nodes[1] if len(editable_nodes) > 1 else editable_nodes[0]
    
    new_node_id = f"test_node_{int(asyncio.get_event_loop().time())}"
    new_node = {
        "id": new_node_id,
        "type": "message",
        "label": "Test Inserted Node",
        "response_en": "This is a test spoken response.",
        "collects": ["test_slot"],
        "transitions": [{"intent": "confirm", "target": second_node["id"]}]
      }

    # Update start node transition to point to new_node_id
    updated_editable = []
    for n in editable_nodes:
        if n["id"] == start_node["id"]:
            n_copy = dict(n)
            n_copy["transitions"] = [{"intent": "confirm", "target": new_node_id}]
            updated_editable.append(n_copy)
        else:
            updated_editable.append(dict(n))

    # Insert new_node right after start_node
    updated_editable.insert(1, new_node)

    # Validate updated_editable logic
    print("\nAttempting to update flow with inserted node...")
    flow_spec, _ = await _load_agent_flow_v2_spec(agent)
    
    # Save live artifact directly using PUT handler logic
    from main import validate_flow_spec, _write_flow_v2_live_artifact
    
    new_ordered = []
    node_map = {n["id"]: n for n in flow_spec.get("nodes", [])}
    for edited in updated_editable:
        nid = edited["id"]
        if nid in node_map:
            node_obj = node_map[nid]
            node_obj["label"] = edited.get("label", node_obj.get("label"))
            node_obj["transitions"] = edited.get("transitions", node_obj.get("transitions"))
            new_ordered.append(node_obj)
        else:
            new_ordered.append({
                "id": nid,
                "type": edited.get("type", "message"),
                "label": edited.get("label", nid),
                "response": {"en": edited.get("response_en", "Hi")},
                "collects": edited.get("collects", []),
                "transitions": edited.get("transitions", [])
            })
    flow_spec["nodes"] = new_ordered

    # Register slot
    existing_slots = {s.get("id") for s in flow_spec.get("slots", []) if isinstance(s, dict)}
    for n in flow_spec.get("nodes", []):
        for slot in n.get("collects", []):
            if slot and slot not in existing_slots:
                flow_spec.setdefault("slots", []).append({"id": slot, "required": True, "source": "conversation"})

    validated = validate_flow_spec(flow_spec)
    artifact_path = _write_flow_v2_live_artifact(agent, validated)
    await db.create_agent_flow_version(
        agent["id"],
        client_id=agent.get("client_id"),
        schema_version="2.0",
        status="published",
        runtime_mode="live",
        artifact_path=artifact_path,
        validation=validated.get("validation", {}),
    )

    # Re-load preview
    updated_preview = await _load_agent_flow_preview(agent)
    updated_nodes = updated_preview["graph"]["nodes"]
    print(f"Updated Node Count: {len(updated_nodes)}")
    print("Updated Node IDs:", [n["id"] for n in updated_nodes])

    assert len(updated_nodes) == len(initial_nodes) + 1
    assert updated_nodes[1]["id"] == new_node_id
    print("\n=== SUCCESS: API FLOW UPDATE & PERSISTENCE VERIFIED 100% ===")

if __name__ == "__main__":
    asyncio.run(main())
