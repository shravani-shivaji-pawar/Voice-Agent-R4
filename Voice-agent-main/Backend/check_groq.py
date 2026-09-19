import os
import asyncio
from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv()

async def main():
    client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
    models = await client.models.list()
    for m in models.data:
        print("Model ID:", m.id)

if __name__ == "__main__":
    asyncio.run(main())
