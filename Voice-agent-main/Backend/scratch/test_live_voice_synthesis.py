"""
test_live_voice_synthesis.py
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from tts.tts_smallest import generate_speech_stream

voices_to_test = [
    ("anika", "lightning_v3.1", "en", "Hello! This is Anika speaking."),
    ("devansh", "lightning_v3.1", "en", "Hello! This is Devansh speaking."),
    ("meher", "lightning_v3.1_pro", "en", "Hello! This is Meher speaking."),
    ("arav", "lightning_v3.1_pro", "en", "Hello! This is Arav speaking."),
    ("emily", "lightning_v3.1_pro", "en", "Hello! This is Emily speaking."),
]

print("=== Testing Live Smallest AI Voice Synthesis ===")
for vid, model, lang, text in voices_to_test:
    chunks = list(generate_speech_stream(text=text, preferred_language=lang, speaker=vid, model=model))
    total_bytes = sum(len(c) for c in chunks)
    print(f"Voice: {vid:10s} | Model: {model:18s} | Chunks: {len(chunks):3d} | Total Bytes: {total_bytes:6d} PCM")

print("=== Voice Synthesis Test Complete ===")
