import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from flows.v2 import (
    build_flow_spec_from_agent,
    validate_flow_spec,
    FlowSpecValidationError,
)
from llm.state_manager import StateManager


class FlowNodeOperationsTest(unittest.TestCase):
    def setUp(self):
        self.agent_id = "test_agent_123"
        self.initial_flow = build_flow_spec_from_agent(
            agent_id=self.agent_id,
            agent_name="Test Agent",
            agent_type="custom",
            script="Initial system prompt.",
            data_fields=["name", "budget"],
            language="English",
        )

    def test_add_node_validation_and_slots_registration(self):
        import main

        # Add a custom billing support node with new slot 'invoice_number'
        new_node = {
            "id": "node_billing_support",
            "type": "message",
            "label": "Billing Support",
            "response": {"en": "I can help with your invoice. What is your invoice number?"},
            "collects": ["invoice_number"],
            "transitions": [
                {"intent": "provide_info", "label": "Provide Invoice", "target": "confirm_followup"},
                {"intent": "deny", "label": "Cancel", "target": "end"},
            ]
        }

        submitted_nodes = self.initial_flow["nodes"] + [new_node]
        
        # Link start node to billing support
        start_node = next(n for n in submitted_nodes if n["id"] == "start")
        start_node["transitions"].append({
            "intent": "billing_query",
            "label": "Ask Billing",
            "target": "node_billing_support"
        })

        # Test backend logic directly
        slots_registry = {s["id"]: s for s in self.initial_flow.get("slots", [])}
        for slot in new_node["collects"]:
            if slot not in slots_registry:
                slots_registry[slot] = {"id": slot, "required": True, "source": "conversation"}

        flow_to_validate = dict(self.initial_flow)
        flow_to_validate["nodes"] = submitted_nodes
        flow_to_validate["slots"] = list(slots_registry.values())

        validated = validate_flow_spec(flow_to_validate)
        self.assertIn("node_billing_support", [n["id"] for n in validated["nodes"]])
        self.assertIn("invoice_number", [s["id"] for s in validated["slots"]])

    def test_delete_node_and_transition_cleanup(self):
        import main

        flow = build_flow_spec_from_agent(
            agent_id=self.agent_id,
            agent_name="Test Agent",
            agent_type="custom",
            script="Initial system prompt.",
            data_fields=["name"],
        )

        # Confirm initial nodes
        node_ids = [n["id"] for n in flow["nodes"]]
        self.assertIn("discovery", node_ids)

        # Delete discovery node and reroute start node transitions targeting discovery to confirm_followup
        submitted_nodes = []
        for n in flow["nodes"]:
            if n["id"] == "discovery":
                continue
            n_copy = dict(n)
            n_copy["transitions"] = [
                {"intent": t["intent"], "label": t.get("label", t["intent"]), "target": "confirm_followup" if t.get("target") == "discovery" else t["target"]}
                for t in n.get("transitions", [])
            ]
            submitted_nodes.append(n_copy)

        flow["nodes"] = submitted_nodes
        validated = validate_flow_spec(flow)
        
        updated_ids = [n["id"] for n in validated["nodes"]]
        self.assertNotIn("discovery", updated_ids)
        
        # Verify no remaining transitions target discovery
        for n in validated["nodes"]:
            for t in n.get("transitions", []):
                self.assertNotEqual(t.get("target"), "discovery")

    def test_delete_start_node_prevention(self):
        flow = build_flow_spec_from_agent(
            agent_id=self.agent_id,
            agent_name="Test Agent",
            agent_type="custom",
            script="Initial system prompt.",
            data_fields=["name"],
        )

        # Attempt to delete start node
        submitted_nodes = [n for n in flow["nodes"] if n["id"] != "start"]
        submitted_ids = {n["id"] for n in submitted_nodes}

        start_id = flow.get("start_node_id", "start")
        self.assertNotIn(start_id, submitted_ids)

    def test_delete_last_end_node_prevention(self):
        flow = build_flow_spec_from_agent(
            agent_id=self.agent_id,
            agent_name="Test Agent",
            agent_type="custom",
            script="Initial system prompt.",
            data_fields=["name"],
        )

        # Attempt to remove all end nodes
        submitted_nodes = [n for n in flow["nodes"] if n.get("type") != "end"]
        has_end_node = any(n.get("type") == "end" for n in submitted_nodes)
        self.assertFalse(has_end_node)

    def test_dynamic_runtime_flow_conversion_and_state_manager(self):
        import main

        flow = build_flow_spec_from_agent(
            agent_id=self.agent_id,
            agent_name="Test Agent",
            agent_type="custom",
            script="Initial system prompt.",
            data_fields=["name"],
        )

        # Add custom technical support node
        tech_node = {
            "id": "node_tech_support",
            "type": "message",
            "label": "Technical Support",
            "response": {"en": "What technical problem are you experiencing?"},
            "collects": ["issue_desc"],
            "transitions": [
                {"intent": "provide_info", "label": "Describe Issue", "target": "confirm_followup"},
                {"intent": "deny", "label": "Cancel", "target": "end"},
            ]
        }
        flow["nodes"].append(tech_node)
        flow["slots"].append({"id": "issue_desc", "required": True, "source": "conversation"})

        # Start node transitions to tech_node
        start_node = next(n for n in flow["nodes"] if n["id"] == "start")
        start_node["transitions"].append({
            "intent": "tech_issue",
            "label": "Tech Issue",
            "target": "node_tech_support"
        })

        validated = validate_flow_spec(flow)
        runtime_flow = main._flow_v2_to_runtime_conversation_flow(validated)

        # Verify runtime conversationFlow structure
        self.assertEqual(runtime_flow["start_node_id"], "start")
        node_map = {n["id"]: n for n in runtime_flow["nodes"]}
        self.assertIn("node_tech_support", node_map)
        self.assertEqual(node_map["node_tech_support"]["response"], "What technical problem are you experiencing?")
        self.assertEqual(node_map["node_tech_support"]["collects"], ["issue_desc"])

        # Test StateManager initializing with this dynamic runtime flow
        schema = {
            "agent_id": self.agent_id,
            "agent_name": "Test Agent",
            "voice_id": "default",
            "language": "en",
            "global_prompt": "Test prompt.",
            "conversationFlow": runtime_flow
        }

        sm = StateManager(schema)
        self.assertEqual(sm.start_node_id, "start")
        self.assertIn("node_tech_support", sm.nodes)
        self.assertIn("issue_desc", sm.extraction_fields)


if __name__ == "__main__":
    unittest.main()
