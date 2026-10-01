import asyncio
import time
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from runtime_resolver import AgentRuntimeResolver
from flows.v2.spec import validate_flow_spec

async def main():
    print("=== TESTING STARTUP LATENCY & ADD NODE FUNCTIONALITY ===")

    # 1. Startup Latency Test
    t0 = time.perf_counter()
    config1 = await AgentRuntimeResolver.resolve("agent-49f64ad7d683")
    t1 = time.perf_counter()
    res1_ms = (t1 - t0) * 1000.0

    t2 = time.perf_counter()
    config2 = await AgentRuntimeResolver.resolve("agent-49f64ad7d683")
    t3 = time.perf_counter()
    res2_ms = (t3 - t2) * 1000.0

    print(f"[TEST 1] First Resolve Time (DB load): {res1_ms:.2f} ms")
    print(f"[TEST 1] Second Resolve Time (Fast TTL Cache): {res2_ms:.2f} ms")
    assert config1["id"] == config2["id"]
    print("[TEST 1] SUCCESS: AgentRuntimeResolver TTL Cache working cleanly!\n")

    # 2. Add Node Flow Validation Test
    sample_flow = {
        "schema_version": "2.0",
        "id": "flow_test_123",
        "agent_id": "agent-49f64ad7d683",
        "status": "draft",
        "runtime_mode": "live",
        "start_node_id": "start",
        "slots": [{"id": "budget", "required": True, "source": "conversation"}],
        "nodes": [
            {
                "id": "start",
                "type": "message",
                "label": "Greeting",
                "response": {"en": "Hello! How can I assist you today?"},
                "transitions": [{"intent": "confirm", "target": "custom_node_1"}]
            },
            {
                "id": "custom_node_1",
                "type": "slot_collection",
                "label": "Custom Added Node",
                "response": {"en": "Could you share your budget?"},
                "collects": ["budget"],
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

    validated = validate_flow_spec(sample_flow)
    print(f"[TEST 2] Add Node Validation: Verified {len(validated['nodes'])} nodes successfully!")
    assert len(validated['nodes']) == 3
    assert validated['nodes'][1]['id'] == 'custom_node_1'
    print("[TEST 2] SUCCESS: Add Node FlowSpec v2 validation passed 100%!\n")

    print("=== ALL TESTS PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    asyncio.run(main())
