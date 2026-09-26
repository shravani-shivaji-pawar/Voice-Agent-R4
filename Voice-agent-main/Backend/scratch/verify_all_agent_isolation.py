import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath("."))
load_dotenv(".env")

from runtime_resolver import AgentRuntimeResolver
from llm.llm import generate_combined_intent_and_response
from db.db_manager import db

async def test_all():
    print("=== STARTING AGENT RUNTIME & ISOLATION VERIFICATION ===")

    # 1. Mock Interview Coach Test
    print("\n--- 1. Mock Interview Coach Test ---")
    mock_config = await AgentRuntimeResolver.resolve("agent-49f64ad7d683")
    print(f"Agent ID: {mock_config['id']}")
    print(f"Agent Name: {mock_config['name']}")
    print(f"Agent Type: {mock_config['agent_type']}")
    print(f"Has Applied Knowledge: {mock_config['has_applied_website_knowledge']}")
    
    mock_query = "What do you do?"
    mock_res = await generate_combined_intent_and_response(
        user_input=mock_query,
        history=[],
        domain=mock_config["agent_type"],
        system_prompt=mock_config["system_prompt"]
    )
    print(f"User: {mock_query}")
    print(f"Reply: {mock_res.spoken_reply_text}")
    
    assert "happy to help with that" not in mock_res.spoken_reply_text.lower(), "FAILED: Returned Real Estate fallback!"
    assert "priya" not in mock_res.spoken_reply_text.lower(), "FAILED: Returned Priya identity!"
    assert "suncity" not in mock_res.spoken_reply_text.lower(), "FAILED: Returned Suncity identity!"
    print("SUCCESS: Mock Interview Coach answered strictly within its own persona!")

    # 2. Multi-Agent Isolation Test (Agent A vs Agent B)
    print("\n--- 2. Multi-Agent Isolation Test ---")
    agent_a_id = "test-agent-alpha-101"
    agent_b_id = "test-agent-beta-202"
    
    await db.save_agent({
        "id": agent_a_id,
        "name": "Quantum Computing Tutor",
        "agent_type": "custom",
        "script": "You are Quantum Computing Tutor. You specialize strictly in qubits, quantum superposition, and quantum gates."
    })
    await db.save_agent({
        "id": agent_b_id,
        "name": "Italian Culinary Chef",
        "agent_type": "custom",
        "script": "You are Italian Culinary Chef. You specialize strictly in authentic Italian pasta, risotto, and woodfired pizza."
    })

    cfg_a = await AgentRuntimeResolver.resolve(agent_a_id)
    cfg_b = await AgentRuntimeResolver.resolve(agent_b_id)

    res_a = await generate_combined_intent_and_response(
        user_input="What is your main expertise?",
        history=[],
        domain=cfg_a["agent_type"],
        system_prompt=cfg_a["system_prompt"]
    )
    res_b = await generate_combined_intent_and_response(
        user_input="What is your main expertise?",
        history=[],
        domain=cfg_b["agent_type"],
        system_prompt=cfg_b["system_prompt"]
    )

    print(f"Agent A ({cfg_a['name']}): {res_a.spoken_reply_text}")
    print(f"Agent B ({cfg_b['name']}): {res_b.spoken_reply_text}")

    assert "quantum" in res_a.spoken_reply_text.lower() or "qubit" in res_a.spoken_reply_text.lower(), "Agent A failed domain check"
    assert "italian" in res_b.spoken_reply_text.lower() or "pasta" in res_b.spoken_reply_text.lower() or "pizza" in res_b.spoken_reply_text.lower() or "culinary" in res_b.spoken_reply_text.lower(), "Agent B failed domain check"
    assert "pasta" not in res_a.spoken_reply_text.lower(), "Cross-agent leakage detected in Agent A!"
    assert "quantum" not in res_b.spoken_reply_text.lower(), "Cross-agent leakage detected in Agent B!"
    print("SUCCESS: Multi-agent isolation confirmed! Zero cross-agent context leakage!")

    # 3. Builtin Agent Preservation Test
    print("\n--- 3. Builtin Real Estate & Education Agent Preservation ---")
    re_cfg = await AgentRuntimeResolver.resolve("real_estate")
    edu_cfg = await AgentRuntimeResolver.resolve("education")
    
    assert re_cfg["agent_type"] == "real_estate_sales", "Real Estate agent type modified!"
    assert edu_cfg["agent_type"] == "education", "Education agent type modified!"
    print("SUCCESS: Built-in Real Estate and Education agent configurations preserved perfectly!")

    print("\n=== ALL VERIFICATION CHECKS PASSED 100% ===")

if __name__ == "__main__":
    asyncio.run(test_all())
