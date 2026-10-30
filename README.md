# CropMandi AI V1 — Coffee + Pepper backend

Cardamom is out of scope for V1 market data. The dashboard includes a Razorpay **TEST MODE** demo checkout; it is not a live crop sale.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

If Docker/Postgres is unavailable, set in `.env`:

```
DATABASE_URL=sqlite:///./data/cropmandi.db
```

SQLite is a local fallback only.

## Ingest (production Pepper / Coffee Board PDFs)

```powershell
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\python -m ingest.audit_datasets
.\.venv\Scripts\python -m ingest.run
.\.venv\Scripts\python -m ingest.readiness
```

The unverified file `karnataka_daily_coffee_prices_7years.xlsx` is **not** inserted into `price_observations`. Experimental Coffee weekday frames live under `data/experimental/`.

## Experimental models (do not re-run for the API)

```powershell
.\.venv\Scripts\python -m ml
```

Phase 2 result: **RandomForestRegressor did not beat naive last-value** on any Coffee or Pepper series. The API uses `naive_last_value` as a **baseline estimate**, not an ML forecast. Saved metrics: `ml/experiments/`.

## API

The dashboard JavaScript calls `http://127.0.0.1:8001`. Start the API on that port:

```powershell
.\.venv\Scripts\uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8001
.\.venv\Scripts\python.exe -m pytest -q
```

OpenAPI: `http://127.0.0.1:8001/docs`

## Razorpay TEST MODE payments

Do not put live keys or any secret values in git, README, or frontend JavaScript. The Key Secret and webhook secret stay on the server only.

1. Create a Razorpay account and switch the dashboard to **Test Mode**.
2. Generate Test API keys (`rzp_test_...` Key ID plus Key Secret).
3. Copy `.env.example` to `.env` if needed, then set:

```
RAZORPAY_KEY_ID=rzp_test_your_key_id
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=
```

4. Webhooks cannot reach localhost directly. Use a tunnel (for example ngrok) or a staging HTTPS URL, then in Razorpay Dashboard → Webhooks add:

`https://<your-public-host>/api/payment/webhook`

Recommended events: `payment.authorized`, `payment.captured`, `payment.failed`, `order.paid`.
Paste the webhook secret into `RAZORPAY_WEBHOOK_SECRET`. Never disable signature verification.

5. Start the backend on port 8001 (command above).
6. Open the dashboard HTML (`frontend/cropmandi_ai_dashboard/code.html`) via a local static server such as `http://127.0.0.1:5500`.
7. Click **Pay ₹100 (Test Mode)**.
8. Razorpay Checkout should open. Complete a test payment with Razorpay test cards.
9. The UI shows success only after `POST /api/payment/verify` confirms the HMAC signature.
10. Confirm `GET /api/payment/status/<order_id>` returns `CAPTURED` (or `AUTHORIZED`).
11. If the tunnel is configured, Razorpay will also POST the webhook; duplicate deliveries are ignored.

Payment API:

| Method | Path | Notes |
|---|---|---|
| POST | `/api/payment/create-order` | Server sets ₹100 (10000 paise). Client amount is not trusted. |
| POST | `/api/payment/verify` | HMAC-SHA256 of `order_id|payment_id` using the server secret. |
| GET | `/api/payment/status/{order_id}` | Server-side status for the demo identity. |
| GET | `/api/payment/history` | Demo-identity history only. |
| POST | `/api/payment/cancel` | Marks `CREATED` orders cancelled after Checkout dismiss. |
| POST | `/api/payment/webhook` | Raw-body webhook signature check. Idempotent by event id. |

Local webhook checks (keep verification on): valid signature, invalid signature, duplicate event, malformed JSON, unknown event.

If Checkout does not open: confirm the API is on **8001**, browser console has no CORS/network error, `https://checkout.razorpay.com/v1/checkout.js` loaded, and `.env` test keys are present. Restart uvicorn after changing `.env`.

### Endpoints

| Method | Path | Query |
|---|---|---|
| GET | `/api/prices/latest` | `commodity=coffee\|pepper` |
| GET | `/api/prices/history` | `commodity`, `series` (required), optional `from`, `to` (`YYYY-MM-DD`) |
| GET | `/api/predictions/next` | `commodity`, `series` (required) |
| GET | `/api/markets/rankings` | `commodity`, optional `series`, `limit` (1–5; defaults to 5) |

Supported series:

- Coffee: `Arabica Parchment`, `Arabica Cherry`, `Robusta Parchment`, `Robusta Cherry`
- Pepper: `Cochin Garbled`, `Cochin Ungarbled`, `Sirsi`

`latest` is the last **observed** price. `predictions/next` is a **next-session estimate** equal to that last price (`naive_last_value`). It is not a trained-model forecast.

### Cross-market price rankings

The dashboard's **Top 5 highest-price markets** panel compares the latest available observation for each market in the selected crop variety/grade and sorts those recorded prices from highest to lowest. It returns the observation date for every market because dates can differ; observations older than 30 days are marked Historical in the UI. Coffee and Pepper rankings use explicitly mapped rows from the local market-centre workbooks (`UNVERIFIED_LOCAL_DATA`, not official exchange/mandi quotations); the Pepper workbook does not provide a price quantity unit. Rice rankings use ingested AGMARKNET records. If Rice observations have not been ingested, the API returns an empty list rather than sample or fabricated prices.

### Data status

- Coffee workbook responses: `data_status=UNVERIFIED_HISTORICAL_COFFEE_DATA`, `data_usage=EXPERIMENTAL_ONLY`, `official=false`. Not Coffee Board / official mandi data.
- Pepper: Spices Board `indicative_daily_average`. Not a guaranteed transaction price. Cochin and Sirsi are not mixed.

### Example: latest Coffee

`GET /api/prices/latest?commodity=coffee`

```json
{
  "available": true,
  "commodity": "coffee",
  "observations": [
    {
      "commodity": "coffee",
      "series": "Arabica Parchment",
      "price": 24000.0,
      "unit": "INR_PER_50KG",
      "observation_date": "2026-08-31",
      "official": false,
      "experimental": true,
      "data_status": "UNVERIFIED_HISTORICAL_COFFEE_DATA",
      "data_usage": "EXPERIMENTAL_ONLY"
    }
  ]
}
```

### Example: latest Pepper

`GET /api/prices/latest?commodity=pepper`

```json
{
  "available": true,
  "commodity": "pepper",
  "observations": [
    {
      "commodity": "pepper",
      "series": "Cochin Garbled",
      "price": 722.0,
      "unit": "INR_PER_KG",
      "price_type": "indicative_daily_average",
      "indicative": true,
      "guaranteed_transaction_price": false,
      "observation_date": "2026-09-03"
    }
  ]
}
```

### Example: next-session estimate (Coffee)

`GET /api/predictions/next?commodity=coffee&series=Arabica%20Parchment`

Coffee target session = next weekday (Friday → Monday). Pepper `target_session` is `null` because the next published date is unknown.

### Errors

| Situation | Status | `error` |
|---|---|---|
| Unsupported commodity | 400 | `unsupported_commodity` |
| Missing series | 400 | `missing_series_parameter` |
| Unsupported series | 400 | `unsupported_series` |
| Bad `from`/`to` | 400 | `invalid_date_filter` |
| No observations | 404 | `no_available_observations` |

Stack traces are not returned to clients.

## Multilingual voice assistant

A Hindi/English/Kannada voice assistant is integrated into the existing FastAPI app and frontend. The widget records speech in the browser and transcribes it locally through faster-whisper, avoiding the browser Web Speech API network-recognition failure. Multilingual neural voice output uses edge-tts, with browser speech synthesis as a fallback. The price lookup uses this project's existing data services.

Start the API from the project root:

```powershell
python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8001
```

In a second terminal, serve `frontend/` as the static web root:

```powershell
Set-Location frontend
python -m http.server 5500
```

Open `http://127.0.0.1:5500/`. The voice widget appears on the frontend pages and calls `/api/voice/transcribe`, `/api/voice/command`, and `/api/voice/speak` on the FastAPI service. First use downloads the Whisper `base` model once; subsequent speech recognition runs locally. Neural audio output needs internet access. See [`cropmandi_voice_assistant/README.md`](cropmandi_voice_assistant/README.md) for details and troubleshooting.

### Voice assistant dependency update

If this project was already installed before the local speech-recognition fix, update the existing virtual environment and restart Uvicorn:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The Whisper `base` model downloads automatically during the first voice-input request (internet needed once; input is local after the model is cached). `av==18.1.0` is pinned to avoid the PyAV 19 `metadata_errors` incompatibility with the project's `faster-whisper==1.2.1`. Hindi/Kannada neural audio uses an online TTS service, so spoken output needs internet unless the computer has a suitable local voice installed. Hard-refresh the frontend with `Ctrl+F5` to load the updated voice JavaScript.

---

## HarvestRoute and vegetable crop intelligence (new)

The recovered CropMandi project now also includes a separate vegetable-market data layer and an integrated **HarvestRoute** frontend. The original Coffee/Pepper/Rice services, cold storage, analytics, payments and multilingual voice assistant remain in place. Vegetable data is stored in `crop_market_observations`; it does not relax or alter the existing `Commodity` table constraints.

### Imported user-supplied datasets

`data/raw/agmarknet_vegetable_reports.zip` is the original uploaded archive. The 86 `.xls` files in that archive are HTML-table exports rather than binary Excel BIFF files. The importer parses the report tables, carries forward repeated market/district headings, drops subtotal and invalid rows, and records source-file provenance. The cleaned data is stored in `data/processed/crop_market_observations.csv` and in the `crop_market_observations` SQLite table.

| Crop | Report files | Clean observations | Market names | Date coverage |
|---|---:|---:|---:|---|
| Tomato | 22 | 14,708 | 44 | 2025-01-01 to 2026-10-30 |
| Maize | 20 | 26,059 | 131 | 2025-01-01 to 2026-10-30 |
| Paddy | 22 | 23,660 | 111 | 2025-01-01 to 2026-10-30 |
| Potato | 22 | 8,991 | 38 | 2025-01-01 to 2026-10-30 |
| **Total** | **86** | **73,418** | **151 market/district pairs** | **2025-01-01 to 2026-10-30** |

The quality audit is `data/reports/crop_market_data_quality.json`. One duplicate paddy series/date had conflicting modal values; that row is flagged `DUPLICATE_CONFLICT_REQUIRES_REVIEW`. These are user-supplied report exports and are labelled `USER_SUPPLIED_AGMARKNET_EXPORT_UNVERIFIED`; do not describe them as a live or independently certified quote feed.

To rebuild the CSV and database import from the included original archive:

```powershell
python -m ingest.crop_market_reports
python -m scripts.import_crop_market_data
```

The database included in this bundle is already seeded with the 73,418 records. To use that local SQLite file, put the following in `.env` (or leave `.env` absent so the local default is used):

```dotenv
DATABASE_URL=sqlite:///./data/cropmandi.db
```

### Supplied model artifacts

The four uploaded pickle files are included under `ml/artifacts/`:

- `tomato_price_model.pkl` — 13 input features; regression output is treated as a price-level model output.
- `maize_delta_rf_model.pkl` — 17 input features; regression output is treated as a signed delta.
- `paddy_delta_rf_model.pkl` — 17 input features; regression output is treated as a signed delta.
- `potato_delta_rf_model.pkl` — 17 input features; regression output is treated as a signed delta.

The artifacts record scikit-learn 1.7.2; `requirements.txt` pins `scikit-learn==1.7.2`. Run the API with the bundled model files present. The application creates model inputs from a selected market + variety + grade history. It needs at least eight dated observations for that series. Lag fields use previous available market observations; the rolling window uses the latest seven records including the latest record.

**Model interpretation limitation:** The pickle files do not include the target-generation script, training notebook, forecast horizon or full feature-engineering specification. For maize, paddy and potato, `price_dev_roll`, `momentum_1d`, `momentum_7d` and `arrivals_log` are currently inferred as (respectively) latest modal minus rolling mean, latest modal minus lag-1, latest modal minus lag-7, and `ln(1 + lag-1 arrivals)`. The delta is returned as the model's raw output; the UI also shows `latest modal + delta` only as an explicitly labelled indicative derivation. Verify those formulas and target semantics against the training pipeline before production use.

Scenario tests demonstrate that the software loads and responds; they are **not model-accuracy metrics**. The app reports `NOT_VALIDATED_AGAINST_HELD_OUT_ACTUALS` and does not claim a percentage accuracy.

### New crop model endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/crops/models` | Model readiness, data counts and top feature importance |
| GET | `/api/crops/options?crop=tomato` | Markets, varieties and valid grade combinations |
| GET | `/api/crops/history` | Historical arrivals/min/max/modal observations for a series |
| GET | `/api/crops/rankings?crop=tomato` | Highest latest recorded modal prices by market |
| POST | `/api/crops/predict` | Run the selected pickle against the selected market history |

Example prediction request:

```json
{
  "crop": "tomato",
  "market_name": "KOLAR",
  "district": "Kolar",
  "variety": "TOMATO",
  "grade": "AVERAGE"
}
```

### Mappls + HarvestRoute

The new page is `frontend/harvestroute/code.html`, linked from the dashboard sidebar and top navigation. It supports optional browser GPS capture, manual village/address geocoding, mandi directory browsing, Mappls geocoding, nearby market search, route distance matrix, model prediction and transport-adjusted net-return comparison.

Add Mappls credentials to local `.env`:

```dotenv
MAPPLS_REST_API_KEY=your_server_side_mappls_rest_key
MAPPLS_MAP_SDK_KEY=your_domain_restricted_map_sdk_key
MAPPLS_API_TIMEOUT=15
```

Enable Distance Matrix, Geocoding and Reverse Geocoding access for the Mappls application in Mappls Console. Use a separate domain-restricted map SDK key for the browser. **The REST key is never returned by the API or placed in frontend JavaScript.** The Map SDK key can be returned by `/api/location/map-config` and should be restricted to the project's frontend domain.

Mappls Distance Matrix is called server-side for driving, biking or trucking profiles. Mappls documents a maximum of 100 coordinate points including the origin; this package sends at most 99 destinations per request. When `MAPPLS_REST_API_KEY` is absent, the app returns Haversine straight-line distances as a development fallback, with no ETA and an explicit `STRAIGHT_LINE_APPROXIMATION` label. They are **not road distances** and must not be used as final transport quotes. See Mappls's [Distance Matrix documentation](https://developer.mappls.com/documentation/sdk/rest-apis/mappls-distance-matrix-api/readme/), [Geocoding documentation](https://developer.mappls.com/documentation/sdk/rest-apis/mappls-maps-geocoding-rest-api-example/Readme/) and [Reverse Geocoding documentation](https://developer.mappls.com/documentation/sdk/rest-apis/mappls-maps-reverse-geocoding-rest-api-example/Readme/).

Mandi names are sourced from the imported market reports. Their coordinates start `UNVERIFIED` and NULL; no coordinates or fees are fabricated. A Mappls geocode result is saved as `MAPPLS_SUGGESTED_UNVERIFIED`. Check that pin against the actual market entrance before confirming it. The confirmation endpoint requires a server-side `MANDI_COORDINATE_ADMIN_TOKEN`, sent in the `X-Mandi-Admin-Token` header. Configure a long random token in `.env`; keep it restricted to authorized administrators and use HTTPS. This is a simple shared-secret gate for the prototype, not a substitute for your production user/role authentication system.

Farmer GPS permission is optional. The browser's current coordinates are used for the request and are not persisted by `/api/location/capture`. The farmer can also enter a village/farm address manually. Use the farm/collection point rather than assuming the phone's current location is the farm. Continuous/background tracking is not implemented.

### Location and HarvestRoute endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/location/map-config` | Return map SDK configuration status (never returns REST key) |
| POST | `/api/location/capture` | Receive coordinates for one request; no persistence |
| POST | `/api/location/geocode` | Convert a manually entered address to a coordinate suggestion |
| POST | `/api/location/reverse-geocode` | Convert GPS coordinates to a readable address |
| GET | `/api/mandis` | Browse market directory and coordinate verification status |
| POST | `/api/mandis/geocode` | Geocode one market record through Mappls |
| POST | `/api/mandis/{id}/confirm` | Mark manually checked coordinates as confirmed (requires server-side admin token) |
| GET | `/api/markets/nearby` | Find geocoded markets around a farmer coordinate and calculate distances |
| POST | `/api/routes/matrix` | Calculate a one-to-many distance matrix |
| POST | `/api/harvestroute/optimize` | Rank markets by estimated net return after costs |

The optimizer uses the most recent stored modal price for each market/selected variety/grade and user-entered costs. The per-km defaults are examples only; replace them with local transporter quotes. The current output is a decision-support estimate, not a guaranteed sale offer. Only coordinate-confirmed mandi records are included in net-return optimization.

Generate a long random admin approval secret for `.env` with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Put the generated value in `MANDI_COORDINATE_ADMIN_TOKEN`. Do not commit `.env` or distribute this token to farmer accounts. The Mappls REST key and admin token remain server-side; only the separately domain-restricted Map SDK key is sent to the browser.

### Run the integrated app

From the project root:

```powershell
python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8001
```

In a second terminal:

```powershell
Set-Location frontend
python -m http.server 5500
```

Open `http://127.0.0.1:5500/` and use **HarvestRoute** in the dashboard navigation, or open `http://127.0.0.1:5500/harvestroute/code.html` directly. API docs: `http://127.0.0.1:8001/docs`.
