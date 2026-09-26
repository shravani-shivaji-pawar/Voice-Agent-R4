import asyncio
import os
import sys
import time
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath("."))
load_dotenv(".env")

from runtime_resolver import AgentRuntimeResolver
from llm.llm import generate_combined_intent_and_response
from tts import generate_speech_stream

async def measure_all():
    print("========================================================================")
    print("                     VOICE AGENT LATENCY MEASUREMENT                     ")
    print("========================================================================\n")

    config = await AgentRuntimeResolver.resolve("agent-49f64ad7d683")
    print(f"Agent: {config['name']} ({config['id']})")
    print(f"Has Applied Knowledge: {config['has_applied_website_knowledge']}\n")
    
    test_queries = [
        "What do you do?",
        "What does your company do?",
        "What is your company name?"
    ]

    llm_latencies = []
    tts_first_byte_latencies = []
    history = []

    for query in test_queries:
        print(f"--- Turn Query: '{query}' ---")

        # 1. LLM Generation Latency
        t_llm_start = time.perf_counter()
        res = await generate_combined_intent_and_response(
            user_input=query,
            history=history,
            domain=config.get("agent_type", "custom"),
            system_prompt=config.get("system_prompt")
        )
        t_llm_end = time.perf_counter()
        llm_ms = (t_llm_end - t_llm_start) * 1000
        llm_latencies.append(llm_ms)

        reply = res.spoken_reply_text
        print(f"LLM Reply: '{reply}'")
        print(f"LLM Latency: {llm_ms:.2f} ms")

        # 2. TTS First Byte Latency
        t_tts_start = time.perf_counter()
        first_byte_ms = 0.0
        try:
            gen = generate_speech_stream(
                text=reply,
                preferred_language="en",
                agent_id=config["id"]
            )
            for chunk in gen:
                if chunk and len(chunk) > 0:
                    t_tts_first = time.perf_counter()
                    first_byte_ms = (t_tts_first - t_tts_start) * 1000
                    break
        except Exception as tts_err:
            print("TTS error:", tts_err)

        if first_byte_ms > 0:
            tts_first_byte_latencies.append(first_byte_ms)
            print(f"TTS First-Byte Latency: {first_byte_ms:.2f} ms")

        total_turn_ms = llm_ms + first_byte_ms
        print(f"Subtotal Processing (LLM + TTS First Byte): {total_turn_ms:.2f} ms\n")

        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": reply})

    print("========================================================================")
    print("                             LATENCY SUMMARY                            ")
    print("========================================================================")
    avg_llm = sum(llm_latencies) / len(llm_latencies) if llm_latencies else 0
    avg_tts = sum(tts_first_byte_latencies) / len(tts_first_byte_latencies) if tts_first_byte_latencies else 0
    print(f"Average LLM Generation Latency:       {avg_llm:.2f} ms")
    print(f"Average TTS First-Byte Latency:       {avg_tts:.2f} ms")
    print(f"Average Processing (LLM + TTS First):  {avg_llm + avg_tts:.2f} ms")
    print("========================================================================\n")

if __name__ == "__main__":
    asyncio.run(measure_all())
