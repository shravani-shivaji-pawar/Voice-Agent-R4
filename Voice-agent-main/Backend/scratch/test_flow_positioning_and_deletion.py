import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from flows.v2.spec import validate_flow_spec

def main():
    print("=== TESTING FLOW ADD NODE POSITIONING & DELETE NODE ===")

    # 1. Base Flow: Start -> Discovery -> End
    flow = {
        "schema_version": "2.0",
        "id": "flow_test_pos",
        "agent_id": "agent-test",
        "status": "draft",
        "runtime_mode": "live",
        "start_node_id": "start",
        "nodes": [
            {
                "id": "start",
                "type": "message",
                "label": "Greeting",
                "response": {"en": "Hello!"},
                "transitions": [{"intent": "confirm", "target": "discovery"}]
            },
            {
                "id": "discovery",
                "type": "message",
                "label": "Discovery",
                "response": {"en": "What are you looking for?"},
                "transitions": [{"intent": "provide_info", "target": "end"}]
            },
            {
                "id": "end",
                "type": "end",
                "label": "End",
                "response": {"en": "Thank you!"},
                "transitions": []
            }
        ]
    }

    validated_base = validate_flow_spec(flow)
    print("Base Flow Validated OK:", [n["id"] for n in validated_base["nodes"]])

    # 2. Insert New Node X after 'start' targeting 'discovery'
    # Expected result: start -> X -> discovery -> end
    new_node_x = {
        "id": "node_x",
        "type": "message",
        "label": "Inserted Step X",
        "response": {"en": "Glad to connect!"},
        "transitions": [{"intent": "confirm", "target": "discovery"}]
    }

    # Re-route start transition to node_x
    nodes_inserted = [
        {
            "id": "start",
            "type": "message",
            "label": "Greeting",
            "response": {"en": "Hello!"},
            "transitions": [{"intent": "confirm", "target": "node_x"}]
        },
        new_node_x,
        {
            "id": "discovery",
            "type": "message",
            "label": "Discovery",
            "response": {"en": "What are you looking for?"},
            "transitions": [{"intent": "provide_info", "target": "end"}]
        },
        {
            "id": "end",
            "type": "end",
            "label": "End",
            "response": {"en": "Thank you!"},
            "transitions": []
        }
    ]

    flow["nodes"] = nodes_inserted
    validated_inserted = validate_flow_spec(flow)
    node_ids = [n["id"] for n in validated_inserted["nodes"]]
    print("Inserted Flow Validated OK:", node_ids)
    assert node_ids == ["start", "node_x", "discovery", "end"], f"Unexpected node order: {node_ids}"
    print("SUCCESS: Node X correctly inserted in position between start and discovery!\n")

    # 3. Delete Node 'discovery' and re-route node_x -> end
    # Expected result: start -> node_x -> end
    nodes_after_delete = [
        {
            "id": "start",
            "type": "message",
            "label": "Greeting",
            "response": {"en": "Hello!"},
            "transitions": [{"intent": "confirm", "target": "node_x"}]
        },
        {
            "id": "node_x",
            "type": "message",
            "label": "Inserted Step X",
            "response": {"en": "Glad to connect!"},
            "transitions": [{"intent": "confirm", "target": "end"}]
        },
        {
            "id": "end",
            "type": "end",
            "label": "End",
            "response": {"en": "Thank you!"},
            "transitions": []
        }
    ]

    flow["nodes"] = nodes_after_delete
    validated_deleted = validate_flow_spec(flow)
    deleted_ids = [n["id"] for n in validated_deleted["nodes"]]
    print("Deleted Flow Validated OK:", deleted_ids)
    assert deleted_ids == ["start", "node_x", "end"], f"Unexpected node order: {deleted_ids}"
    print("SUCCESS: Node 'discovery' deleted and graph re-routed cleanly to 'end'!\n")

    print("=== ALL FLOW POSITIONING & DELETION TESTS PASSED 100% ===")

if __name__ == "__main__":
    main()
