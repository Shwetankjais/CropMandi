import csv
import tempfile
import unittest
from pathlib import Path

from cropmandi_voice_assistant import make_csv_price_lookup


class CsvAdapterTests(unittest.TestCase):
    def test_exact_market_and_date_lookup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dataset_dir = root / "datasets"
            dataset_dir.mkdir()
            path = dataset_dir / "india_mandi_data.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    "state", "district", "market", "commodity", "arrival_date",
                    "min_price", "max_price", "modal_price"
                ])
                writer.writeheader()
                writer.writerow({
                    "state": "Karnataka", "district": "Chikkamagaluru",
                    "market": "Chikkamagaluru APMC", "commodity": "Coffee",
                    "arrival_date": "2026-08-07", "min_price": "28000",
                    "max_price": "32000", "modal_price": "30000"
                })
                writer.writerow({
                    "state": "Karnataka", "district": "Chikkamagaluru",
                    "market": "Chikkamagaluru APMC", "commodity": "Coffee",
                    "arrival_date": "2026-08-08", "min_price": "29000",
                    "max_price": "33000", "modal_price": "31000"
                })

            lookup = make_csv_price_lookup(project_root=root, csv_paths=["datasets/india_mandi_data.csv"])
            exact = lookup({
                "commodity": "coffee", "state": "Karnataka", "district": "Chikkamagaluru",
                "market": "Chikkamagaluru APMC", "arrival_date": "2026-08-07"
            })
            latest = lookup({
                "commodity": "coffee", "state": "Karnataka", "district": "Chikkamagaluru",
                "market": "Chikkamagaluru APMC", "arrival_date": None
            })
            missing = lookup({
                "commodity": "coffee", "state": "Karnataka", "district": "Chikkamagaluru",
                "market": "Chikkamagaluru APMC", "arrival_date": "2026-08-09"
            })
            self.assertEqual(exact["modal_price"], 30000.0)
            self.assertEqual(exact["arrival_date"], "2026-08-07")
            self.assertEqual(latest["modal_price"], 31000.0)
            self.assertIsNone(missing)


if __name__ == "__main__":
    unittest.main()
