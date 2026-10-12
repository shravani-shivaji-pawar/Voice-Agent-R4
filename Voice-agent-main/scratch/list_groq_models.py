import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(r"s:\voice agent roy\Voice agent R4\Voice-agent-main\Backend\.env")
load_dotenv(env_path)

from groq import AsyncGroq

async def list_models():
    api_key = os.getenv("GROQ_API_KEY", "")
    client = AsyncGroq(api_key=api_key)
    try:
        models = await client.models.list()
        print("Available Groq models:")
        for m in models.data:
            print(" -", m.id)
    except Exception as e:
        print("Error listing models:", e)

if __name__ == "__main__":
    asyncio.run(list_models())
