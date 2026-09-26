import asyncio
import os
import sys
import time
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath("."))
load_dotenv(".env")

from groq import AsyncGroq

async def test_groq_speed():
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    client = AsyncGroq(api_key=api_key)
    
    prompt = """You are Mock Interview Coach.
Respond ONLY with a valid JSON object matching this schema:
{
  "intent_analysis": {"intent": "DISCOVERY", "confidence_score": 1.0, "entities": {}},
  "spoken_reply_text": "Your natural spoken response here"
}"""
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "What do you do?"}
    ]

    for i in range(3):
        t0 = time.perf_counter()
        resp = await client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=messages,
            temperature=0.2,
            max_tokens=120
        )
        t_ms = (time.perf_counter() - t0) * 1000
        print(f"Run {i+1} completed in {t_ms:.2f} ms: {resp.choices[0].message.content.strip()}")

if __name__ == "__main__":
    asyncio.run(test_groq_speed())
