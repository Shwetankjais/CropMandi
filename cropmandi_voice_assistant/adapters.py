"""Adapters that connect the voice assistant to CropMandi CSV price data."""
from __future__ import annotations

import csv
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from .intent_parser import CROPS, DISTRICTS, MARKETS, STATES, normalize_text


def _key(value: Any) -> str:
    value = normalize_text(str(value or ""))
    return re.sub(r"[^\w\u0900-\u097f\u0c80-\u0cff]+", "", value, flags=re.UNICODE)


def _canonical(value: Any, groups: dict[str, tuple[str, ...]]) -> str:
    key = _key(value)
    if not key:
        return ""
    for canonical, aliases in groups.items():
        if key == _key(canonical) or any(key == _key(alias) for alias in aliases):
            return _key(canonical)
    return key


def _date_iso(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw[:19], fmt).date().isoformat()
        except ValueError:
            continue
    try:
        return date.fromisoformat(raw[:10]).isoformat()
    except ValueError:
        return None


def _get(row: dict[str, Any], *keys: str) -> str:
    lookup = {str(k).strip().lower(): v for k, v in row.items()}
    for key in keys:
        val = lookup.get(key.lower())
        if val is not None and str(val).strip() != "":
            return str(val).strip()
    return ""


def make_csv_price_lookup(
    project_root: str | Path | None = None,
    csv_paths: list[str | Path] | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any] | None]:
    """Create a price-lookup callback reading the project's CSV files.

    By default it checks these files relative to ``project_root`` (or the current
    working directory): datasets/india_mandi_data.csv,
    datasets/chikkamagaluru_data.csv, and crop-specific coffee/cardamom/pepper
    CSVs. It never silently substitutes another date or market when the query
    explicitly requests one.
    """
    root = Path(project_root or Path.cwd()).resolve()
    if csv_paths is None:
        candidates = [
            root / "datasets" / "chikkamagaluru_data.csv",
            root / "datasets" / "india_mandi_data.csv",
            root / "datasets" / "coffee_prices.csv",
            root / "datasets" / "cardamom_prices.csv",
            root / "datasets" / "pepper_prices.csv",
        ]
    else:
        candidates = [Path(path) if Path(path).is_absolute() else root / Path(path) for path in csv_paths]

    def lookup(params: dict[str, Any]) -> dict[str, Any] | None:
        commodity = str(params.get("commodity") or params.get("crop") or "").strip().lower()
        query_date = _date_iso(params.get("arrival_date"))
        requested_market = str(params.get("market") or "").strip()
        requested_state = str(params.get("state") or "").strip()
        requested_district = str(params.get("district") or "").strip()

        if not commodity:
            return None

        matches: list[dict[str, Any]] = []
        for path in candidates:
            if not path.exists() or not path.is_file():
                continue
            inferred_crop = path.stem.replace("_prices", "").replace("_data", "").lower()
            try:
                with path.open("r", encoding="utf-8-sig", newline="") as handle:
                    for raw in csv.DictReader(handle):
                        row = {str(k).strip(): (v.strip() if isinstance(v, str) else v) for k, v in raw.items() if k is not None}
                        row_crop = _get(row, "commodity", "crop") or inferred_crop
                        canonical_crop = _canonical(row_crop, CROPS)
                        if canonical_crop != _canonical(commodity, CROPS):
                            continue

                        market_value = _get(row, "market", "mandi", "apmc", "market_name")
                        if requested_market:
                            if not market_value:
                                continue
                            if _canonical(market_value, MARKETS) != _canonical(requested_market, MARKETS):
                                continue

                        state_value = _get(row, "state", "state_name")
                        if requested_state and state_value and _canonical(state_value, STATES) != _canonical(requested_state, STATES):
                            continue
                        district_value = _get(row, "district", "district_name")
                        if requested_district and district_value and _canonical(district_value, DISTRICTS) != _canonical(requested_district, DISTRICTS):
                            continue

                        row_date = _date_iso(_get(row, "arrival_date", "date", "price_date", "reported_date"))
                        if query_date and row_date != query_date:
                            continue
                        if query_date and not row_date:
                            continue

                        price_raw = _get(row, "modal_price", "modalprice", "modal_price_rs", "price_per_qtl", "price", "rate")
                        try:
                            price = float(price_raw.replace(",", ""))
                        except (ValueError, AttributeError):
                            continue
                        if price <= 0:
                            continue

                        min_raw = _get(row, "min_price", "minprice")
                        max_raw = _get(row, "max_price", "maxprice")
                        try:
                            min_price = float(min_raw.replace(",", "")) if min_raw else None
                        except ValueError:
                            min_price = None
                        try:
                            max_price = float(max_raw.replace(",", "")) if max_raw else None
                        except ValueError:
                            max_price = None

                        matches.append({
                            "commodity": commodity,
                            "market": market_value or requested_market,
                            "state": state_value or requested_state,
                            "district": district_value or requested_district,
                            "arrival_date": row_date,
                            "modal_price": price,
                            "current_price": price,
                            "min_price": min_price,
                            "max_price": max_price,
                            "unit": "per quintal",
                            "source_file": path.name,
                        })
            except (OSError, csv.Error, UnicodeDecodeError):
                continue

        if not matches:
            return None
        # For explicit dates, the filter above only returns records for that date.
        # For latest-price queries, use the most recent dated record rather than row order.
        matches.sort(key=lambda item: item.get("arrival_date") or "0000-00-00")
        return matches[-1]

    return lookup
