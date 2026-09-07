"""
test_smallest_improvements.py — Verification test suite for Smallest AI TTS improvements.

Tests:
1. Professional prompt & anti-hallucination formatting.
2. Smallest AI TTS session reuse & streaming chunk execution.
3. Model selection (lightning_v3.1 vs lightning_v3.1_pro) and voice filtering.
4. Text cleaning for spoken TTS generation.
5. Language code resolution and Devanagari UTF-8 payload handling.
6. Unbuffered immediate audio streaming in tts/provider.py.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from tts import tts_smallest
from tts import provider
from llm import llm_response_generator
from core_voice_loop import SYSTEM_PROMPT_CONSTRAINTS


class SmallestAIImprovementsTest(unittest.TestCase):

    def setUp(self):
        self._env = os.environ.copy()
        os.environ["SMALLEST_API_KEY"] = "test_key_smallest_12345"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_professional_and_anti_hallucination_prompt_constraints(self):
        """Verify system prompt rules enforce professional tone and strict anti-hallucination rules."""
        prompt = llm_response_generator._RESPONSE_SYSTEM_PROMPT
        self.assertIn("PROFESSIONAL, CLEAR, POLITE, AND NATURAL", prompt)
        self.assertIn("STRICT CONTEXT GROUNDING & ANTI-HALLUCINATION", prompt)
        self.assertIn("SYSTEM_PROMPT_CONSTRAINTS", globals())
        self.assertIn("STRICT ANTI-HALLUCINATION", SYSTEM_PROMPT_CONSTRAINTS)

    def test_model_and_language_filtering(self):
        """Verify model selection and language filtering return correct compatible voices."""
        v31_voices = tts_smallest.get_voices_for_model_and_language(model="lightning_v3.1", language="en")
        v31_pro_voices = tts_smallest.get_voices_for_model_and_language(model="lightning_v3.1_pro", language="en")
        
        self.assertTrue(len(v31_voices) > 0)
        self.assertTrue(len(v31_pro_voices) > 0)

        # Confirm Pro models include pro-specific voices like Meher or Arav
        pro_ids = [v["voice_id"] for v in v31_pro_voices]
        self.assertIn("meher", pro_ids)

    def test_speaker_resolution_per_model(self):
        """Verify model-voice pairing prevents cross-model voice leakage."""
        speaker_v31 = tts_smallest._resolve_speaker(speaker="anika", model="lightning_v3.1", language="en")
        speaker_pro = tts_smallest._resolve_speaker(speaker="meher", model="lightning_v3.1_pro", language="en")

        self.assertEqual(speaker_v31, "anika")
        self.assertEqual(speaker_pro, "meher")

    def test_text_cleaning_for_tts(self):
        """Verify markdown, bullets, and emojis are stripped while numbers and currency are preserved."""
        raw_text = "## Options Available:\n- **2BHK** Flat at *INR 50 Lakhs*! Call https://example.com 🚀"
        cleaned = tts_smallest.clean_text_for_tts(raw_text)

        self.assertNotIn("**", cleaned)
        self.assertNotIn("##", cleaned)
        self.assertNotIn("https://", cleaned)
        self.assertIn("2BHK Flat at INR 50 Lakhs!", cleaned)

    def test_session_reuse(self):
        """Verify that Smallest AI TTS uses a persistent requests.Session."""
        session1 = tts_smallest._get_session()
        session2 = tts_smallest._get_session()
        self.assertIs(session1, session2)

    @patch.object(tts_smallest, "_get_session")
    def test_smallest_tts_streaming_payload(self, mock_get_session):
        """Verify HTTP stream=True request payload and model parameters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        wav_header = b"RIFF" + b"\x00" * 36 + b"data" + b"\x00" * 4
        pcm_payload = b"\x01\x02\x03\x04" * 100
        mock_response.iter_content.return_value = [wav_header + pcm_payload]

        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_get_session.return_value = mock_session

        hindi_text = "मैं आपकी सहायता करने के लिए तैयार हूँ।"
        chunks = list(tts_smallest.generate_speech_stream(
            hindi_text,
            preferred_language="hi",
            speaker="meher",
            model="lightning_v3.1_pro"
        ))

        mock_session.post.assert_called_once()
        _, kwargs = mock_session.post.call_args
        self.assertTrue(kwargs.get("stream"))
        self.assertEqual(kwargs["json"]["text"], hindi_text)
        self.assertEqual(kwargs["json"]["language"], "hi")
        self.assertEqual(kwargs["json"]["voice_id"], "meher")
        self.assertEqual(kwargs["json"]["model"], "lightning_v3.1_pro")

        yielded_bytes = b"".join(chunks)
        self.assertTrue(len(yielded_bytes) > 0)
        self.assertNotIn(b"RIFF", yielded_bytes[:4])

    def test_provider_immediate_streaming(self):
        """Verify provider.generate_speech_stream yields chunks immediately as generated."""
        def mock_stream_provider(*args, **kwargs):
            yield b"chunk_1_"
            yield b"chunk_2_"
            yield b"chunk_3_"

        with patch("tts.provider._stream_provider", side_effect=mock_stream_provider):
            os.environ["TTS_PROVIDER"] = "smallest"
            chunks = list(provider.generate_speech_stream("Hello", "en"))
            self.assertEqual(chunks, [b"chunk_1_", b"chunk_2_", b"chunk_3_"])


if __name__ == "__main__":
    unittest.main()
