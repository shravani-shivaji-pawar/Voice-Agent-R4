import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath("."))
load_dotenv(".env")

from groq import AsyncGroq

async def main():
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    print("GROQ_API_KEY present:", bool(api_key))
    if not api_key:
        print("No Groq API Key found!")
        return
    client = AsyncGroq(api_key=api_key)
    models = await client.models.list()
    print("Available Groq Models:")
    for m in models.data:
        print(" -", m.id)

if __name__ == "__main__":
    asyncio.run(main())
