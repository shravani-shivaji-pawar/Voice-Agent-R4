"""
Test Phase 15: Exact conversation scenario verification.
"""

import asyncio
import os
import sys

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.language_utils import strip_stt_control_tokens, normalize_language_code
from llm.state_manager import StateManager
from llm.llm import generate_response

async def run_phase15_test():
    print("==================================================")
    print("STARTING PHASE 15 END-TO-END CONVERSATION TEST")
    print("==================================================\n")

    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    schema_path = os.path.join(_root, "Updated_Real_Estate_Agent.json")
    state_mgr = StateManager(schema_path)
    state_mgr.reset_state()
    history = []
    session_lang = "hi"

    # Step 1: Initial Greeting (Dashboard language = Hindi)
    reply, terminal = await generate_response(
        "[System: The call has just been connected.]",
        conversation_history=history,
        language=session_lang,
        state_manager=state_mgr,
        allow_transition=False
    )
    history.append({"role": "assistant", "content": reply})
    print(f"Turn 0 [Greeting]:\n  Agent: {reply}\n")
    assert any(w in reply for w in ["नमस्ते", "सनसिटी", "प्रिया", "स्वागत", "नमस्कार", "बोल"]), f"Expected Hindi greeting, got: {reply}"

    turns = [
        "हाँ, मुझे प्रॉपर्टी खरीदनी है.",
        "मैं Jaipur में apartment खरीदने पर विचार कर रही हूँ.",
        "मेरा बजट 50 lakhs to 70 lakhs है और मुझे 2BHK खरीदना है.",
        "मुझे 5-6 दिनों में घर चाहिए.",
        "हाँ, ठीक है.",
        "मेरा मोबाइल नंबर 1234567890 है.",
        "हाँ रविवार ठीक है.",
        "मुझे Jaipur में घर खरीदना है, मैंने आपको बताया है.",
    ]

    for i, u_input in enumerate(turns, 1):
        # Control token check
        cleaned, _ = strip_stt_control_tokens(u_input)
        assert cleaned, "Valid turn was accidentally stripped!"
        
        reply, terminal = await generate_response(
            cleaned,
            conversation_history=history,
            language=session_lang,
            state_manager=state_mgr
        )
        history.append({"role": "user", "content": cleaned})
        history.append({"role": "assistant", "content": reply})

        slots = state_mgr.conversation_data
        print(f"Turn {i}:\n  User:  {u_input}\n  Agent: {reply}")
        print(f"  State: location={slots.get('location')}, bhk={slots.get('property_type') or slots.get('bhk')}, budget={slots.get('budget')}\n")

        # Verify strict rules
        reply_lower = reply.lower()
        if slots.get("location") == "Jaipur":
            assert "किस शहर" not in reply, f"Agent asked for city when location is already Jaipur! Reply: {reply}"
            assert "जोधपुर" not in reply and "मदुरै" not in reply, f"Agent invented Jodhpur/Madurai! Reply: {reply}"
        if slots.get("budget"):
            assert "बजट लगभग कितना" not in reply and "क्या बजट" not in reply, f"Agent asked for budget when budget is already set! Reply: {reply}"

    # Test control tokens
    print("\nTesting STT control tokens (<|hi|>, <|hi|><|hi|>):")
    tok1, _ = strip_stt_control_tokens("<|hi|>")
    tok2, _ = strip_stt_control_tokens("<|hi|><|hi|>")
    print(f"  '<|hi|>' cleaned -> '{tok1}' (empty = {not bool(tok1)})")
    print(f"  '<|hi|><|hi|>' cleaned -> '{tok2}' (empty = {not bool(tok2)})")
    assert not tok1 and not tok2, "Control tokens were not stripped cleanly!"

    # Test closing
    print("\nTesting Conversation Closing ('Bye'):")
    reply, terminal = await generate_response(
        "Bye",
        conversation_history=history,
        language=session_lang,
        state_manager=state_mgr
    )
    print(f"  User:  Bye\n  Agent: {reply}\n  Terminal: {terminal}\n  Session Ended: {getattr(state_mgr, '_session_ended', False)}")
    assert getattr(state_mgr, "_session_ended", False) or terminal or state_mgr.current_node_id == "CLOSING", "State did not transition to closing!"

    print("==================================================")
    print("PHASE 15 TEST PASSED 100% SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_phase15_test())
