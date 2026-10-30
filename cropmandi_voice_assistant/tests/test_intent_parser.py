import unittest
from datetime import date

from cropmandi_voice_assistant.intent_parser import parse_command


class IntentParserTests(unittest.TestCase):
    def test_english_price_query_with_date_and_market(self):
        result = parse_command(
            "What was the coffee price at Chikkamagaluru APMC on 7 August 2026?",
            "en-IN",
            {"client_date": "2026-10-25"},
        )
        self.assertEqual(result["intent"], "price_lookup")
        self.assertEqual(result["entities"]["commodity"], "coffee")
        self.assertEqual(result["entities"]["market"], "Chikkamagaluru APMC")
        self.assertEqual(result["entities"]["arrival_date"], "2026-08-07")

    def test_hindi_price_query(self):
        result = parse_command("कॉफी का भाव चिक्कमगलूरु मंडी में बताइए", "hi-IN", {})
        self.assertEqual(result["intent"], "price_lookup")
        self.assertEqual(result["entities"]["commodity"], "coffee")

    def test_kannada_price_query(self):
        result = parse_command("ಚಿಕ್ಕಮಗಳೂರು ಎಪಿಎಂಸಿಯಲ್ಲಿ ಕಾಫಿ ಬೆಲೆ ಎಷ್ಟು?", "kn-IN", {})
        self.assertEqual(result["intent"], "price_lookup")
        self.assertEqual(result["entities"]["commodity"], "coffee")

    def test_navigation(self):
        result = parse_command("Open the dashboard", "en-IN", {})
        self.assertEqual(result["intent"], "navigate")
        self.assertEqual(result["entities"]["navigation_target"], "dashboard")

    def test_hindi_kal_is_clarified(self):
        result = parse_command("कॉफी का भाव कल हासन मंडी में क्या था", "hi-IN", {})
        self.assertTrue(result["entities"]["date_ambiguous"])


if __name__ == "__main__":
    unittest.main()
