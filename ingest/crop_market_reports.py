"""Parse AGMARKNET date-wise Excel-export HTML reports into a clean CSV.

The supplied .xls files are HTML-table exports rather than BIFF workbooks.
This parser reads their table structure, carries forward merged market/district
labels, excludes market subtotals, validates numeric values, and deduplicates
repeated report rows while preserving source filenames.
"""
from __future__ import annotations

import csv
import json
import re
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from lxml import html

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ZIP = ROOT / "data/raw/agmarknet_vegetable_reports.zip"
DEFAULT_CSV = ROOT / "data/processed/crop_market_observations.csv"
DEFAULT_REPORT = ROOT / "data/reports/crop_market_data_quality.json"

CROP_FOLDERS = {"maize": "MAIZE", "paddy": "Paddy", "potato": "Potato", "tomato": "Tomato"}
COLUMNS = [
    "crop", "market_name", "district", "state", "market_date", "variety", "grade",
    "arrivals", "unit", "min_price", "max_price", "modal_price", "source_file",
    "source_publisher", "data_status",
]


def _number(value: str) -> float | None:
    value = (value or "").strip().replace(",", "")
    if not value or value in {"-", "NA", "N/A", "na", "null"}:
        return None
    return float(value)


def _date(value: str):
    value = (value or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def parse_archive(zip_path: Path = DEFAULT_ZIP) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    audit: dict[str, Any] = {
        "source_archive": str(zip_path.name),
        "parser_note": "The supplied .xls files are HTML tables, not binary Excel BIFF files.",
        "crops": {},
        "total_rows_imported": 0,
    }
    with zipfile.ZipFile(zip_path) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(".xls")]
        for crop, folder in CROP_FOLDERS.items():
            files = [n for n in names if f"/{folder.lower()}/" in n.lower()]
            stats = Counter()
            crop_rows: list[dict[str, Any]] = []
            for file_name in sorted(files):
                try:
                    root = html.fromstring(archive.read(file_name).decode("utf-8-sig", errors="replace"))
                except Exception:
                    stats["parse_error_files"] += 1
                    continue
                tables = root.xpath("//table")
                if not tables:
                    stats["files_without_table"] += 1
                    continue
                current_market = ""
                current_district = ""
                for tr in tables[0].xpath(".//tr"):
                    cells = [" ".join((cell.text_content() or "").replace("\xa0", " ").split()) for cell in tr.xpath("./th|./td")]
                    if not cells or (cells and cells[0].strip().casefold() == "market"):
                        continue
                    cells += [""] * max(0, 10 - len(cells))
                    market, date_text, variety, grade, arrivals, unit, min_p, max_p, modal, district = [x.strip() for x in cells[:10]]
                    if market.casefold() in {"total", "market total"}:
                        stats["subtotal_rows_excluded"] += 1
                        continue
                    if market:
                        current_market = market
                    if district:
                        current_district = district
                    if (variety or "").casefold() == "avg of modal price":
                        stats["summary_average_rows_excluded"] += 1
                        continue
                    observed = _date(date_text)
                    if observed is None:
                        stats["invalid_or_missing_dates"] += 1
                        continue
                    if not current_market:
                        stats["missing_market_heading"] += 1
                        continue
                    try:
                        arrival_value = _number(arrivals)
                        min_value = _number(min_p)
                        max_value = _number(max_p)
                        modal_value = _number(modal)
                    except ValueError:
                        stats["non_numeric_rows"] += 1
                        continue
                    if arrival_value is None or arrival_value < 0 or modal_value is None or modal_value <= 0:
                        stats["invalid_arrival_or_modal_price"] += 1
                        continue
                    if min_value is not None and min_value <= 0:
                        min_value = None
                    if max_value is not None and max_value <= 0:
                        max_value = None
                    if min_value is not None and max_value is not None and min_value > max_value:
                        stats["invalid_min_max_range"] += 1
                        continue
                    unit_value = unit or "Quintal"
                    row = {
                        "crop": crop,
                        "market_name": current_market.strip(),
                        "district": current_district.strip(),
                        "state": "Karnataka",
                        "market_date": observed.isoformat(),
                        "variety": variety or "UNSPECIFIED",
                        "grade": grade or "UNSPECIFIED",
                        "arrivals": round(arrival_value, 4),
                        "unit": unit_value,
                        "min_price": round(min_value, 4) if min_value is not None else "",
                        "max_price": round(max_value, 4) if max_value is not None else "",
                        "modal_price": round(modal_value, 4),
                        "source_file": file_name,
                        "source_publisher": "AGMARKNET date-wise report export (user-supplied)",
                        "data_status": "USER_SUPPLIED_AGMARKNET_EXPORT_UNVERIFIED",
                    }
                    key = (
                        crop, row["market_name"].casefold(), row["district"].casefold(),
                        row["market_date"], row["variety"].casefold(), row["grade"].casefold(), row["unit"].casefold(),
                    )
                    existing = rows_by_key.get(key)
                    if existing:
                        stats["duplicate_series_rows"] += 1
                        # Retain the more complete row; preserve a conflict marker if prices differ.
                        if float(row["modal_price"]) != float(existing["modal_price"]):
                            stats["duplicate_price_conflicts"] += 1
                            existing["data_status"] = "DUPLICATE_CONFLICT_REQUIRES_REVIEW"
                        if (row["min_price"] != "" and existing["min_price"] == "") or (row["max_price"] != "" and existing["max_price"] == ""):
                            existing["min_price"] = row["min_price"] or existing["min_price"]
                            existing["max_price"] = row["max_price"] or existing["max_price"]
                    else:
                        rows_by_key[key] = row
                    crop_rows.append(row)
                    stats["valid_rows_seen"] += 1
            unique_crop_rows = [r for r in rows_by_key.values() if r["crop"] == crop]
            unique_crop_rows.sort(key=lambda r: (r["market_name"].casefold(), r["variety"].casefold(), r["grade"].casefold(), r["market_date"]))
            audit["crops"][crop] = {
                "source_files": len(files),
                "unique_observations": len(unique_crop_rows),
                "markets": len({r["market_name"] for r in unique_crop_rows}),
                "districts": len({r["district"] for r in unique_crop_rows if r["district"]}),
                "varieties": len({r["variety"] for r in unique_crop_rows}),
                "grades": len({r["grade"] for r in unique_crop_rows}),
                "date_min": min((r["market_date"] for r in unique_crop_rows), default=None),
                "date_max": max((r["market_date"] for r in unique_crop_rows), default=None),
                "quality_counts": dict(stats),
            }
    rows = list(rows_by_key.values())
    rows.sort(key=lambda r: (r["crop"], r["market_date"], r["market_name"].casefold(), r["variety"].casefold(), r["grade"].casefold()))
    audit["total_rows_imported"] = len(rows)
    audit["total_market_names"] = len({(r["market_name"], r["district"]) for r in rows})
    audit["date_min"] = min((r["market_date"] for r in rows), default=None)
    audit["date_max"] = max((r["market_date"] for r in rows), default=None)
    return rows, audit


def write_clean_csv(rows: list[dict[str, Any]], output_csv: Path = DEFAULT_CSV) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows, audit = parse_archive()
    write_clean_csv(rows)
    DEFAULT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_REPORT.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps({"csv": str(DEFAULT_CSV), "report": str(DEFAULT_REPORT), "audit": audit}, indent=2))


if __name__ == "__main__":
    main()
