import unittest
from unittest.mock import patch

from cropmandi_voice_assistant.project_adapter import make_project_price_lookup


class ProjectAdapterTests(unittest.TestCase):
    def setUp(self):
        self.lookup = make_project_price_lookup(session_factory=lambda: None)

    @patch("cropmandi_voice_assistant.project_adapter.prices_payload")
    @patch("cropmandi_voice_assistant.project_adapter.resolve_location", return_value="Chikkamagaluru")
    def test_exact_date_and_selected_series_use_dashboard_market_data(self, _resolve, prices):
        prices.return_value = {
            "commodity": "coffee",
            "location": "Chikkamagaluru",
            "unit": "Rs./50 Kg",
            "official": False,
            "observations": [
                {"date": "2026-08-07", "type": "Arabica Parchment", "price": 25000, "market_centre": "Seller A", "unit": "Rs./50 Kg"},
                {"date": "2026-08-07", "type": "Robusta Parchment", "price": 18000, "market_centre": "Seller B", "unit": "Rs./50 Kg"},
                {"date": "2026-08-08", "type": "Arabica Parchment", "price": 26000, "market_centre": "Seller A", "unit": "Rs./50 Kg"},
            ],
        }
        record = self.lookup({
            "commodity": "coffee", "market": "Chikkamagaluru",
            "variety": "Arabica Parchment", "arrival_date": "2026-08-07",
        })
        self.assertIsNotNone(record)
        self.assertEqual(record["price"], 25000)
        self.assertEqual(record["arrival_date"], "2026-08-07")
        self.assertEqual(record["unit"], "Rs./50 Kg")
        self.assertEqual(record["series"], "Arabica Parchment")

    @patch("cropmandi_voice_assistant.project_adapter.history_response")
    @patch("cropmandi_voice_assistant.project_adapter.resolve_series")
    @patch("cropmandi_voice_assistant.project_adapter.prices_payload")
    @patch("cropmandi_voice_assistant.project_adapter.resolve_location", return_value="Chikkamagaluru")
    def test_known_location_never_falls_back_to_unrelated_series_if_date_missing(
        self, _resolve, prices, resolve_series, history
    ):
        prices.return_value = {
            "observations": [{"date": "2026-08-08", "type": "Arabica Parchment", "price": 26000, "unit": "Rs./50 Kg"}]
        }
        record = self.lookup({
            "commodity": "coffee", "market": "Chikkamagaluru",
            "variety": "Arabica Parchment", "arrival_date": "2026-08-07",
        })
        self.assertIsNone(record)
        resolve_series.assert_not_called()
        history.assert_not_called()

    @patch("cropmandi_voice_assistant.project_adapter.prices_payload")
    @patch("cropmandi_voice_assistant.project_adapter.resolve_location", return_value="Chikkamagaluru")
    def test_ambiguous_market_prices_ask_for_a_variety(self, _resolve, prices):
        prices.return_value = {
            "observations": [
                {"date": "2026-08-07", "type": "Arabica Parchment", "price": 25000},
                {"date": "2026-08-07", "type": "Robusta Parchment", "price": 18000},
            ]
        }
        record = self.lookup({"commodity": "coffee", "market": "Chikkamagaluru", "arrival_date": "2026-08-07"})
        self.assertTrue(record["needs_variety"])
        self.assertEqual(len(record["available_series"]), 2)


if __name__ == "__main__":
    unittest.main()
