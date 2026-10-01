import unittest
import asyncio
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from llm.llm import (
    CombinedResponseAnalysis,
    IntentAnalysis,
    ExtractedEntities,
    _parse_combined_response_payload,
    _build_safe_fallback_combined_response,
    generate_combined_intent_and_response,
)


class TestCombinedResponseAnalysis(unittest.TestCase):
    def test_valid_json_payload_parsing(self):
        raw = '{"intent_analysis": {"intent": "QUALIFICATION", "confidence_score": 0.9}, "spoken_reply_text": "How can I assist you with your property search?"}'
        parsed = _parse_combined_response_payload(raw, domain="real_estate")
        self.assertIsNotNone(parsed)
        self.assertIsInstance(parsed, CombinedResponseAnalysis)
        self.assertEqual(parsed.intent_analysis.intent, "QUALIFICATION")
        self.assertEqual(parsed.spoken_reply_text, "How can I assist you with your property search?")

    def test_plain_text_payload_parsing(self):
        raw = "I would be glad to help you find apartments in Wakad."
        parsed = _parse_combined_response_payload(raw, domain="real_estate")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.intent_analysis.intent, "DISCOVERY")
        self.assertEqual(parsed.spoken_reply_text, "I would be glad to help you find apartments in Wakad.")

    def test_empty_json_dict_does_not_throw_validation_error(self):
        raw = "{}"
        parsed = _parse_combined_response_payload(raw, domain="real_estate")
        self.assertIsNone(parsed)

    def test_empty_string_does_not_throw_validation_error(self):
        parsed = _parse_combined_response_payload("", domain="real_estate")
        self.assertIsNone(parsed)

    def test_safe_fallback_generator(self):
        fallback = _build_safe_fallback_combined_response(domain="real_estate", user_input="Okay. And")
        self.assertIsNotNone(fallback)
        self.assertIsInstance(fallback, CombinedResponseAnalysis)
        self.assertIsInstance(fallback.intent_analysis, IntentAnalysis)
        self.assertEqual(fallback.intent_analysis.intent, "DISCOVERY")
        self.assertTrue(len(fallback.spoken_reply_text) > 0)

    def test_async_combined_generation_handles_empty_model_response(self):
        async def run_test():
            # Test when input causes short/empty/unclear model output
            res = await generate_combined_intent_and_response(
                user_input="Okay. And",
                history=[{"role": "user", "content": "Okay. And"}],
                domain="real_estate"
            )
            self.assertIsNotNone(res)
            self.assertIsInstance(res, CombinedResponseAnalysis)
            self.assertTrue(len(res.spoken_reply_text) > 0)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
