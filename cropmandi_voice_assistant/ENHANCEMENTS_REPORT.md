# Voice Assistant enhancement delivery — 7 November 2026

All changes are inside CropMandi_Enhancements. The original project was not modified. No paid API, new dependency, shared API/schema/model/business-logic change or project-wide refactor was introduced.

## Delivered behavior

- Multilingual navigation to actual Dashboard, My Crops, HarvestRoute, Mandi Price AI, Analytics, Settings, Calendar and Alerts pages, existing dashboard section anchors, and a previously visited CropMandi page. The client validates destinations and prevents navigation to arbitrary/nonexistent pages.
- Exact-date/latest-recorded price lookups for supported coffee, pepper, rice, paddy, tomato, potato and maize data. Retains source currency, units, dates and unverified-data warnings. A missing date/market never becomes a nearby date, another market or a configured benchmark price.
- Matching historical price comparisons, Hindi/Kannada month names and numerals, ambiguity clarification, invalid-date rejection and decimal quantities.
- Existing ExtraTrees market-level recursive forecasts, including next-week requests, with input dates and prediction labels. Coffee/pepper answers identify last-value baselines. No prediction engine was added.
- Structured follow-up memory, actual page selections, JSON variety/grade selections, selected forecast dates, inventory ambiguities, origin, quantity units, transport mode and vehicle ownership. Reading context does not change any page form or result card.
- Genuine inventory, existing HarvestRoute distance/cost/net-return estimates, live weather and cold-storage records. No new SELL/WAIT/STORE rules were invented.
- Existing floating interface retained, adding Auto language choice, Mute and Replay; Stop retained and repaired. New questions, close, language changes and page exit cancel stale browser work. Added recording/decoding limits, server/client timeouts, microphone cleanup and transcript review safeguards.

## Speech stack, cost and measured results

Existing faster-whisper 1.2.1 and Edge TTS dependencies are reused. No LLM or paid provider. Default local model is now large-v3-turbo, CPU int8, at most six threads. Existing process/root-.env CROPMANDI_WHISPER_MODEL overrides remain authoritative. Free turbo and small comparison caches are inside this voice package (about 2 GB total), ignored by its own .gitignore.

Real Edge TTS synthesized generic samples; real local Whisper transcribed those audio bytes:

| Language | Turbo result | Approximate time |
| --- | --- | --- |
| English | Correct: What is the coffee price at Hassan? | 9.36 s, including initial load |
| Hindi | Correct: मुझे आज का कॉफी का भाव बताओ। | 7.03 s |
| Kannada, explicitly selected | Recognizable Kannada with phonetic errors: ಇವತ್ತಿನ ಕಾಪಿ ಬಿಲೆಯೆಷ್ಟು, ಇವತ್ತಿನ ಕಾಪಿ ಬಿಲೆಯೆಷ್ಟು. Narrow aliases recover coffee, price and today. | 10.35 s |

Base/small performed poorly on the same Kannada sample and were not selected. Auto mode misidentified one Kannada sample as Tamil (17.5 s). The widget rejects unsupported detected languages and asks the user to choose a supported language. Choose Kannada explicitly for better results. Wrong-script, low-confidence, highly repetitive or potentially truncated transcripts require review before execution.

Real Edge TTS returned audio in all three languages. Human accents, noisy field recordings and physical microphone capture were not validated. Permission denial, pending/late permission, unsupported microphone/browser APIs, interruption, network timeout, duplicates and stale audio were exercised in deterministic widget tests. Physical microphone/cross-browser acceptance testing remains a user validation step.

## Validation

- Combined Python regression run: 283 passed (208 pre-existing project tests + 75 voice tests at that point).
- Final voice suite after two additional edge cases: 77 passed.
- Widget lifecycle tests: 14 passed.
- JavaScript syntax and git diff whitespace checks passed.
- Read-only real observations for all four ML crops matched exact database prices/dates. Missing date/market cases were rejected.
- Existing Kolar tomato forecast for 8 November 2026: INR 1,310.73/quintal, input date 26 October 2026. Matched the actual Mandi Price AI model function and was labelled a recursive market estimate.
- Browser verification: widget on actual HarvestRoute; 15 October 2026 Kolar tomato observation of INR 800/quintal displayed in English, Hindi and Kannada; speech stop/mute, forecast follow-up, navigation to Mandi Price AI and return to HarvestRoute.
- Live route sample: 79 km, estimated INR 1,422 transport and INR 281,107 net return for 500 kg coffee, using existing services. Price date was 18 November 2025, explicitly historical. Separate regression checks used real price/vehicle/net calculations with only network distance lookup mocked.
- Live weather sample: Hassan, 19.3 C, 99% humidity, overcast; a point-in-time observation.
- Existing storage records: Shri Anand Cold Storage near Hassan, listed capacity 7,071.49 MT. No claim of live available space, current operation or verified crop compatibility.

The full suite initially ran against an empty disposable database and exposed six data/seed-dependent failures. Rerunning against a populated disposable copy passed. No unrelated code was changed to suppress failures. Added real-data voice tests open the working database read-only; full-suite CRUD/prediction writes went to the disposable copy, removed after testing.

Working database SHA256 was identical before/after regression and at delivery:

681bedde9da069e26efa302723aee709ca9c18e9f17478ba774643e1e8332db8

Its modification time remains 6 November 2026, 06:55:55. No pre-existing user server was stopped; the process on port 8001 was left untouched. Separate QA instances used ports 8765/8766.

## Boundaries and limitations

The only change outside voice-related files is the approved two-line HarvestRoute HTML integration: the assistant stylesheet include and deferred script include. The page previously loaded neither, so these are necessary for the widget to appear there. A regression test removes those two lines and checks equality with the original HTML. Existing HarvestRoute UI, scripts, styles, routes, calculations and business logic were not edited.

Dashboard, navigation components, other page files, shared APIs, ML artifacts/pipelines, authentication, schemas and business services remain unchanged. The pre-existing untracked PROJECT_DOCUMENTATION.md was preserved and is excluded from the created-file list.

The existing four-crop database ends on 30 October 2026; pepper production observations end on 26 October 2026. Explicit today queries may have no result. Cardamom's feed remains unavailable. Forecasts are existing market-level experimental estimates, not grade-specific models; targets over 31 days after the last input are refused. Coffee/pepper remain baselines. No connected service provides a verified SELL/WAIT/STORE decision, so the assistant states that limitation. Some rankings cannot be compared because source dates/units differ. Free Edge TTS needs internet; offline speech requires a matching installed device voice. Automatic Kannada detection remains unreliable in the short sample tested.

## Setup and configuration

Restart the duplicated backend from this project folder and hard-refresh the frontend. No required new environment variable or API key. Existing CROPMANDI_WHISPER_MODEL can override the default; change an existing base override to large-v3-turbo to use the tested model. New optional CROPMANDI_VOICE_MODEL_DIR controls cache location; its default stays inside this voice package. No dependency file was changed. See the updated voice README for commands and optional read-only QA-server instructions.

## Complete file list

### Modified — 10 files

- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/README.md`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/intent_parser.py`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/project_adapter.py`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/routes.py`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/speech_engine.py`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/static/voice-assistant.css`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/static/voice-assistant.js`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/frontend/cropmandi_ai_harvest_route/code.html`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/frontend/js/voice-assistant.js`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/frontend/styles/voice-assistant.css`

### Created — 7 source/documentation files

- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.gitignore`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/assistant_service.py`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/tests/test_enhancements.py`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/tests/validation_server.py`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/tests/widget.test.cjs`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/VALIDATION_RESULTS.txt`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/ENHANCEMENTS_REPORT.md`

### Deleted source files

None. Only the disposable database generated for validation was removed. No pre-existing file was deleted.

### Generated model cache

39 generated cached files/symlinks are runtime assets, listed separately from source/documentation changes and excluded from Git by the voice-local ignore file:

- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/.locks/models--Systran--faster-whisper-small/3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671.lock`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/.locks/models--Systran--faster-whisper-small/7818adb6de9fa3064d3ff81226fdd675be1f6344.lock`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/.locks/models--Systran--faster-whisper-small/c9074644d9d1205686f16d411564729461324b75.lock`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/.locks/models--Systran--faster-whisper-small/e5047537059bd8f182d9ca64c470201585015187.lock`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/.locks/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/0351d1d6870005e865747b781b5d7c23ea0459cd.lock`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/.locks/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/0adcd01e7c237205d593b707e66dd5d7bc785d2d.lock`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/.locks/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/17456db595adc78a973f97d69d8cb50bc87c0b1c.lock`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/.locks/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/931c77a740890c46365c7ae0c9d350ba3cca908f.lock`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/.locks/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da.lock`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/CACHEDIR.TAG`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/blobs/.huggingface-shared-blobs`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/blobs/42/429ffc84492c1122da005d7274fc397bf142fe12066eb7e4612dc25c579db2ea`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/blobs/42/429ffc84492c1122da005d7274fc397bf142fe12066eb7e4612dc25c579db2ea.lock`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/blobs/42/429ffc84492c1122da005d7274fc397bf142fe12066eb7e4612dc25c579db2ea.refs`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/blobs/b5/b5de55e781fd93b7d472c8ca3f7d40d870a3be764f8bb1a9c4a0511c55f9ca5b`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/blobs/b5/b5de55e781fd93b7d472c8ca3f7d40d870a3be764f8bb1a9c4a0511c55f9ca5b.lock`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/blobs/b5/b5de55e781fd93b7d472c8ca3f7d40d870a3be764f8bb1a9c4a0511c55f9ca5b.refs`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/models--Systran--faster-whisper-small/blobs/3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/models--Systran--faster-whisper-small/blobs/7818adb6de9fa3064d3ff81226fdd675be1f6344`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/models--Systran--faster-whisper-small/blobs/c9074644d9d1205686f16d411564729461324b75`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/models--Systran--faster-whisper-small/blobs/e5047537059bd8f182d9ca64c470201585015187`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/models--Systran--faster-whisper-small/refs/main`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/models--Systran--faster-whisper-small/snapshots/536b0662742c02347bc0e980a01041f333bce120/config.json`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/models--Systran--faster-whisper-small/snapshots/536b0662742c02347bc0e980a01041f333bce120/model.bin`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/models--Systran--faster-whisper-small/snapshots/536b0662742c02347bc0e980a01041f333bce120/tokenizer.json`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/models--Systran--faster-whisper-small/snapshots/536b0662742c02347bc0e980a01041f333bce120/vocabulary.txt`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/models--Systran--faster-whisper-small/trees/536b0662742c02347bc0e980a01041f333bce120.json`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/blobs/0351d1d6870005e865747b781b5d7c23ea0459cd`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/blobs/0adcd01e7c237205d593b707e66dd5d7bc785d2d`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/blobs/17456db595adc78a973f97d69d8cb50bc87c0b1c`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/blobs/931c77a740890c46365c7ae0c9d350ba3cca908f`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/blobs/e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/refs/main`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/snapshots/0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf/config.json`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/snapshots/0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf/model.bin`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/snapshots/0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf/preprocessor_config.json`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/snapshots/0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf/tokenizer.json`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/snapshots/0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf/vocabulary.json`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/trees/0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf.json`
