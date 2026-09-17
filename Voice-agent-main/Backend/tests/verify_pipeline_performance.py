"""
Pipeline Latency and Performance Benchmark Script.
"""

import asyncio
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.language_utils import strip_stt_control_tokens, analyze_user_text
from llm.state_manager import StateManager
from llm.llm import generate_response
from stt import config as stt_cfg

async def run_benchmark():
    print("==================================================")
    print("RUNNING VOICE AGENT R4 LATENCY & PERFORMANCE BENCHMARK")
    print("==================================================\n")

    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    schema_path = os.path.join(_root, "Updated_Real_Estate_Agent.json")
    state_mgr = StateManager(schema_path)
    state_mgr.reset_state()

    print(f"[CONFIG] VAD Trailing Silence MS: {stt_cfg.STT_TRAILING_SILENCE_MS}ms")
    print(f"[CONFIG] Min Voice Start MS:      {stt_cfg.MIN_VOICE_START_MS}ms")

    # 1. Preprocessing & Control Token Benchmark
    t0 = time.perf_counter()
    cleaned, lang = strip_stt_control_tokens("<|hi|><|hi|>")
    dt_prep = (time.perf_counter() - t0) * 1000
    print(f"[PREPROCESSING] STT Control Token Stripping Latency: {dt_prep:.3f}ms")

    # 2. State & LLM Generation Benchmark
    sample_inputs = [
        "हाँ, मुझे प्रॉपर्टी खरीदनी है.",
        "मैं Jaipur में apartment खरीदने पर विचार कर रही हूँ.",
        "मेरा बजट 50 lakhs to 70 lakhs है और मुझे 2BHK खरीदना है.",
    ]

    history = []
    latencies = []

    for turn_idx, text in enumerate(sample_inputs, 1):
        t_start = time.perf_counter()
        
        # Preprocessing
        c_text, _ = strip_stt_control_tokens(text)
        t_prep = time.perf_counter()
        
        # State + LLM response
        reply, terminal = await generate_response(
            c_text,
            conversation_history=history,
            language="hi",
            state_manager=state_mgr
        )
        t_llm = time.perf_counter()
        
        history.append({"role": "user", "content": c_text})
        history.append({"role": "assistant", "content": reply})

        prep_time = (t_prep - t_start) * 1000
        llm_time = (t_llm - t_prep) * 1000
        total_turn = (t_llm - t_start) * 1000
        latencies.append(total_turn)

        print(f"[TURN {turn_idx}] Prep: {prep_time:.2f}ms | LLM Generation: {llm_time:.2f}ms | Total Pipeline Turn: {total_turn:.2f}ms")

    avg_lat = sum(latencies) / len(latencies)
    print(f"\n[SUMMARY] Average LLM Generation + State Latency: {avg_lat:.2f}ms")
    print("==================================================")
    print("BENCHMARK COMPLETED SUCCESSFULLY")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
