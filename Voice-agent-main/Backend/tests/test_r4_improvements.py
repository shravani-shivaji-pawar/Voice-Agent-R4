"""
test_r4_improvements.py — Verification suite for Voice-Agent-R4 improvements.
"""

import os
import sys
import unittest
import asyncio

# Ensure backend dir is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from stt import config as stt_cfg
from stt.stt_smallest import _get_session
from llm.language_utils import LanguageTracker, _detect_explicit_language_request
from llm.llm import _quick_is_company_question, _generate_answer_from_chunks


class TestR4VoiceImprovements(unittest.TestCase):

    def test_stt_vad_config_defaults(self):
        self.assertEqual(stt_cfg.TRAILING_SILENCE_MS, 400)
        self.assertEqual(stt_cfg.MAX_CHUNK_MS, 12000)

    def test_smallest_stt_session_reuse(self):
        session1 = _get_session()
        session2 = _get_session()
        self.assertIs(session1, session2, "Session should be reused across requests")

    def test_fast_company_question_classifier(self):
        company_queries = [
            "What does this company do?",
            "Who is your CEO?",
            "Tell me about Suncity Apartments",
            "Where is your office located?",
        ]
        normal_queries = [
            "My budget is 30 lakhs",
            "I want a 2 BHK in Jaipur",
            "Yes I am interested",
        ]
        for q in company_queries:
            self.assertTrue(_quick_is_company_question(q), f"Failed to classify company question: {q}")
        for q in normal_queries:
            self.assertFalse(_quick_is_company_question(q), f"False positive classification: {q}")

    def test_language_lock_and_explicit_requests(self):
        self.assertEqual(_detect_explicit_language_request("Please speak in Hindi"), "hi")
        self.assertEqual(_detect_explicit_language_request("Talk in English please"), "en")
        self.assertEqual(_detect_explicit_language_request("marathi me baat karo"), "mr")
        self.assertIsNone(_detect_explicit_language_request("Jaipur and budget is 30 lakhs"))

    def test_summary_grounding_fallback(self):
        async def run_test():
            chunks = [
                "## Overview\nSuncity Apartments offers 1BHK, 2BHK, and 3BHK flats in Jaipur, Jodhpur, and Madurai."
            ]
            ans = await _generate_answer_from_chunks(
                user_text="Who is your CEO?",
                retrieved_chunks=chunks,
                language="en"
            )
            self.assertTrue("don't have that detail" in ans.lower().replace("’", "'") or "dont have that detail" in ans.lower())
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
