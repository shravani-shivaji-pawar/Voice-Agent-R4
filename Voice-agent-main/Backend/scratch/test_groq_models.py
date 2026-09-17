import asyncio
import os
from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv()
key = os.getenv("GROQ_API_KEY")
client = AsyncGroq(api_key=key)

async def test():
    try:
        models = await client.models.list()
        for m in models.data:
            print(f"AVAILABLE MODEL: id='{m.id}'")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test())
