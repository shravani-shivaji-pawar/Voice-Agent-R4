import asyncio
import os
import sys
import io
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

backend_dir = r"s:\voice agent roy\Voice agent R4\Voice-agent-main\backend"
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from llm.language_utils import normalize_language_code, validate_response_language, normalize_domain_vocabulary
from llm.llm import generate_response, _classify_local_intent, _extract_budget_entity, _extract_course_entity
from llm.state_manager import StateManager

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_SCHEMA_PATH = os.path.join(_ROOT, "Updated_Real_Estate_Agent.json")

async def measure_turn_latency(user_text: str, state_mgr: StateManager, history: list, language: str = "hi") -> dict:
    t_start = time.perf_counter()
    
    # Stage 1: Domain Normalization
    t0 = time.perf_counter()
    norm_text = normalize_domain_vocabulary(user_text)
    t_norm = (time.perf_counter() - t0) * 1000

    # Stage 2: Local Entity & Intent Pre-Extraction
    t0 = time.perf_counter()
    local_info = _classify_local_intent(norm_text)
    t_local = (time.perf_counter() - t0) * 1000

    # Stage 3: Full Pipeline Execution (State Graph + LLM if invoked)
    t0 = time.perf_counter()
    reply, is_terminal = await generate_response(
        user_text=user_text,
        conversation_history=history,
        language=language,
        state_manager=state_mgr
    )
    t_gen = (time.perf_counter() - t0) * 1000

    # Stage 4: Language Validation
    t0 = time.perf_counter()
    is_valid, reason = validate_response_language(reply, language)
    t_val = (time.perf_counter() - t0) * 1000

    t_total = (time.perf_counter() - t_start) * 1000

    return {
        "user_text": user_text,
        "reply": reply,
        "is_terminal": is_terminal,
        "norm_ms": round(t_norm, 2),
        "local_ms": round(t_local, 2),
        "pipeline_gen_ms": round(t_gen, 2),
        "val_ms": round(t_val, 2),
        "total_ms": round(t_total, 2)
    }

async def run_latency_benchmark():
    print("==========================================================================================")
    print("                     VOICE AGENT R4 — EXACT LATENCY BREAKDOWN BENCHMARK                   ")
    print("==========================================================================================\n")

    test_turns = [
        ("System Trigger / Initial Greeting", "__CONNECTED__", "hi"),
        ("Qualification + Course (Local Fast Path)", "हाँ, मैं BCA कर रही हूँ और MCA करना चाहती हूँ।", "hi"),
        ("Single City (Local Fast Path)", "मुझे Pune में करना है।", "hi"),
        ("Percentage (Local Fast Path)", "मेरा प्रतिशत 78 है।", "hi"),
        ("Budget Range (Local Fast Path)", "मेरा बजट 2 से 3 लाख है।", "hi"),
        ("General Education Question", "What is MCA?", "hi"),
        ("Short Acknowledgement", "ठीक है", "hi"),
        ("Goodbye / Goodbye Sign-off", "ठीक है, धन्यवाद, बाय।", "hi"),
    ]

    state_mgr = StateManager(STATE_SCHEMA_PATH)
    state_mgr.reset_state(language="hi")
    history = []

    print(f"{'Turn Type':<38} | {'Local Extract':<12} | {'Pipeline/LLM':<14} | {'Val Check':<10} | {'Total Latency':<12}")
    print("-" * 98)

    for label, user_input, lang in test_turns:
        res = await measure_turn_latency(user_input, state_mgr, history, language=lang)
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": res["reply"]})
        
        print(f"{label:<38} | {res['local_ms']:>8.2f} ms | {res['pipeline_gen_ms']:>10.2f} ms | {res['val_ms']:>6.2f} ms | {res['total_ms']:>10.2f} ms")

    print("-" * 98)

if __name__ == "__main__":
    asyncio.run(run_latency_benchmark())
