"""
Multi-Agent Runtime Isolation & Prompt Cross-Contamination Test Suite.

Verifies that:
1. AgentRuntimeResolver resolves custom and built-in agents without hardcoded fallbacks.
2. Custom agents (e.g. LIC Insurance, Restaurant) use their own prompts and greetings.
3. LLM Processor processes turns based on the agent's exact prompt.
4. Consecutive calls to different agents maintain strict isolation without state leakage.
"""

import asyncio
from unittest.mock import AsyncMock, patch
from runtime_resolver import AgentRuntimeResolver
from db.db_manager import db
from flows.runtime import RealEstateLLMProcessor


def test_agent_runtime_resolver_isolation():
    """Verify resolver isolates custom agents from built-in fallbacks."""
    async def _run():
        # Seed mock custom agents into DB memory for testing
        lic_agent = {
            "id": "lic_insurance_101",
            "name": "LIC Insurance Advisor",
            "script": "You are a professional LIC Insurance customer support representative.",
            "greeting_response": "Welcome to LIC Customer Care. How can I assist with your policy today?",
            "voice": "kavya",
            "agent_type": "insurance",
            "status": "published"
        }
        
        restaurant_agent = {
            "id": "table_booking_202",
            "name": "Gourmet Bistro Hostess",
            "script": "You are a restaurant receptionist handling dining reservations.",
            "greeting_response": "Hello! Welcome to Gourmet Bistro. Would you like to reserve a table?",
            "voice": "anika",
            "agent_type": "hospitality",
            "status": "published"
        }

        await db.save_agent(lic_agent)
        await db.save_agent(restaurant_agent)

        # Resolve LIC agent
        lic_config = await AgentRuntimeResolver.resolve("lic_insurance_101")
        assert lic_config["id"] == "lic_insurance_101"
        assert lic_config["name"] == "LIC Insurance Advisor"
        assert "LIC Insurance customer support" in lic_config["system_prompt"]
        assert lic_config["greeting_response"] == "Welcome to LIC Customer Care. How can I assist with your policy today?"
        assert lic_config["is_builtin"] is False

        # Resolve Restaurant agent
        rest_config = await AgentRuntimeResolver.resolve("table_booking_202")
        assert rest_config["id"] == "table_booking_202"
        assert rest_config["name"] == "Gourmet Bistro Hostess"
        assert "restaurant receptionist" in rest_config["system_prompt"]
        assert rest_config["greeting_response"] == "Hello! Welcome to Gourmet Bistro. Would you like to reserve a table?"
        assert rest_config["is_builtin"] is False

        # Resolve Builtin Education agent
        edu_config = await AgentRuntimeResolver.resolve("education")
        assert edu_config["id"] == "education"
        assert "Aarohi" in edu_config["name"] or "Education" in edu_config["name"]
        assert edu_config["is_builtin"] is True

    asyncio.run(_run())


def test_llm_processor_custom_prompt_execution():
    """Verify RealEstateLLMProcessor respects custom agent prompt without schema fallback leakage."""
    async def _run():
        custom_agent = {
            "id": "lic_insurance_101",
            "name": "LIC Insurance Advisor",
            "script": "You are an LIC Insurance assistant. Only discuss insurance policies, premiums, and coverage.",
            "greeting_response": "Welcome to LIC support!",
            "voice": "kavya"
        }
        await db.save_agent(custom_agent)

        processor = RealEstateLLMProcessor(agent_id="lic_insurance_101")
        
        # Verify initialized config loaded from DB/Resolver
        assert processor.agent_config["id"] == "lic_insurance_101"
        assert processor.agent_config["system_prompt"] == custom_agent["script"]

        # Test processing a frame through processor
        from pipecat.frames.frames import TextFrame
        text_frame = TextFrame(text="What is the status of my life insurance policy?")
        
        # Mock LLM response to simulate LLM invocation
        with patch("llm.llm.generate_combined_intent_and_response", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = {
                "intent": "policy_inquiry",
                "extracted": {},
                "response": "I can help you check your LIC policy status. Could you share your policy number?"
            }

            # Process frame
            await processor.process_frame(text_frame)
            
            mock_gen.assert_called_once()
            call_kwargs = mock_gen.call_args[1]
            assert call_kwargs["system_prompt"] == custom_agent["script"]

    asyncio.run(_run())


def test_consecutive_multi_agent_session_isolation():
    """Verify consecutive turns with different agents maintain 100% state isolation."""
    async def _run():
        agent_a = {
            "id": "agent_alpha",
            "name": "Alpha Agent",
            "script": "You are Agent Alpha.",
            "greeting_response": "Greetings from Alpha.",
        }
        agent_b = {
            "id": "agent_beta",
            "name": "Beta Agent",
            "script": "You are Agent Beta.",
            "greeting_response": "Greetings from Beta.",
        }

        await db.save_agent(agent_a)
        await db.save_agent(agent_b)

        proc_a = RealEstateLLMProcessor(agent_id="agent_alpha")
        proc_b = RealEstateLLMProcessor(agent_id="agent_beta")

        assert proc_a.agent_id != proc_b.agent_id
        assert proc_a.agent_config["greeting_response"] == "Greetings from Alpha."
        assert proc_b.agent_config["greeting_response"] == "Greetings from Beta."

    asyncio.run(_run())


if __name__ == "__main__":
    print("Running multi-agent isolation tests...")
    test_agent_runtime_resolver_isolation()
    print("  [OK] AgentRuntimeResolver test passed")
    test_llm_processor_custom_prompt_execution()
    print("  [OK] LLM Processor custom prompt test passed")
    test_consecutive_multi_agent_session_isolation()
    print("  [OK] Consecutive multi-agent session isolation test passed")
    print("\nALL MULTI-AGENT ISOLATION TESTS PASSED SUCCESSFULLY!")

