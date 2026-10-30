"""Market price ranking endpoint tests."""

from fastapi.testclient import TestClient

import apps.api.main as api_main

client = TestClient(api_main.app)


def test_coffee_rankings_return_top_five_latest_arabica_parchment_centres():
    response = client.get(
        "/api/markets/rankings",
        params={"commodity": "coffee", "series": "ARABICA PARCHMENT"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["commodity"] == "coffee"
    assert body["selected_series"] == "ARABICA PARCHMENT"
    assert body["data_status"] == "UNVERIFIED_LOCAL_DATA"
    assert body["official"] is False
    assert body["unit"] == "Rs./50 Kg"
    assert len(body["rankings"]) == 5
    assert body["count"] == 5
    assert body["total_markets"] >= 5
    prices = [row["price"] for row in body["rankings"]]
    assert prices == sorted(prices, reverse=True)
    assert [row["rank"] for row in body["rankings"]] == [1, 2, 3, 4, 5]
    assert all(row["date"] and row["market_name"] and row["locations"] for row in body["rankings"])
    assert all(row["series"] == "ARABICA PARCHMENT" for row in body["rankings"])


def test_coffee_rankings_keep_ot_qualifiers_separate():
    response = client.get(
        "/api/markets/rankings",
        params={"commodity": "coffee", "series": "ARABICA CHERRY (28 OT)"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["selected_series"] == "ARABICA CHERRY (28 OT)"
    assert body["count"] >= 1
    assert all(row["series"] == "ARABICA CHERRY (28 OT)" for row in body["rankings"])


def test_pepper_rankings_mark_missing_workbook_unit():
    response = client.get(
        "/api/markets/rankings",
        params={"commodity": "pepper", "series": "UnGarbaled"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["commodity"] == "pepper"
    assert body["selected_series"] == "UnGarbaled"
    assert body["data_status"] == "UNVERIFIED_LOCAL_DATA"
    assert body["official"] is False
    assert body["unit"] is None
    assert "does not specify" in body["unit_note"]
    assert body["count"] <= 5
    assert body["count"] >= 1
    prices = [row["price"] for row in body["rankings"]]
    assert prices == sorted(prices, reverse=True)


def test_rice_rankings_report_no_data_without_inventing_markets():
    response = client.get("/api/markets/rankings", params={"commodity": "rice"})
    assert response.status_code == 200
    body = response.json()
    assert body["commodity"] == "rice"
    assert body["data_status"] == "NO_DATA_AVAILABLE"
    assert body["series_options"] == []
    assert body["rankings"] == []
    assert body["count"] == 0


def test_unknown_ranking_series_returns_available_options():
    response = client.get(
        "/api/markets/rankings",
        params={"commodity": "coffee", "series": "not-a-coffee-grade"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "unknown_ranking_series"
    assert body["available_series"]


def test_rice_rankings_use_latest_observation_per_market_not_historical_peak():
    from datetime import date
    from decimal import Decimal

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from apps.api.market_rankings import market_rankings_payload
    from cropmandi.db.models import (
        Base,
        Commodity,
        Grade,
        IngestionRun,
        Market,
        PriceObservation,
        Source,
    )

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        rice = Commodity(code="rice", name="Rice")
        grade = Grade(commodity=rice, code="FAQ", name="FAQ")
        source = Source(
            code="agmarknet-test",
            name="AGMARKNET test source",
            publisher="Government of India",
            classification="official",
        )
        run = IngestionRun(connector="test", status="completed")
        session.add_all([rice, grade, source, run])
        session.flush()

        markets = [
            Market(name="Market A", kind="mandi", district="A district", state="Karnataka"),
            Market(name="Market B", kind="mandi", district="B district", state="Karnataka"),
            Market(name="Market C", kind="mandi", district="C district", state="Karnataka"),
        ]
        session.add_all(markets)
        session.flush()

        observations = [
            # A's old peak must not win: current/latest observation is 110.
            PriceObservation(
                commodity_id=rice.id, market_id=markets[0].id, grade_id=grade.id,
                source_id=source.id, ingestion_run_id=run.id,
                market_date=date(2026, 10, 1), price=Decimal("300"),
                variety="IR_64", unit="INR_PER_QUINTAL", price_type="modal_daily",
            ),
            PriceObservation(
                commodity_id=rice.id, market_id=markets[0].id, grade_id=grade.id,
                source_id=source.id, ingestion_run_id=run.id,
                market_date=date(2026, 10, 10), price=Decimal("110"),
                variety="IR_64", unit="INR_PER_QUINTAL", price_type="modal_daily",
            ),
            PriceObservation(
                commodity_id=rice.id, market_id=markets[1].id, grade_id=grade.id,
                source_id=source.id, ingestion_run_id=run.id,
                market_date=date(2026, 10, 9), price=Decimal("150"),
                variety="IR_64", unit="INR_PER_QUINTAL", price_type="modal_daily",
            ),
            PriceObservation(
                commodity_id=rice.id, market_id=markets[2].id, grade_id=grade.id,
                source_id=source.id, ingestion_run_id=run.id,
                market_date=date(2026, 10, 8), price=Decimal("120"),
                variety="IR_64", unit="INR_PER_QUINTAL", price_type="modal_daily",
            ),
        ]
        session.add_all(observations)
        session.commit()

        initial = market_rankings_payload(session, "rice")
        series_key = initial["series_options"][0]["value"]
        result = market_rankings_payload(session, "rice", series=series_key)

    assert [row["market_name"] for row in result["rankings"]] == [
        "Market B", "Market C", "Market A"
    ]
    assert [row["price"] for row in result["rankings"]] == [150.0, 120.0, 110.0]
    assert result["rankings"][-1]["date"] == "2026-10-10"
    assert result["unit"] == "INR_PER_QUINTAL"
    assert result["official"] is True
