import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from llm.llm import generate_combined_intent_and_response

async def test():
    prompt = "You are a Mock Interview Coach. You help candidates practice technical interviews."
    inputs = [
        "What you do?",
        "What does your company do?",
        "Why are you out of snake dang?",
        "What is your company name?"
    ]
    for inp in inputs:
        print(f"\n--- USER INPUT: {inp} ---")
        try:
            res = await generate_combined_intent_and_response(
                user_input=inp,
                history=[],
                domain="custom",
                system_prompt=prompt
            )
            print("RESPONSE:", res.spoken_reply_text)
            print("INTENT:", res.intent_analysis.intent)
        except Exception as e:
            print("EXCEPTION:", e)

if __name__ == "__main__":
    asyncio.run(test())
