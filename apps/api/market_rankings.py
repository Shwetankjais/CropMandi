"""Price-based market-centre rankings for each supported commodity.

Coffee and Pepper rankings reuse the same mapped local market-centre workbooks
as the dashboard. Rice rankings use ingested AGMARKNET observations. Each
market is represented by its latest available observation for the selected
variety/grade; markets are then ordered by that recorded price (descending).
Observation dates are returned per row because they may differ between markets.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from apps.api.errors import ApiError
from apps.api.market_centres import (
    DATA_STATUS,
    SOURCE_PROVENANCE,
    _mapping_index,
    load_workbook_observations,
    normalize_centre,
)

RANKING_METHOD = (
    "Latest valid observation per market for the selected variety/grade; "
    "markets are sorted by recorded price, highest first. Observation dates may differ."
)
COFFEE_TYPE_ORDER = (
    "ARABICA PARCHMENT",
    "ARABICA CHERRY",
    "ROBUSTA PARCHMENT",
    "ROBUSTA CHERRY",
)


def _normalise(value: str | None) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).casefold()


def _freshness_fields(observed_on: date) -> dict[str, Any]:
    age_days = max((date.today() - observed_on).days, 0)
    return {
        "age_days": age_days,
        "freshness_status": "HISTORICAL" if age_days > 30 else "RECENT",
    }


def _series_label(value: str) -> str:
    """Readable label while retaining source qualifiers such as 28 OT / EP."""
    label = " ".join(value.split()).title()
    for source, target in ((" Ot", " OT"), (" Ep", " EP"), (" Rs", " Rs")):
        label = label.replace(source, target)
    return label


def _workbook_series_sort_key(commodity: str, value: str) -> tuple[int, str]:
    if commodity == "coffee":
        upper = value.upper()
        for index, base in enumerate(COFFEE_TYPE_ORDER):
            if upper == base or upper.startswith(base + " "):
                return index, upper
        return len(COFFEE_TYPE_ORDER), upper
    return 0, value.casefold()


def _rank_workbook_markets(
    commodity: str,
    series: str | None,
    limit: int,
) -> dict[str, Any]:
    observations = load_workbook_observations(commodity)
    mappings = _mapping_index(commodity)

    # Keep only centres that the current dashboard can map to a real location.
    valid_rows: list[dict[str, Any]] = []
    for row in observations:
        market_date = row.get("observation_date")
        price = row.get("price")
        centre = str(row.get("raw_market_centre") or "").strip()
        type_name = str(row.get("type") or "").strip()
        if not centre or not type_name or not isinstance(market_date, date):
            continue
        if not isinstance(price, (int, float)) or price <= 0:
            continue
        centre_key = normalize_centre(centre)
        centre_mappings = mappings.get(centre_key, [])
        if not centre_mappings:
            continue
        valid_rows.append(
            {
                "market_name": centre,
                "market_kind": "market_centre",
                "locations": sorted({m.canonical_location for m in centre_mappings}),
                "series": type_name,
                "price": float(price),
                "unit": "Rs./50 Kg" if commodity == "coffee" else None,
                "date": market_date.isoformat(),
                **_freshness_fields(market_date),
                "source": "coffee_market_price.xlsx" if commodity == "coffee" else "pepper_market_price.xlsx",
                "official": False,
                "data_status": DATA_STATUS,
            }
        )

    series_names = sorted(
        {row["series"] for row in valid_rows},
        key=lambda value: _workbook_series_sort_key(commodity, value),
    )
    options = [{"value": name, "label": _series_label(name)} for name in series_names]
    if not series_names:
        return {
            "commodity": commodity,
            "selected_series": None,
            "series_options": [],
            "rankings": [],
            "count": 0,
            "total_markets": 0,
            "as_of": None,
            "unit": "Rs./50 Kg" if commodity == "coffee" else None,
            "unit_note": (
                "The Pepper source workbook does not specify the price quantity unit."
                if commodity == "pepper"
                else None
            ),
            "source": "coffee_market_price.xlsx" if commodity == "coffee" else "pepper_market_price.xlsx",
            "provenance": SOURCE_PROVENANCE,
            "data_status": "NO_DATA_AVAILABLE",
            "official": False,
            "ranking_method": RANKING_METHOD,
        }

    selected_series = series or series_names[0]
    series_lookup = {_normalise(name): name for name in series_names}
    canonical_series = series_lookup.get(_normalise(selected_series))
    if canonical_series is None:
        raise ApiError(
            400,
            "unknown_ranking_series",
            f"The selected {commodity} variety/grade is not available for ranking.",
            {"available_series": options},
        )

    # Latest observation per market centre. For duplicate rows on the same day,
    # retain the higher recorded price rather than letting file order decide.
    latest_by_market: dict[str, dict[str, Any]] = {}
    for row in valid_rows:
        if row["series"] != canonical_series:
            continue
        key = row["market_name"].casefold()
        previous = latest_by_market.get(key)
        candidate_key = (row["date"], row["price"])
        previous_key = (previous["date"], previous["price"]) if previous else None
        if previous is None or candidate_key > previous_key:
            latest_by_market[key] = row

    all_rankings = sorted(
        latest_by_market.values(),
        key=lambda row: (-row["price"], -date.fromisoformat(row["date"]).toordinal(), row["market_name"].casefold()),
    )
    rankings = [dict(row, rank=index + 1) for index, row in enumerate(all_rankings[:limit])]
    latest_date = max((row["date"] for row in all_rankings), default=None)
    return {
        "commodity": commodity,
        "selected_series": canonical_series,
        "series_options": options,
        "rankings": rankings,
        "count": len(rankings),
        "total_markets": len(all_rankings),
        "limit": limit,
        "as_of": latest_date,
        "unit": "Rs./50 Kg" if commodity == "coffee" else None,
        "unit_note": (
            "The Pepper source workbook does not specify the price quantity unit; values are shown as recorded."
            if commodity == "pepper"
            else None
        ),
        "source": "coffee_market_price.xlsx" if commodity == "coffee" else "pepper_market_price.xlsx",
        "provenance": SOURCE_PROVENANCE,
        "data_status": DATA_STATUS,
        "official": False,
        "ranking_method": RANKING_METHOD,
    }


def _rice_series_key(variety: str | None, grade: str, unit: str, price_type: str, source_code: str) -> str:
    return json.dumps(
        [variety or "General", grade or "UNSPECIFIED", unit, price_type, source_code],
        ensure_ascii=True,
        separators=(",", ":"),
    )


def _rank_rice_markets(session: Session, series: str | None, limit: int) -> dict[str, Any]:
    from cropmandi.db.models import Commodity, Grade, Market, PriceObservation, Source

    commodity = session.query(Commodity).filter_by(code="rice").one_or_none()
    rows = []
    if commodity is not None:
        rows = (
            session.query(PriceObservation, Market, Grade, Source)
            .join(Market, PriceObservation.market_id == Market.id)
            .join(Grade, PriceObservation.grade_id == Grade.id)
            .join(Source, PriceObservation.source_id == Source.id)
            .filter(PriceObservation.commodity_id == commodity.id)
            .order_by(PriceObservation.market_date.asc(), PriceObservation.id.asc())
            .all()
        )

    groups: dict[str, dict[str, Any]] = {}
    latest_by_series_market: dict[tuple[str, int], dict[str, Any]] = {}
    for observation, market, grade, source in rows:
        key = _rice_series_key(
            observation.variety,
            grade.code,
            observation.unit,
            observation.price_type,
            source.code,
        )
        variety_name = (observation.variety or "General").replace("_", "-")
        grade_name = grade.code or "UNSPECIFIED"
        # Include every field that separates a ranking series so similarly
        # named entries from different sources/units/price types are explicit.
        price_type_label = observation.price_type.replace("_", " ").title()
        label = (
            f"{variety_name} · {grade_name} · {price_type_label} · "
            f"{observation.unit.replace('_', ' ').lower()} · {source.name}"
        )
        groups[key] = {
            "value": key,
            "label": label,
            "source": source.name,
            "unit": observation.unit,
        }
        candidate = {
            "market_name": market.name,
            "market_kind": market.kind or "mandi",
            "locations": [value for value in (market.district, market.state) if value],
            "price": float(observation.price),
            "unit": observation.unit,
            "date": observation.market_date.isoformat(),
            **_freshness_fields(observation.market_date),
            "source": source.name,
            "official": True,
            "data_status": "AGMARKNET_INGESTED",
            "price_type": observation.price_type,
        }
        market_key = (key, market.id)
        previous = latest_by_series_market.get(market_key)
        if previous is None or (candidate["date"], observation.id) > (
            previous["date"], previous["observation_id"]
        ):
            candidate["observation_id"] = observation.id
            latest_by_series_market[market_key] = candidate

    options = sorted(groups.values(), key=lambda item: (item["label"].casefold(), item["source"].casefold()))
    if not options:
        return {
            "commodity": "rice",
            "selected_series": None,
            "series_options": [],
            "rankings": [],
            "count": 0,
            "total_markets": 0,
            "as_of": None,
            "unit": None,
            "unit_note": None,
            "source": "AGMARKNET / data.gov.in",
            "provenance": "AGMARKNET / data.gov.in",
            "data_status": "NO_DATA_AVAILABLE",
            "official": False,
            "ranking_method": RANKING_METHOD,
        }

    selected_series = series or options[0]["value"]
    if selected_series not in groups:
        raise ApiError(
            400,
            "unknown_ranking_series",
            "The selected Rice variety/grade is not available for ranking.",
            {"available_series": options},
        )

    candidates = [
        row
        for (series_key, _market_id), row in latest_by_series_market.items()
        if series_key == selected_series
    ]
    candidates.sort(
        key=lambda row: (-row["price"], -date.fromisoformat(row["date"]).toordinal(), row["market_name"].casefold())
    )
    rankings = []
    for index, row in enumerate(candidates[:limit]):
        clean_row = {key: value for key, value in row.items() if key != "observation_id"}
        rankings.append(dict(clean_row, rank=index + 1))
    selected = groups[selected_series]
    return {
        "commodity": "rice",
        "selected_series": selected_series,
        "series_options": options,
        "rankings": rankings,
        "count": len(rankings),
        "total_markets": len(candidates),
        "limit": limit,
        "as_of": max((row["date"] for row in candidates), default=None),
        "unit": selected["unit"],
        "unit_note": None,
        "source": selected["source"],
        "provenance": "AGMARKNET / data.gov.in",
        "data_status": "AGMARKNET_INGESTED",
        "official": True,
        "ranking_method": RANKING_METHOD,
    }


def market_rankings_payload(
    session: Session,
    commodity: str,
    series: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Return the top ``limit`` latest-price markets for one crop series."""
    if commodity in {"coffee", "pepper"}:
        return _rank_workbook_markets(commodity, series, limit)
    if commodity == "rice":
        return _rank_rice_markets(session, series, limit)
    raise ApiError(404, "unknown_commodity", f"No market ranking provider for '{commodity}'.")
