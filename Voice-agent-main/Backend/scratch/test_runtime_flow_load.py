import asyncio
import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.db_manager import db
from runtime_resolver import AgentRuntimeResolver
from llm.state_manager import StateManager
from main import _load_agent_flow_v2_spec

async def test():
    aid = 'agent-24d052dde825'
    agent = await db.get_agent(aid)
    flow, source = await _load_agent_flow_v2_spec(agent)
    print("Source:", source)
    print("Flow v2 node count:", len(flow.get("nodes", [])))
    for n in flow.get("nodes", []):
        print(f" Node: {n['id']} | type: {n.get('type')} | response: {n.get('response')} | transitions: {n.get('transitions')}")

if __name__ == "__main__":
    asyncio.run(test())
