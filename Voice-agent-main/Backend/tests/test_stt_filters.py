import sys
import os

backend_dir = r"s:\voice agent roy\Voice agent R4\Voice-agent-main\backend"
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from flows.runtime import _strip_stt_special_tokens, _is_actionable_transcript

def test_stt_hallucination_filters():
    test_cases = [
        ("<|hi|> hendur, Maud , Maud , Maud , Maud , Maud , Maud , Maud .", False),
        ("<|hi|>, 4BHK, budget, buy.", False),
        ("<|hi|>,<|hi|>, आए, आए, आए.", False),
        ("ठीक है.", True),
        ("I want to buy a 2BHK.", True),
        ("My budget is around 50 lakhs to 70 lakhs.", True),
        ("मुझे जयपुर में 2 BHK फ्लैट देखना है।", True),
    ]

    print("========================================================")
    print("TESTING STT SPECIAL TOKEN & HALLUCINATION FILTERS")
    print("========================================================\n")

    for raw, expected in test_cases:
        cleaned = _strip_stt_special_tokens(raw)
        actionable = _is_actionable_transcript(raw)
        print(f"RAW INPUT   : {raw!r}")
        print(f"CLEANED     : {cleaned!r}")
        print(f"ACTIONABLE  : {actionable} (Expected: {expected})")
        assert actionable == expected, f"FAIL: Expected actionable={expected} for {raw!r}, got {actionable}"
        print(">>> PASS\n")

    print("ALL STT HALLUCINATION FILTER TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_stt_hallucination_filters()
