import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath("."))
from runtime_resolver import AgentRuntimeResolver

async def main():
    config = await AgentRuntimeResolver.resolve("agent-49f64ad7d683")
    print("Resolved Agent Config:")
    print("  - ID:", config.get("id"))
    print("  - Name:", config.get("name"))
    print("  - Agent Type:", config.get("agent_type"))
    print("  - Base Prompt:", config.get("base_prompt"))
    print("  - System Prompt:", config.get("system_prompt")[:150] + "...")
    print("  - Greeting:", config.get("greeting_response"))
    print("  - Has Applied Knowledge:", config.get("has_applied_website_knowledge"))

if __name__ == "__main__":
    asyncio.run(main())
