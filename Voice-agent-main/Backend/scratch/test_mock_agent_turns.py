import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath("."))
load_dotenv(".env")

from runtime_resolver import AgentRuntimeResolver
from llm.llm import generate_combined_intent_and_response

async def main():
    config = await AgentRuntimeResolver.resolve("agent-49f64ad7d683")
    print("Agent Name:", config.get("name"))
    print("Agent Type:", config.get("agent_type"))
    print("Has Applied Knowledge:", config.get("has_applied_website_knowledge"))
    
    user_inputs = [
        "What do you do?",
        "What does your company do?",
        "What is your company name?"
    ]
    history = []
    for inp in user_inputs:
        print(f"\nUser: {inp}")
        res = await generate_combined_intent_and_response(
            user_input=inp,
            history=history,
            domain=config.get("agent_type", "custom"),
            system_prompt=config.get("system_prompt")
        )
        reply = res.spoken_reply_text
        print(f"Agent ({config.get('name')}): {reply}")
        history.append({"role": "user", "content": inp})
        history.append({"role": "assistant", "content": reply})

if __name__ == "__main__":
    asyncio.run(main())
