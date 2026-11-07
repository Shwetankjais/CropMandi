# CropMandi Voice Assistant — isolated enhancement

The assistant is still mounted by the existing `apps.api.main:app` backend. No shared API, model, database schema, prediction pipeline, navigation component or authentication code was changed.

## What it can do

- Navigate to existing Dashboard, My Crops, HarvestRoute, Mandi Price AI, Analytics, Settings, Farm Calendar and Alert Center pages, plus existing Cold Storage, Weather and Payment dashboard anchors.
- Return to a previous CropMandi page tracked in this browser tab. It never sends a back command to another website.
- Read exact-date and latest-recorded coffee, pepper, rice, paddy, tomato, potato and maize prices when matching observations exist. Source units, dates and unverified-data status are retained.
- Compare matching historical prices. An explicit missing day is never replaced with a nearby day.
- Reuse the Mandi Price AI ExtraTrees pipeline for market-level recursive forecasts (up to 31 days after its last input). These are not variety/grade-specific forecasts.
- Explain coffee/pepper last-value baselines as baselines, not new ML forecasts.
- Read actual existing inventory, route distance/transport/net-return estimates, weather and cold-storage records. Ambiguous inventory/variety/grade selections trigger clarification.
- Retain structured follow-up context in sessionStorage for this tab. Restored context older than 30 minutes is discarded. Clear removes it. New page selections take precedence when changed.
- Speak English, Hindi and Kannada through existing Edge TTS, with compatible installed browser voices as fallback. Mute, Replay and Stop are available.

Cardamom has no connected official price feed. No service provides a verified SELL/WAIT/STORE decision; the assistant states that limitation instead of inventing advice. Market rankings require comparable varieties, units and observation dates. Weather/storage records and transport estimates retain the limitations of their existing services.

## Speech and costs

No paid API, LLM, new dependency or credentials are required.

The default local speech model is now **large-v3-turbo**, using the existing faster-whisper library, CPU int8, six CPU threads at most and bounded decoding. Existing `CROPMANDI_WHISPER_MODEL` settings in the process environment or root `.env` override this default. Small/base were tested and performed poorly on Kannada in the sample benchmark.

The free model cache is inside `cropmandi_voice_assistant/.models/` and is ignored by the voice-local `.gitignore`. This machine contains the turbo model and the small model used for comparison (about 2 GB total). On another machine the selected model downloads once on first use. Thereafter speech input can run offline. The original root dependency pins, including PyAV, are preserved.

| Setting | Required? | Meaning |
| --- | --- | --- |
| `CROPMANDI_WHISPER_MODEL` | No; existing setting | Optional model name/path. Default `large-v3-turbo`. An existing `base` setting will continue to select base until changed. |
| `CROPMANDI_VOICE_MODEL_DIR` | No; new optional setting | Alternate model cache directory. Default is `.models` inside this voice package. |

Edge TTS uses the existing free online service: `en-IN-NeerjaNeural`, `hi-IN-SwaraNeural`, `kn-IN-SapnaNeural`. Answer text is sent to that service. On-device fallback depends on installed language voices. No external LLM or paid speech provider is called.

Select **Kannada** or **Hindi** for best results in those languages. Auto mode is optional: a short Kannada benchmark was misidentified as Tamil, so the widget asks for a supported language instead of executing it. Suspicious/low-confidence transcripts are placed in the text box for review and manual sending. Indian accents, noisy environments and real microphones still require user acceptance testing; synthetic speech is not a substitute for that.

## Start normally

Run the existing backend **from this duplicated project**, using its normal dependencies and database configuration:

```sh
.venv/bin/python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8001
```

Serve `frontend/` using the project's existing frontend startup procedure. Restart the duplicated backend and hard-refresh the frontend after the changes. The assistant retains the existing port-8001 configuration. Do not stop an original-project server without checking which process it is. No pre-existing user server was stopped during this work.

The optional validation server can serve a separate instance on port 8766 without editing frontend configuration files. It rewrites port strings only in HTTP responses. For safe QA, set `DATABASE_URL` to a read-only URI for the duplicate database before starting it:

```sh
.venv/bin/python -m uvicorn cropmandi_voice_assistant.tests.validation_server:app --host 127.0.0.1 --port 8766
```

That server is a QA helper, not a new product feature or replacement prediction service.

## Endpoint contracts and limits

- `GET /api/voice/health` — voice service metadata.
- `POST /api/voice/transcribe` — multipart `audio` and `language` (`en-IN`, `hi-IN`, `kn-IN`, `auto`); returns transcript, language, model and `needs_confirmation`.
- `POST /api/voice/command` — JSON `text`, `language`, `client_date`, `context`; returns text/spoken answer, structured context, verified navigation action and relevant genuine service records.
- `POST /api/voice/speak` — JSON `text`, `language`; returns MP3.

Browser recordings stop at 30 seconds. The backend rejects decoded clips over 35 seconds and uploads over 15 MB. One transcription runs at a time per backend process. Server timeouts are 90 seconds for transcription, 40 for commands and 12 for synthesis; browser limits are slightly longer. Timed-out worker operations can finish in the background, but stale results cannot update the widget or restart speech. New questions, close, language changes and page exit cancel pending browser work and release microphone tracks.

## HarvestRoute boundary

Only two lines were added to `frontend/cropmandi_ai_harvest_route/code.html`: the assistant stylesheet in the head and its deferred script before the body closes. The page previously included neither; without these lines the assistant would not appear there. No existing HarvestRoute element, script, stylesheet, route, calculation or business logic was changed. A regression test removes those two lines and checks byte-for-byte equality with the original HTML.

## Validation

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest cropmandi_voice_assistant/tests -q -p no:cacheprovider
node --test cropmandi_voice_assistant/tests/widget.test.cjs
```

For the full project tests, use a populated disposable database copy rather than the working database: some existing tests perform CRUD and write prediction history. The added real-data voice tests open the actual dataset read-only. See `ENHANCEMENTS_REPORT.md` and `VALIDATION_RESULTS.txt` for the final results and complete file list.

## Multilingual retest follow-up

See `KANNADA_DATE_FIX_REPORT.md` for the latest 323-Python/15-widget test run. The previously failing Kannada historical-date recording now resolves automatically through guarded local Whisper/IndicConformer date recovery, and returns the actual stored price without transcript edits. English/Hindi historical input and Kannada navigation/prediction/follow-up passed live audio regression checks. Unreadable or conflicting dates still require clarification. See `KANNADA_ASR_MODEL.md` for optional local model setup and attribution; no paid API or new environment variable is required. The original server remains untouched, and the fixed duplicate runs on port 8766. `RETEST_RESULTS.md` preserves the earlier baseline and its limitations.
