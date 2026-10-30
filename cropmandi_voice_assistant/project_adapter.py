"""Adapters that connect voice commands to the existing CropMandi API data.

The integrated app reads the same market-centre workbook/DB-backed data as the
dashboard. It never falls back from a known location to unrelated price-series
data when that location has no observation for the requested date.
"""
from __future__ import annotations

import re
from statistics import median
from typing import Any, Callable

from apps.api.catalog import resolve_series
from apps.api.market_centres import prices_payload, resolve_location
from apps.api.services import history_response

SessionFactory = Callable[[], Any]
SUPPORTED_COMMODITIES = {"coffee", "pepper", "rice"}
SERIES_BY_COMMODITY = {
    "coffee": {"arabica parchment", "arabica cherry", "robusta parchment", "robusta cherry"},
    "pepper": {"cochin garbled", "cochin ungarbled", "sirsi"},
}

def _norm(value: Any) -> str:
    text = str(value or "").casefold().replace("_", " ").replace("-", " ")
    text = re.sub(r"\b(?:apmc|mandi|market yard|market|agricultural produce market committee)\b", " ", text)
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())



def _series_belongs_to_commodity(series: str | None, commodity: str) -> bool:
    wanted = _norm(series)
    if not wanted:
        return False
    for other_commodity, names in SERIES_BY_COMMODITY.items():
        if other_commodity == commodity:
            continue
        if wanted in {_norm(name) for name in names}:
            return False
    return True

def _location_candidates(value: Any) -> list[str]:
    original = str(value or "").strip()
    if not original:
        return []
    without_suffix = re.sub(
        r"\b(?:APMC|mandi|market yard|market|agricultural produce market committee)\b",
        " ", original, flags=re.IGNORECASE,
    )
    without_suffix = " ".join(without_suffix.split()).strip(" ,.-")
    candidates = [original]
    if without_suffix and without_suffix.casefold() != original.casefold():
        candidates.append(without_suffix)
    return candidates

def _resolve_project_location(commodity: str, value: Any) -> str | None:
    for candidate in _location_candidates(value):
        try:
            return resolve_location(commodity, candidate)
        except Exception:
            continue
    return None

def _date_for(row: dict[str, Any]) -> str:
    value = row.get("date") or row.get("arrival_date") or row.get("observation_date") or ""
    return str(value)[:10]

def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("₹", "").strip()
        number = float(value)
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None

def _row_series(row: dict[str, Any]) -> str:
    for key in ("type", "series", "variety", "grade", "grade_code"):
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""

def _matches_series(row: dict[str, Any], requested: str) -> bool:
    wanted = _norm(requested)
    if not wanted:
        return True
    fields = [row.get(k) for k in ("type", "series", "variety", "grade", "grade_code")]
    for value in fields:
        actual = _norm(value)
        if actual and (actual == wanted or actual.startswith(wanted + " ") or wanted.startswith(actual + " ")):
            return True
    return False

def _from_market_centres(
    commodity: str,
    location: str,
    requested_date: str | None,
    requested_series: str | None,
) -> dict[str, Any] | None:
    payload = prices_payload(commodity, location)
    rows = [row for row in payload.get("observations", []) if _number(row.get("price")) is not None and _date_for(row)]
    if requested_date:
        rows = [row for row in rows if _date_for(row) == requested_date]
    if requested_series:
        rows = [row for row in rows if _matches_series(row, requested_series)]
    if not rows:
        return None

    # A no-date request means the newest recorded date, not a forecast.
    latest_date = max(_date_for(row) for row in rows)
    rows = [row for row in rows if _date_for(row) == latest_date]

    series_names = sorted({ _row_series(row) for row in rows if _row_series(row) }, key=str.casefold)
    if not requested_series and len(series_names) > 1:
        return {"needs_variety": True, "market": location, "commodity": commodity, "available_series": series_names}

    # Multiple vendor/centre entries for the same date and series are summarized
    # by their median, not by arbitrarily selecting one row.
    values = [_number(row.get("price")) for row in rows]
    values = [value for value in values if value is not None]
    if not values:
        return None
    chosen = sorted(rows, key=lambda row: str(row.get("market_centre") or row.get("source") or "").casefold())[0]
    unit = chosen.get("unit") or payload.get("unit") or "unit not specified by source data"
    market_centres = sorted({str(row.get("market_centre") or row.get("source") or "").strip() for row in rows if row.get("market_centre") or row.get("source")})
    return {
        "commodity": commodity,
        "market": location,
        "market_centre": market_centres[0] if len(market_centres) == 1 else None,
        "market_centres": market_centres,
        "series": _row_series(chosen) or (series_names[0] if series_names else None),
        "arrival_date": latest_date,
        "price": median(values),
        "unit": unit,
        "record_count": len(values),
        "price_method": "median_of_matching_records" if len(values) > 1 else "recorded_observation",
        "source": chosen.get("source") or payload.get("source_workbook"),
        "official": chosen.get("official", payload.get("official", False)),
        "data_status": chosen.get("data_status") or payload.get("data_status"),
        "data_usage": payload.get("data_usage"),
    }

def _from_price_series(
    commodity: str,
    selector: str,
    requested_date: str | None,
    session_factory: SessionFactory,
) -> dict[str, Any] | None:
    if not selector:
        return None
    session = session_factory()
    try:
        spec = resolve_series(commodity, selector, session=session)
        if spec is None:
            return None
        result = history_response(
            session, commodity, spec.display_name,
            requested_date, requested_date,
        ) if requested_date else history_response(session, commodity, spec.display_name, None, None)
        observations = result.get("observations", [])
        if not observations:
            return None
        point = max(observations, key=lambda row: str(row.get("observation_date", "")))
        return {
            "commodity": commodity,
            "market": spec.display_name,
            "series": spec.display_name,
            "arrival_date": point.get("observation_date"),
            "price": point.get("price"),
            "unit": point.get("unit") or result.get("unit") or "unit not specified by source data",
            "source": result.get("provenance"),
            "official": result.get("official", False),
            "data_status": result.get("data_status"),
            "data_usage": result.get("data_usage"),
        }
    except Exception:
        # A missing series/date is a normal no-result, not a server error.
        return None
    finally:
        session.close()

def make_project_price_lookup(session_factory: SessionFactory):
    """Build the callback expected by ``create_voice_router``.

    It uses the dashboard's location + selected variety whenever possible. When
    the user says a known price-series name instead of a geographic location, it
    can query the project's existing `/api/prices/history` data path directly.
    """
    def lookup(params: dict[str, Any]) -> dict[str, Any] | None:
        commodity = str(params.get("commodity") or "").strip().lower()
        if commodity not in SUPPORTED_COMMODITIES:
            return None
        market_text = params.get("market") or params.get("district") or params.get("location")
        requested_date = str(params.get("arrival_date") or "").strip() or None
        spoken_series = str(params.get("spoken_series") or "").strip() or None
        requested_series = str(params.get("variety") or params.get("series") or "").strip() or None
        if spoken_series and not _series_belongs_to_commodity(spoken_series, commodity):
            spoken_series = None
        if requested_series and not _series_belongs_to_commodity(requested_series, commodity):
            requested_series = None

        # If the utterance explicitly names a known backend series as its selector,
        # treat it as a series query rather than confusing it with a location of
        # the same name (notably Pepper's Sirsi series).
        if spoken_series and _norm(spoken_series) == _norm(market_text):
            record = _from_price_series(commodity, spoken_series, requested_date, session_factory)
            if record:
                return record

        canonical = _resolve_project_location(commodity, market_text)
        if canonical:
            try:
                return _from_market_centres(commodity, canonical, requested_date, requested_series)
            except Exception:
                # Do not answer with a different source if a recognized location
                # did not contain the requested record.
                return None

        # There was no known location match. Here the market text itself may be
        # a named series such as "Arabica Parchment" or "Cochin Garbled".
        selector_candidates = [spoken_series, requested_series, str(market_text or "").strip()]
        seen = set()
        for selector in selector_candidates:
            if not selector or _norm(selector) in seen:
                continue
            seen.add(_norm(selector))
            record = _from_price_series(commodity, selector, requested_date, session_factory)
            if record:
                return record
        return None

    return lookup
