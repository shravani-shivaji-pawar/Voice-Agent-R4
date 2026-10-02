"""
test_live_multi_voice_synthesis.py

Verifies live Smallest AI TTS audio generation payload across multiple switchable voices.
"""

import sys
import os
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from tts.tts_smallest import generate_speech_stream, _resolve_speaker

def test_voices():
    voices_to_test = [
        ("anika", "lightning_v3.1", "en", "Hello, this is Anika speaking in her natural sales tone."),
        ("dhruv", "lightning_v3.1", "en", "Hello, this is Dhruv speaking in a clear confident voice."),
        ("devansh", "lightning_v3.1", "en", "Hello, this is Devansh speaking in his professional tone."),
        ("meher", "lightning_v3.1_pro", "en", "Hello, this is Meher speaking in her expressive pro voice."),
    ]

    print("=== SMALLEST AI MULTI-VOICE SYNTHESIS TEST ===")
    for voice_name, model_name, lang, sample_text in voices_to_test:
        resolved_voice, resolved_model = _resolve_speaker(voice_name, model=model_name, language=lang)
        print(f"\n[TESTING VOICE] Requested='{voice_name}' -> Resolved='{resolved_voice}' (model={resolved_model})")
        
        chunks = list(generate_speech_stream(
            text=sample_text,
            preferred_language=lang,
            speaker=voice_name,
            model=model_name
        ))
        
        total_bytes = sum(len(c) for c in chunks if c)
        print(f" -> Yielded {len(chunks)} chunks, Total PCM16 Bytes: {total_bytes}")
        assert total_bytes > 0, f"Expected audio bytes for voice {voice_name}, got {total_bytes}"
        print(f" -> SUCCESS: Audio stream generated cleanly for {resolved_voice}!")

if __name__ == "__main__":
    test_voices()
