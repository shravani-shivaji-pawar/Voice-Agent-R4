"""
Test script for verifying built-in test agent seeding and alias resolution in SQLite database.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import pytest
from db.db_manager import db

@pytest.mark.anyio
async def test_builtin_agents():
    print("[TEST] Initializing database...")
    await db.initialize()

    print("[TEST] Testing list_agents()...")
    agents = await db.list_agents()
    print(f"[TEST] Total agents found in DB: {len(agents)}")
    for a in agents:
        print(f"  - Agent ID: '{a.get('id')}', Name: '{a.get('name')}', Type: '{a.get('agent_type')}'")

    # Verify built-in test agents exist
    education_agent = await db.get_agent("education")
    assert education_agent is not None, "Built-in agent 'education' should exist"
    assert "Aarohi" in education_agent.get("name", ""), f"Agent 'education' name should contain Aarohi, got {education_agent.get('name')}"

    real_estate_agent = await db.get_agent("real_estate")
    assert real_estate_agent is not None, "Built-in agent 'real_estate' should exist"
    assert "Priya" in real_estate_agent.get("name", ""), f"Agent 'real_estate' name should contain Priya, got {real_estate_agent.get('name')}"

    # Verify alias lookups work
    edu_counselling_alias = await db.get_agent("education_counselling")
    assert edu_counselling_alias is not None, "Alias 'education_counselling' should resolve"
    assert edu_counselling_alias.get("id") in ["education", "education_counselling"]

    real_estate_sales_alias = await db.get_agent("real_estate_sales")
    assert real_estate_sales_alias is not None, "Alias 'real_estate_sales' should resolve"
    assert real_estate_sales_alias.get("id") in ["real_estate", "real_estate_sales"]

    default_alias = await db.get_agent("default")
    assert default_alias is not None, "Alias 'default' should resolve to real estate agent"

    print("\n[SUCCESS] All built-in test agent seeding and alias resolution tests passed!")

if __name__ == "__main__":
    asyncio.run(test_builtin_agents())
