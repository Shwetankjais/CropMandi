# CropMandi AI — Integrated update report

## What this package is

This update builds on the recovered `CropMandi_Market_Rankings_Integrated` project. It preserves the original FastAPI + SQLAlchemy/SQLite backend, static HTML/Tailwind/vanilla-JavaScript frontend, and existing modules for Coffee, Pepper, Rice, market rankings, analytics, cold storage, weather, alerts, settings, Razorpay test-mode payments, and the voice assistant.

## Data imported

The supplied `DATASET.zip` contains 86 `.xls` files which are HTML-table exports rather than binary Excel BIFF workbooks. The importer carries forward sparsely repeated market/district labels, excludes subtotal/summary rows, skips invalid dates and prices, and deduplicates repeated series observations. One conflicting duplicate in the Paddy reports is flagged in the quality report.

| Crop | Files | Clean observations | Market names | Districts |
|---|---:|---:|---:|---:|
| Tomato | 22 | 14,708 | 44 | 18 |
| Maize | 20 | 26,059 | 131 | 28 |
| Paddy | 22 | 23,660 | 111 | 29 |
| Potato | 22 | 8,991 | 38 | 20 |
| **Total** | **86** | **73,418** | **151 (unique market/district pairs)** | — |

Date coverage: 2025-01-01 through 2026-10-30. The database includes the imported data in a dedicated crop-market observations table; existing commodity observation tables and records were not replaced. The original archive is retained at `data/raw/agmarknet_vegetable_reports.zip`; the cleaned CSV and audit are retained under `data/processed/` and `data/reports/`.

The reports were supplied by the user and have not been independently authenticated against a live AGMARKNET feed. API responses therefore identify this data as `USER_SUPPLIED_AGMARKNET_EXPORT_UNVERIFIED`.

## Crop models integrated

The four supplied `RandomForestRegressor` pickle files are included under `ml/artifacts/` and loaded by `ml/crop_prediction_service.py`:

- Tomato: 13 input features; price-level estimator.
- Maize: 17 input features; delta estimator.
- Paddy: 17 input features; delta estimator.
- Potato: 17 input features; delta estimator.

For each crop, the service reads the matching market/variety/grade history from the local database, constructs the model input, runs the prediction and reports the observations used. The maize/paddy/potato engineered fields (`price_dev_roll`, `momentum_1d`, `momentum_7d`, `arrivals_log`) are inferred from feature names because the original training/preprocessing code was not supplied. The pickle also does not disclose the target construction or forecast horizon. The API therefore returns the raw delta and marks the delta-to-price addition as an assumption. This integration does **not** establish predictive accuracy; no held-out chronological evaluation dataset/target definition was provided.

The project pins scikit-learn to 1.7.2, the serialization version identified for the supplied models.

## Location and HarvestRoute

The new page is `frontend/harvestroute/code.html`, linked from the dashboard navigation. It includes:

- Optional farmer GPS capture through browser Geolocation, plus manual coordinates/address entry.
- Mappls forward and reverse geocoding.
- Mandi directory populated from market records, with coordinates initially NULL/unverified.
- Mappls geocoding for a selected mandi. New coordinates remain suggested/unverified pending verification against the actual market entrance.
- Nearby mandi search and distance matrix for driving, biking or trucking.
- Transport-cost and net-return calculator with quantity, round-trip, per-km rate, fixed vehicle fee, handling, market fee and produce-loss inputs.
- Market sorting based on estimated net return, not the listed market price alone.

If the Mappls REST key is absent, development mode returns Haversine straight-line approximations only (no ETA), explicitly labelled as not-road-distance. If a key is configured but the provider call fails, the integration reports the failure rather than silently substituting a straight-line estimate. The live Mappls endpoints and live map rendering have not been exercised because Mappls credentials were not included.

Set `MAPPLS_REST_API_KEY` in `.env` and enable Distance Matrix, Geocoding and Reverse Geocoding for the Mappls application. Set a separately domain-restricted `MAPPLS_MAP_SDK_KEY` for the browser map. Set a strong random `MANDI_COORDINATE_ADMIN_TOKEN`; the coordinate-confirmation endpoint requires it in `X-Mandi-Admin-Token`. Use HTTPS and integrate the shared-secret prototype approval with your real admin/role system before production.

Farmer GPS is optional and is not persisted by the capture endpoint. Current phone location is not assumed to be the farm location. Background tracking is not implemented.

## New APIs

- `GET /api/crops/models`
- `GET /api/crops/options?crop=tomato|maize|paddy|potato`
- `GET /api/crops/history`
- `GET /api/crops/rankings`
- `POST /api/crops/predict`
- `GET /api/mandis`
- `POST /api/location/capture`
- `POST /api/location/geocode`
- `POST /api/location/reverse-geocode`
- `GET /api/location/map-config`
- `POST /api/mandis/geocode`
- `POST /api/mandis/{id}/confirm`
- `GET /api/markets/nearby`
- `POST /api/routes/matrix`
- `POST /api/harvestroute/optimize`

The dashboard's existing Top 5 market ranking selector now also supports Tomato, Maize, Paddy and Potato. Existing Coffee/Pepper/Rice selection remains on its original ranking service.

## Run locally (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set your Mappls credentials and a random `MANDI_COORDINATE_ADMIN_TOKEN`. Start the backend from the project root:

```powershell
python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8001
```

In a second terminal:

```powershell
Set-Location frontend
python -m http.server 5500
```

Open `http://127.0.0.1:5500/` and choose HarvestRoute, or open `http://127.0.0.1:5500/harvestroute/code.html`. API docs: `http://127.0.0.1:8001/docs`.

## QA completed in the build environment

- Original baseline before modifications: 96 tests passed.
- Updated test suite: **105 tests passed**.
- Python compilation: passed.
- JavaScript syntax checks for HarvestRoute, market rankings and shared API helper: passed.
- API smoke checks for OpenAPI, all four crop options, crop rankings, mandi directory and Mappls configuration: HTTP 200.
- Real database-history prediction requests: all four supplied models returned finite outputs.
- Mappls distance matrix: mocked provider test passed, including coordinate order and distance/time unit conversion.
- Farmer location capture: verified to return `stored: false` when processed.
- Static frontend server: dashboard, HarvestRoute page and JS assets returned HTTP 200.

A full Chromium UI automation run was blocked by the build environment's local-loopback browser policy; interactive visual testing with a real Mappls SDK key remains a setup-time check.
