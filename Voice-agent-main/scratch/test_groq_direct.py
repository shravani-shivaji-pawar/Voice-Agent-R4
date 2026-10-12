import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(r"s:\voice agent roy\Voice agent R4\Voice-agent-main\Backend\.env")
load_dotenv(env_path)

from groq import AsyncGroq

async def test_groq():
    api_key = os.getenv("GROQ_API_KEY", "")
    print("GROQ_API_KEY present:", bool(api_key), "Key start:", api_key[:10])
    client = AsyncGroq(api_key=api_key)
    candidate_models = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "llama3-70b-8192",
        "llama3-8b-8192",
        "mixtral-8x7b-32768",
        "gemma2-9b-it",
        "qwen-2.5-32b"
    ]
    for model in candidate_models:
        try:
            res = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "hello"}],
                max_tokens=10
            )
            print(f"SUCCESS model '{model}': {res.choices[0].message.content}")
            break
        except Exception as e:
            print(f"FAILED model '{model}': {e}")

if __name__ == "__main__":
    asyncio.run(test_groq())
