import asyncio
import os
import sys

# Ensure backend folder is in python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from db.db_manager import db
from runtime_resolver import AgentRuntimeResolver

async def run_test():
    print("--- Starting Runtime Generate Summary Connection & Isolation Test ---")
    
    agent_a_id = "test-agent-a-101"
    agent_b_id = "test-agent-b-102"
    agent_c_id = "test-agent-c-103"
    
    # 1. Create 3 agents
    await db.save_agent({
        "id": agent_a_id,
        "name": "Acme Sales Agent",
        "agent_type": "custom",
        "script": "You are Acme Sales Representative.",
        "language": "en"
    })
    await db.save_agent({
        "id": agent_b_id,
        "name": "Beta Corp Support",
        "agent_type": "custom",
        "script": "You are Beta Corp Support Agent.",
        "language": "en"
    })
    await db.save_agent({
        "id": agent_c_id,
        "name": "Clean Agent Without Website",
        "agent_type": "custom",
        "script": "You are Clean Agent with no website knowledge.",
        "language": "en"
    })
    
    # 2. Simulate Scrape Job & Script Draft for Agent A
    job_a = await db.create_scrape_job(
        client_id=None,
        agent_id=agent_a_id,
        url="https://acme-inc.example.com",
        domain="acme-inc.example.com"
    )
    draft_a = await db.create_generated_script_draft(
        job_id=job_a["id"],
        agent_id=agent_a_id,
        client_id=None,
        status="draft_ready",
        knowledge_json={
            "source_url": "https://acme-inc.example.com",
            "company": {
                "name": "Acme Anvils Inc",
                "summary": "Acme manufacture heavy duty industrial anvils and rockets."
            },
            "products_or_services": [
                {"name": "Ultra Anvil 3000", "description": "100kg cast iron anvil"}
            ],
            "faqs": [
                {"question": "What is the warranty?", "answer": "Lifetime warranty on all anvils."}
            ]
        },
        draft_json={
            "global_prompt": "Sell Acme anvils"
        }
    )
    # Apply draft A
    await db.mark_generated_script_draft_reviewed(draft_a["id"], status="published_live")
    
    # 3. Simulate Scrape Job & Script Draft for Agent B
    job_b = await db.create_scrape_job(
        client_id=None,
        agent_id=agent_b_id,
        url="https://beta-software.example.com",
        domain="beta-software.example.com"
    )
    draft_b = await db.create_generated_script_draft(
        job_id=job_b["id"],
        agent_id=agent_b_id,
        client_id=None,
        status="draft_ready",
        knowledge_json={
            "source_url": "https://beta-software.example.com",
            "company": {
                "name": "Beta Cloud Software",
                "summary": "Beta Cloud delivers enterprise SaaS accounting platform."
            },
            "products_or_services": [
                {"name": "Beta Ledger AI", "description": "Automated cloud bookkeeping"}
            ]
        },
        draft_json={
            "global_prompt": "Help users with Beta Ledger"
        }
    )
    # Apply draft B
    await db.mark_generated_script_draft_reviewed(draft_b["id"], status="published_live")
    
    # 4. Resolve Runtime Config for Agent A
    config_a = await AgentRuntimeResolver.resolve(agent_a_id)
    print("\n--- Agent A Config ---")
    print("has_applied_website_knowledge:", config_a.get("has_applied_website_knowledge"))
    print("source_url:", config_a.get("website_source_url"))
    assert config_a.get("has_applied_website_knowledge") is True
    assert "https://acme-inc.example.com" in config_a.get("system_prompt")
    assert "Acme manufacture heavy duty industrial anvils" in config_a.get("system_prompt")
    assert "Beta Cloud Software" not in config_a.get("system_prompt")
    print("SUCCESS: Agent A successfully resolved Acme knowledge only!")

    # 5. Resolve Runtime Config for Agent B
    config_b = await AgentRuntimeResolver.resolve(agent_b_id)
    print("\n--- Agent B Config ---")
    print("has_applied_website_knowledge:", config_b.get("has_applied_website_knowledge"))
    print("source_url:", config_b.get("website_source_url"))
    assert config_b.get("has_applied_website_knowledge") is True
    assert "https://beta-software.example.com" in config_b.get("system_prompt")
    assert "Beta Cloud Software" in config_b.get("system_prompt")
    assert "Acme" not in config_b.get("system_prompt")
    print("SUCCESS: Agent B successfully resolved Beta Cloud knowledge only!")

    # 6. Verify Cross-Agent Isolation
    assert "Beta" not in config_a.get("system_prompt")
    assert "Acme" not in config_b.get("system_prompt")
    print("SUCCESS: Multi-agent isolation confirmed: zero cross-agent knowledge leakage!")

    # 7. Resolve Runtime Config for Agent C (clean agent with no summary)
    config_c = await AgentRuntimeResolver.resolve(agent_c_id)
    print("\n--- Agent C Config ---")
    print("has_applied_website_knowledge:", config_c.get("has_applied_website_knowledge"))
    assert config_c.get("has_applied_website_knowledge") is False
    assert config_c.get("system_prompt") == "You are Clean Agent with no website knowledge."
    print("SUCCESS: Agent C without website summary cleanly uses original base prompt!")

    # 8. Re-apply Agent A with new URL (URL A2) to test Cache Invalidation & Updates
    job_a2 = await db.create_scrape_job(
        client_id=None,
        agent_id=agent_a_id,
        url="https://acme-v2.example.com",
        domain="acme-v2.example.com"
    )
    draft_a2 = await db.create_generated_script_draft(
        job_id=job_a2["id"],
        agent_id=agent_a_id,
        client_id=None,
        status="draft_ready",
        knowledge_json={
            "source_url": "https://acme-v2.example.com",
            "company": {
                "name": "Acme NextGen Robotics",
                "summary": "Acme updated site for autonomous drones."
            }
        },
        draft_json={}
    )
    await db.mark_generated_script_draft_reviewed(draft_a2["id"], status="published_live")
    
    config_a_updated = await AgentRuntimeResolver.resolve(agent_a_id)
    print("\n--- Agent A Re-applied Config ---")
    print("source_url:", config_a_updated.get("website_source_url"))
    assert config_a_updated.get("website_source_url") == "https://acme-v2.example.com"
    assert "Acme NextGen Robotics" in config_a_updated.get("system_prompt")
    print("SUCCESS: Re-applying Agent A immediately updated runtime to the latest applied website knowledge!")

    # Clean up test scratch jobs and drafts
    from db.db_manager import _get_connection
    conn = _get_connection()
    try:
        for aid in (agent_a_id, agent_b_id, agent_c_id):
            conn.execute("DELETE FROM generated_script_drafts WHERE agent_id=?", (aid,))
            conn.execute("DELETE FROM website_scrape_jobs WHERE agent_id=?", (aid,))
            conn.execute("DELETE FROM agents WHERE id=?", (aid,))
        conn.commit()
    finally:
        conn.close()
    print("\nALL 5 TEST SCENARIOS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(run_test())
