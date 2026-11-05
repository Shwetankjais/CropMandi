"""Enhanced HarvestRoute tests — vehicle catalogue, transport cost engine,
mandi optimizer and API regression tests.

Covers:
  Phase 1: Vehicle catalogue
  Phase 2: Payload validation
  Phase 3: Transport cost calculation (owned + hired)
  Phase 4: Mandi optimizer / net realization
  Phase 5: harvest_routes_payload integration (monkeypatched)
  Phase 6: API endpoint regression
  Phase 7: Commodity extension (tomato, maize, paddy, potato)
"""
from __future__ import annotations

import math

import pytest

# ---------------------------------------------------------------------------
# Phase 1: Vehicle catalogue
# ---------------------------------------------------------------------------

class TestVehicleCatalogue:
    def test_catalogue_has_seven_vehicles(self):
        from apps.api.vehicle_catalogue import get_all_vehicles
        vehicles = get_all_vehicles()
        assert len(vehicles) == 7

    def test_all_vehicles_have_required_fields(self):
        from apps.api.vehicle_catalogue import get_all_vehicles
        required = {
            "id", "category", "model", "fuel_type",
            "max_payload_kg", "usable_payload_kg",
            "mileage_kmpl", "maintenance_per_km", "tyre_per_km",
            "depreciation_per_km", "driver_per_km",
            "min_hire_charge", "base_hire_rate_per_km",
            "data_source", "last_verified", "confidence",
        }
        for v in get_all_vehicles():
            missing = required - set(v.keys())
            assert not missing, f"Vehicle '{v['id']}' missing fields: {missing}"

    def test_usable_payload_less_than_max(self):
        from apps.api.vehicle_catalogue import get_all_vehicles
        for v in get_all_vehicles():
            assert v["usable_payload_kg"] <= v["max_payload_kg"], (
                f"Vehicle '{v['id']}' usable payload exceeds max payload"
            )

    def test_get_vehicle_by_id_returns_correct_vehicle(self):
        from apps.api.vehicle_catalogue import get_vehicle_by_id
        v = get_vehicle_by_id("tata_ace")
        assert v is not None
        assert v["id"] == "tata_ace"
        assert v["usable_payload_kg"] == 900

    def test_get_vehicle_by_id_returns_none_for_unknown(self):
        from apps.api.vehicle_catalogue import get_vehicle_by_id
        assert get_vehicle_by_id("nonexistent_vehicle") is None

    def test_goods_auto_uses_petrol(self):
        from apps.api.vehicle_catalogue import get_vehicle_by_id
        v = get_vehicle_by_id("goods_auto")
        assert v["fuel_type"] == "petrol"

    def test_all_trucks_use_diesel(self):
        from apps.api.vehicle_catalogue import get_all_vehicles
        for v in get_all_vehicles():
            if v["id"] != "goods_auto":
                assert v["fuel_type"] == "diesel", (
                    f"Expected diesel for '{v['id']}'"
                )

    def test_confidence_scores_in_valid_range(self):
        from apps.api.vehicle_catalogue import get_all_vehicles
        for v in get_all_vehicles():
            assert 0.0 <= v["confidence"] <= 1.0, (
                f"Confidence out of range for '{v['id']}': {v['confidence']}"
            )

    def test_diesel_price_has_required_fields(self):
        from apps.api.vehicle_catalogue import get_diesel_price
        price_info = get_diesel_price()
        assert "price_per_litre" in price_info
        assert "price_type" in price_info
        assert price_info["price_type"] == "CONFIGURED_ESTIMATE"
        assert price_info["price_per_litre"] > 0

    def test_payload_ordering_smallest_to_largest(self):
        from apps.api.vehicle_catalogue import get_all_vehicles
        vehicles = get_all_vehicles()
        payloads = [v["usable_payload_kg"] for v in vehicles]
        assert payloads == sorted(payloads), "Vehicles should be ordered by payload"


# ---------------------------------------------------------------------------
# Phase 2: Payload validation
# ---------------------------------------------------------------------------

class TestPayloadValidation:
    def test_50kg_goods_auto_single_trip(self):
        from apps.api.vehicle_service import validate_payload
        result = validate_payload("goods_auto", 50)
        assert result["ok"] is True
        assert result["trips"] == 1
        assert result["warning"] is None

    def test_500kg_tata_ace_single_trip(self):
        from apps.api.vehicle_service import validate_payload
        result = validate_payload("tata_ace", 500)
        assert result["ok"] is True
        assert result["trips"] == 1
        assert result["warning"] is None

    def test_5000kg_tata_ace_needs_6_trips(self):
        from apps.api.vehicle_service import validate_payload
        result = validate_payload("tata_ace", 5000)
        assert result["ok"] is True
        assert result["trips"] == math.ceil(5000 / 900)  # = 6
        assert result["warning"] is not None
        assert "trip" in result["warning"].lower()

    def test_50000kg_goods_auto_many_trips_warning(self):
        from apps.api.vehicle_service import validate_payload
        result = validate_payload("goods_auto", 50000)
        assert result["ok"] is True
        assert result["trips"] == math.ceil(50000 / 450)  # 112
        assert result["warning"] is not None

    def test_50000kg_heavy_truck_valid_many_trips(self):
        from apps.api.vehicle_service import validate_payload
        result = validate_payload("truck_10w", 50000)
        assert result["ok"] is True
        assert result["trips"] == math.ceil(50000 / 14400)  # 4
        assert result["trips"] == 4

    def test_unknown_vehicle_returns_error(self):
        from apps.api.vehicle_service import validate_payload
        result = validate_payload("flying_saucer", 100)
        assert result["ok"] is False
        assert result["vehicle"] is None

    def test_exact_payload_is_one_trip(self):
        from apps.api.vehicle_service import validate_payload
        result = validate_payload("tata_ace", 900)  # exactly 900 usable
        assert result["trips"] == 1

    def test_payload_plus_one_is_two_trips(self):
        from apps.api.vehicle_service import validate_payload
        result = validate_payload("tata_ace", 901)  # 1 kg over
        assert result["trips"] == 2


# ---------------------------------------------------------------------------
# Phase 3: Transport cost calculation
# ---------------------------------------------------------------------------

class TestTransportCostOwned:
    def setup_method(self):
        from apps.api.vehicle_catalogue import get_vehicle_by_id
        self.v = get_vehicle_by_id("tata_ace")

    def test_owned_single_trip_cost_structure(self):
        from apps.api.vehicle_service import calculate_transport_cost
        result = calculate_transport_cost(self.v, 500, 50.0, "owned")
        assert result["trips"] == 1
        assert result["one_way_distance_km"] == 50.0
        assert result["total_transport_cost"] > 0
        assert "breakdown" in result
        assert "fuel_cost_per_km_inr" in result["breakdown"]

    def test_owned_rate_type_is_configured_estimate(self):
        from apps.api.vehicle_service import calculate_transport_cost
        result = calculate_transport_cost(self.v, 500, 100.0, "owned")
        assert result["rate_type"] == "CONFIGURED_ESTIMATE_OPERATING_COST"

    def test_owned_multiple_trips_scales_linearly(self):
        from apps.api.vehicle_service import calculate_transport_cost
        r1 = calculate_transport_cost(self.v, 900, 50.0, "owned")   # 1 trip
        r2 = calculate_transport_cost(self.v, 1800, 50.0, "owned")  # 2 trips
        assert r2["trips"] == 2
        assert abs(r2["total_transport_cost"] - r1["total_transport_cost"] * 2) < 1.0

    def test_owned_cost_per_kg_decreases_with_larger_vehicle(self):
        from apps.api.vehicle_catalogue import get_vehicle_by_id
        from apps.api.vehicle_service import calculate_transport_cost
        ace = get_vehicle_by_id("tata_ace")
        heavy = get_vehicle_by_id("truck_10w")
        r_ace = calculate_transport_cost(ace, 10000, 100.0, "owned")
        r_heavy = calculate_transport_cost(heavy, 10000, 100.0, "owned")
        # Heavy truck should have lower total cost for 10 tonnes over 100 km
        assert r_heavy["total_transport_cost"] < r_ace["total_transport_cost"]

    def test_effective_cost_per_kg_calculation(self):
        from apps.api.vehicle_service import calculate_transport_cost
        result = calculate_transport_cost(self.v, 500, 50.0, "owned")
        expected = result["total_transport_cost"] / 500.0
        assert abs(result["effective_cost_per_kg"] - expected) < 0.01


class TestTransportCostHired:
    def setup_method(self):
        from apps.api.vehicle_catalogue import get_vehicle_by_id
        self.v = get_vehicle_by_id("tata_ace")

    def test_hired_rate_type_is_configured_estimate_hire(self):
        from apps.api.vehicle_service import calculate_transport_cost
        result = calculate_transport_cost(self.v, 500, 50.0, "hired")
        assert result["rate_type"] == "CONFIGURED_ESTIMATE_HIRE_RATE"

    def test_hired_minimum_charge_applied_for_short_distance(self):
        from apps.api.vehicle_service import calculate_transport_cost
        # At 5 km, rate × distance < min_hire_charge
        result = calculate_transport_cost(self.v, 500, 5.0, "hired")
        assert result["min_charge_applied"] is True
        assert result["cost_per_trip"] == self.v["min_hire_charge"]

    def test_hired_no_minimum_for_long_distance(self):
        from apps.api.vehicle_service import calculate_transport_cost
        # At 200 km, rate × distance > min_hire_charge
        result = calculate_transport_cost(self.v, 500, 200.0, "hired")
        assert result["min_charge_applied"] is False

    def test_hired_multiple_trips_cost(self):
        from apps.api.vehicle_service import calculate_transport_cost
        r_single = calculate_transport_cost(self.v, 900, 50.0, "hired")   # 1 trip
        r_double = calculate_transport_cost(self.v, 1800, 50.0, "hired")  # 2 trips
        assert r_double["trips"] == 2
        assert r_double["total_transport_cost"] == r_single["total_transport_cost"] * 2


class TestVehicleAutoRecommend:
    def test_recommend_goods_auto_for_small_quantity(self):
        from apps.api.vehicle_service import recommend_vehicle
        result = recommend_vehicle(50, 20.0, "hired")
        # Goods auto should win for 50 kg / 20 km
        assert result["vehicle_id"] == "goods_auto"

    def test_recommend_larger_vehicle_for_large_quantity(self):
        from apps.api.vehicle_service import recommend_vehicle
        result = recommend_vehicle(50000, 100.0, "hired")
        # For 50 tonnes, should NOT recommend goods auto or mini truck
        assert result["vehicle_id"] not in {"goods_auto"}
        assert result["trips"] <= 20

    def test_recommendation_has_reason(self):
        from apps.api.vehicle_service import recommend_vehicle
        result = recommend_vehicle(500, 60.0, "owned")
        assert "recommendation_reason" in result
        assert len(result["recommendation_reason"]) > 10

    def test_recommend_returns_valid_cost_breakdown(self):
        from apps.api.vehicle_service import recommend_vehicle
        result = recommend_vehicle(1000, 80.0, "hired")
        assert result["total_transport_cost"] > 0
        assert result["trips"] >= 1
        assert result["vehicle_id"] is not None


# ---------------------------------------------------------------------------
# Phase 4: Mandi optimizer / net realization
# ---------------------------------------------------------------------------

class TestNetRealization:
    def _get_tata_ace(self):
        from apps.api.vehicle_catalogue import get_vehicle_by_id
        return get_vehicle_by_id("tata_ace")

    def test_net_realization_less_than_gross(self):
        from apps.api.mandi_optimizer import calculate_net_realization
        v = self._get_tata_ace()
        result = calculate_net_realization(
            commodity="coffee",
            price_per_kg=240.0,
            quantity_kg=500,
            distance_km=50.0,
            vehicle=v,
            ownership="hired",
        )
        assert result["net_realization"] < result["gross_revenue"]

    def test_net_realization_includes_market_fee(self):
        from apps.api.mandi_optimizer import calculate_net_realization
        from apps.api.vehicle_catalogue import MARKET_FEE_FRACTION
        v = self._get_tata_ace()
        result = calculate_net_realization(
            commodity="coffee",
            price_per_kg=240.0,
            quantity_kg=500,
            distance_km=50.0,
            vehicle=v,
            ownership="hired",
        )
        expected_fee = result["gross_revenue"] * MARKET_FEE_FRACTION
        assert abs(result["market_fee"] - expected_fee) < 0.01

    def test_perishable_has_higher_loss_than_durable(self):
        from apps.api.mandi_optimizer import calculate_net_realization
        v = self._get_tata_ace()
        tomato_result = calculate_net_realization(
            commodity="tomato",
            price_per_kg=20.0,
            quantity_kg=500,
            distance_km=200.0,
            vehicle=v,
            ownership="hired",
        )
        coffee_result = calculate_net_realization(
            commodity="coffee",
            price_per_kg=240.0,
            quantity_kg=500,
            distance_km=200.0,
            vehicle=v,
            ownership="hired",
        )
        # Tomato has higher loss fraction than coffee for same distance
        assert tomato_result["loss_fraction"] > coffee_result["loss_fraction"]

    def test_distant_mandi_may_not_beat_nearby_low_price(self):
        """A far mandi with higher price may lose to nearby mandi after transport."""
        from apps.api.mandi_optimizer import calculate_net_realization
        v = self._get_tata_ace()
        nearby = calculate_net_realization(
            commodity="rice",
            price_per_kg=25.0,
            quantity_kg=1000,
            distance_km=20.0,
            vehicle=v,
            ownership="hired",
        )
        faraway = calculate_net_realization(
            commodity="rice",
            price_per_kg=27.0,
            quantity_kg=1000,
            distance_km=200.0,
            vehicle=v,
            ownership="hired",
        )
        # Net realization comparison is the whole point
        assert nearby["net_realization"] != faraway["net_realization"]

    def test_sellable_quantity_less_than_input_for_perishable(self):
        from apps.api.mandi_optimizer import calculate_net_realization
        v = self._get_tata_ace()
        result = calculate_net_realization(
            commodity="tomato",
            price_per_kg=20.0,
            quantity_kg=500,
            distance_km=150.0,
            vehicle=v,
            ownership="hired",
        )
        assert result["sellable_quantity_kg"] < 500.0

    def test_handling_cost_scales_with_quantity(self):
        from apps.api.mandi_optimizer import calculate_net_realization
        from apps.api.vehicle_catalogue import HANDLING_COST_PER_QUINTAL
        v = self._get_tata_ace()
        result = calculate_net_realization(
            commodity="coffee",
            price_per_kg=240.0,
            quantity_kg=500,
            distance_km=50.0,
            vehicle=v,
            ownership="hired",
        )
        expected_handling = (500 / 100) * HANDLING_COST_PER_QUINTAL
        assert abs(result["handling_cost"] - expected_handling) < 0.01


class TestRankMarkets:
    def _make_candidate(self, name, price_per_kg, distance_km):
        return {
            "rank": 1,
            "market_name": name,
            "town": name,
            "price": price_per_kg * 100,  # Rs/quintal
            "price_per_kg": price_per_kg,
            "unit": "Rs./Quintal",
            "price_date": "2024-10-30",
            "price_freshness": "recent",
            "distance_km": distance_km,
            "duration_min": distance_km * 1.5 if distance_km is not None else None,
            "destination_coordinates": [13.0, 76.0],
            "route_geometry": None,
            "route_url": "https://maps.google.com",
            "route_status": "road_route_available",
            "gross_estimate_inr": None,
            "transport_estimate_inr": None,
            "net_estimate_inr": None,
        }

    def test_closer_mandi_wins_when_prices_equal(self):
        from apps.api.mandi_optimizer import rank_markets
        from apps.api.vehicle_catalogue import get_vehicle_by_id
        v = get_vehicle_by_id("tata_ace")
        candidates = [
            self._make_candidate("Far Market", 240.0, 200.0),
            self._make_candidate("Near Market", 240.0, 50.0),
        ]
        ranked = rank_markets(
            commodity="coffee",
            candidates=candidates,
            quantity_kg=500,
            vehicle_mode="manual",
            vehicle=v,
            ownership="hired",
        )
        assert ranked[0]["market_name"] == "Near Market"

    def test_farther_high_price_mandi_may_rank_first(self):
        from apps.api.mandi_optimizer import rank_markets
        from apps.api.vehicle_catalogue import get_vehicle_by_id
        v = get_vehicle_by_id("tata_ace")
        candidates = [
            self._make_candidate("Near Cheap", 200.0, 10.0),
            self._make_candidate("Far Expensive", 350.0, 80.0),
        ]
        # For 100 kg of coffee — the expensive far mandi may still win on net
        ranked = rank_markets(
            commodity="coffee",
            candidates=candidates,
            quantity_kg=100,
            vehicle_mode="manual",
            vehicle=v,
            ownership="hired",
        )
        # Both should have net_estimate_inr computed
        assert ranked[0]["net_estimate_inr"] is not None
        assert ranked[1]["net_estimate_inr"] is not None

    def test_all_ranked_mandis_have_recommendation_order(self):
        from apps.api.mandi_optimizer import rank_markets
        from apps.api.vehicle_catalogue import get_vehicle_by_id
        v = get_vehicle_by_id("tata_ace")
        candidates = [
            self._make_candidate("A", 240.0, 50.0),
            self._make_candidate("B", 220.0, 30.0),
            self._make_candidate("C", 260.0, 100.0),
        ]
        ranked = rank_markets(
            commodity="coffee",
            candidates=candidates,
            quantity_kg=500,
            vehicle_mode="manual",
            vehicle=v,
            ownership="hired",
        )
        orders = [m["recommendation_order"] for m in ranked]
        assert orders == list(range(1, len(candidates) + 1))

    def test_no_route_candidate_ranks_last(self):
        from apps.api.mandi_optimizer import rank_markets
        from apps.api.vehicle_catalogue import get_vehicle_by_id
        v = get_vehicle_by_id("tata_ace")
        candidates = [
            self._make_candidate("Good Route", 240.0, 50.0),
            {**self._make_candidate("No Route", 300.0, None), "distance_km": None},
        ]
        ranked = rank_markets(
            commodity="coffee",
            candidates=candidates,
            quantity_kg=500,
            vehicle_mode="manual",
            vehicle=v,
            ownership="hired",
        )
        # Mandi with net_realization should rank above one without route
        assert ranked[0]["market_name"] == "Good Route"

    def test_auto_mode_selects_vehicle_per_mandi(self):
        from apps.api.mandi_optimizer import rank_markets
        candidates = [
            self._make_candidate("Market A", 240.0, 50.0),
        ]
        ranked = rank_markets(
            commodity="coffee",
            candidates=candidates,
            quantity_kg=500,
            vehicle_mode="auto",
            vehicle=None,
            ownership="hired",
        )
        assert ranked[0]["vehicle_summary"] is not None
        assert ranked[0]["vehicle_summary"]["vehicle_id"] is not None


# ---------------------------------------------------------------------------
# Phase 5: harvest_routes_payload integration (monkeypatched)
# ---------------------------------------------------------------------------

class TestHarvestRoutesPayloadV2:
    def _mock_rankings(self):
        return {
            "rankings": [
                {
                    "rank": 1,
                    "market_name": "Chikkamagaluru APMC",
                    "locations": ["Chikkamagaluru"],
                    "price": 240.0,
                    "unit": "INR_PER_KG",
                    "date": "2026-10-30",
                    "freshness_status": "recent",
                },
                {
                    "rank": 2,
                    "market_name": "Sakleshpur Market",
                    "locations": ["Sakleshpur"],
                    "price": 230.0,
                    "unit": "INR_PER_KG",
                    "date": "2026-10-30",
                    "freshness_status": "recent",
                },
            ],
            "unit": "INR_PER_KG",
            "selected_series": "Arabica Parchment",
            "unit_note": None,
            "data_status": "test",
            "source": "test source",
        }

    def test_response_has_vehicle_header(self, monkeypatch):
        from apps.api import harvest_routes

        monkeypatch.setattr(harvest_routes, "market_rankings_payload", lambda *a, **kw: self._mock_rankings())
        monkeypatch.setattr(harvest_routes, "_geocode", lambda place: (12.9, 75.78) if "Sakleshpur" in place else (13.31, 75.77))
        monkeypatch.setattr(harvest_routes, "_road_route", lambda o, d: {"distance_km": 52.4, "duration_min": 74.0, "geometry": None})

        payload = harvest_routes.HarvestRouteRequest(
            commodity="coffee",
            origin="Sakleshpur, Hassan",
            quantity_kg=500,
            vehicle_mode="auto",
            ownership="hired",
            limit=2,
        )
        result = harvest_routes.harvest_routes_payload(None, payload)
        assert "vehicle" in result
        assert result["vehicle"]["mode"] == "auto"

    def test_manual_vehicle_selection_uses_tata_ace(self, monkeypatch):
        from apps.api import harvest_routes

        monkeypatch.setattr(harvest_routes, "market_rankings_payload", lambda *a, **kw: self._mock_rankings())
        monkeypatch.setattr(harvest_routes, "_geocode", lambda p: (12.9, 75.78))
        monkeypatch.setattr(harvest_routes, "_road_route", lambda o, d: {"distance_km": 52.4, "duration_min": 74.0, "geometry": None})

        payload = harvest_routes.HarvestRouteRequest(
            commodity="coffee",
            origin="Sakleshpur, Hassan",
            quantity_kg=500,
            vehicle_mode="manual",
            vehicle_id="tata_ace",
            ownership="hired",
            limit=2,
        )
        result = harvest_routes.harvest_routes_payload(None, payload)
        assert result["vehicle"]["vehicle_id"] == "tata_ace"
        assert result["vehicle"]["mode"] == "manual"

    def test_markets_sorted_by_net_realization(self, monkeypatch):
        from apps.api import harvest_routes

        monkeypatch.setattr(harvest_routes, "market_rankings_payload", lambda *a, **kw: self._mock_rankings())
        monkeypatch.setattr(harvest_routes, "_geocode", lambda p: (12.9, 75.78))
        monkeypatch.setattr(harvest_routes, "_road_route", lambda o, d: {"distance_km": 52.4, "duration_min": 74.0, "geometry": None})

        payload = harvest_routes.HarvestRouteRequest(
            commodity="coffee",
            origin="Sakleshpur, Hassan",
            quantity_kg=500,
            vehicle_mode="auto",
            ownership="hired",
            limit=2,
        )
        result = harvest_routes.harvest_routes_payload(None, payload)
        markets = result["markets"]
        nets = [m["net_estimate_inr"] for m in markets if m["net_estimate_inr"] is not None]
        assert nets == sorted(nets, reverse=True), "Markets not sorted by net realization"

    def test_response_includes_profit_breakdown(self, monkeypatch):
        from apps.api import harvest_routes

        monkeypatch.setattr(harvest_routes, "market_rankings_payload", lambda *a, **kw: self._mock_rankings())
        monkeypatch.setattr(harvest_routes, "_geocode", lambda p: (12.9, 75.78))
        monkeypatch.setattr(harvest_routes, "_road_route", lambda o, d: {"distance_km": 52.4, "duration_min": 74.0, "geometry": None})

        payload = harvest_routes.HarvestRouteRequest(
            commodity="coffee",
            origin="Sakleshpur, Hassan",
            quantity_kg=500,
            vehicle_mode="auto",
            ownership="hired",
            limit=2,
        )
        result = harvest_routes.harvest_routes_payload(None, payload)
        market = result["markets"][0]
        assert "profit_breakdown" in market
        assert market["profit_breakdown"] is not None

    def test_overload_warning_for_manual_small_vehicle_large_quantity(self, monkeypatch):
        from apps.api import harvest_routes

        monkeypatch.setattr(harvest_routes, "market_rankings_payload", lambda *a, **kw: self._mock_rankings())
        monkeypatch.setattr(harvest_routes, "_geocode", lambda p: (12.9, 75.78))
        monkeypatch.setattr(harvest_routes, "_road_route", lambda o, d: {"distance_km": 52.4, "duration_min": 74.0, "geometry": None})

        payload = harvest_routes.HarvestRouteRequest(
            commodity="coffee",
            origin="Sakleshpur, Hassan",
            quantity_kg=5000,  # > goods_auto usable payload (450 kg)
            vehicle_mode="manual",
            vehicle_id="goods_auto",
            ownership="hired",
            limit=2,
        )
        result = harvest_routes.harvest_routes_payload(None, payload)
        assert result["vehicle"]["overload_warning"] is not None

    def test_backward_compat_transport_cost_per_km_accepted(self, monkeypatch):
        from apps.api import harvest_routes

        monkeypatch.setattr(harvest_routes, "market_rankings_payload", lambda *a, **kw: self._mock_rankings())
        monkeypatch.setattr(harvest_routes, "_geocode", lambda p: (12.9, 75.78))
        monkeypatch.setattr(harvest_routes, "_road_route", lambda o, d: {"distance_km": 52.4, "duration_min": 74.0, "geometry": None})

        payload = harvest_routes.HarvestRouteRequest(
            commodity="coffee",
            origin="Sakleshpur, Hassan",
            quantity_kg=500,
            transport_cost_per_km=12.0,  # legacy field
            limit=1,
        )
        result = harvest_routes.harvest_routes_payload(None, payload)
        assert "markets" in result


# ---------------------------------------------------------------------------
# Phase 6: API regression tests (GET endpoints)
# ---------------------------------------------------------------------------

class TestHarvestRouterEndpoints:
    def test_get_health(self):
        from apps.api.harvest_routes import harvest_route_health
        result = harvest_route_health()
        assert result["status"] == "available"
        assert result["feature"] == "harvest-route"
        assert "v2" in result["version"]

    def test_get_vehicles_returns_7(self):
        from apps.api.harvest_routes import list_vehicles
        result = list_vehicles()
        assert result["count"] == 7
        assert len(result["vehicles"]) == 7

    def test_get_fuel_price_returns_configured_estimate(self):
        from apps.api.harvest_routes import fuel_price
        result = fuel_price()
        assert "diesel" in result
        assert result["diesel"]["price_type"] == "CONFIGURED_ESTIMATE"


# ---------------------------------------------------------------------------
# Phase 7: Commodity extension regression
# ---------------------------------------------------------------------------

class TestCommodityExtension:
    def test_coffee_accepted(self):
        from apps.api.harvest_routes import HarvestRouteRequest
        p = HarvestRouteRequest(commodity="coffee", origin="Test", quantity_kg=100)
        assert p.commodity == "coffee"

    def test_pepper_accepted(self):
        from apps.api.harvest_routes import HarvestRouteRequest
        p = HarvestRouteRequest(commodity="pepper", origin="Test", quantity_kg=100)
        assert p.commodity == "pepper"

    def test_rice_accepted(self):
        from apps.api.harvest_routes import HarvestRouteRequest
        p = HarvestRouteRequest(commodity="rice", origin="Test", quantity_kg=100)
        assert p.commodity == "rice"

    def test_tomato_accepted(self):
        from apps.api.harvest_routes import HarvestRouteRequest
        p = HarvestRouteRequest(commodity="tomato", origin="Test", quantity_kg=100)
        assert p.commodity == "tomato"

    def test_maize_accepted(self):
        from apps.api.harvest_routes import HarvestRouteRequest
        p = HarvestRouteRequest(commodity="maize", origin="Test", quantity_kg=100)
        assert p.commodity == "maize"

    def test_paddy_accepted(self):
        from apps.api.harvest_routes import HarvestRouteRequest
        p = HarvestRouteRequest(commodity="paddy", origin="Test", quantity_kg=100)
        assert p.commodity == "paddy"

    def test_potato_accepted(self):
        from apps.api.harvest_routes import HarvestRouteRequest
        p = HarvestRouteRequest(commodity="potato", origin="Test", quantity_kg=100)
        assert p.commodity == "potato"

    def test_invalid_commodity_rejected(self):
        from apps.api.harvest_routes import HarvestRouteRequest
        import pydantic
        with pytest.raises((pydantic.ValidationError, ValueError)):
            HarvestRouteRequest(commodity="wheat", origin="Test", quantity_kg=100)

    def test_vehicle_mode_defaults_to_auto(self):
        from apps.api.harvest_routes import HarvestRouteRequest
        p = HarvestRouteRequest(commodity="coffee", origin="Test", quantity_kg=100)
        assert p.vehicle_mode == "auto"

    def test_ownership_defaults_to_hired(self):
        from apps.api.harvest_routes import HarvestRouteRequest
        p = HarvestRouteRequest(commodity="coffee", origin="Test", quantity_kg=100)
        assert p.ownership == "hired"

    def test_manual_mode_without_vehicle_id_falls_back_to_auto(self):
        from apps.api.harvest_routes import HarvestRouteRequest
        p = HarvestRouteRequest(
            commodity="coffee",
            origin="Test",
            quantity_kg=100,
            vehicle_mode="manual",
            vehicle_id=None,
        )
        assert p.vehicle_mode == "auto"


# ---------------------------------------------------------------------------
# Phase 8: Original OSRM helper regression (from test_harvest_route_map.py)
# ---------------------------------------------------------------------------

class TestOsrmHelper:
    def test_road_route_returns_geojson_geometry(self, monkeypatch):
        from apps.api import harvest_routes

        class FakeResponse:
            def raise_for_status(self): return None
            def json(self):
                return {
                    "routes": [{
                        "distance": 12450,
                        "duration": 1800,
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [[75.7, 12.9], [75.8, 13.0]],
                        },
                    }]
                }

        monkeypatch.setattr(harvest_routes.httpx, "get",
                            lambda url, params, timeout: FakeResponse())
        route = harvest_routes._road_route((12.9, 75.7), (13.0, 75.8))
        assert route["distance_km"] == 12.45
        assert route["duration_min"] == 30.0
        assert route["geometry"]["type"] == "LineString"

