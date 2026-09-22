"""
Test script for verifying Smallest AI TTS audio streaming capability.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import pytest
from tts.tts_smallest import stream_smallest_tts

@pytest.mark.anyio
async def test_audio_stream():
    print("[TEST] Testing Smallest AI TTS streaming generation...")
    text = "Hello, I am Aarohi from education counselling. How can I guide you today?"
    chunks = []
    total_bytes = 0

    async for chunk in stream_smallest_tts(text, voice="emily", model="lightning_v3.1"):
        chunks.append(chunk)
        total_bytes += len(chunk)

    print(f"[TEST] TTS Stream Results: {len(chunks)} chunks received, total {total_bytes} bytes of PCM16 audio.")
    assert len(chunks) > 0, "TTS should return audio chunks"
    assert total_bytes > 1000, f"Total audio bytes should be significant, got {total_bytes}"

    print("[SUCCESS] Smallest AI TTS audio streaming test passed!")

if __name__ == "__main__":
    asyncio.run(test_audio_stream())
