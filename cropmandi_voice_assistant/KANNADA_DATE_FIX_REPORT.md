# Kannada historical-date recognition fix — 7 November 2026

The previously failing saved Kannada clip now runs automatically, without manual
transcript changes: `2026-10-15 ಕೋಲಾರದಲ್ಲಿ ಟೊಮೆಟೊ ಬೆಲೆ ಎಷ್ಟು`.
The live duplicate returned the actual local Kolar tomato record, INR 800/quintal,
15 October 2026. The response retains the project's unverified-data label.
`needs_confirmation` is false for this recording. Live recognition took 12.27 s.

## Implementation

Whisper remains the primary recognizer. For Kannada calendar questions with a
recognized day and missing/corrupted year, an optional local Kannada
IndicConformer CTC decoder supplies an independent transcript. The recovery code
requires the same month, an explicit recognized year, agreement on any overlapping
day/year, valid calendar date, adequate secondary confidence, and a recognized
commodity and market. Conflicting known crop/market also blocks recovery.
Low-quality/truncated primary audio cannot bypass confirmation. Missing optional
model files retain the existing clarification path. No current-year default,
known database date, expected price or hardcoded test date supplies a missing slot.
The API retains both original transcripts and calendar evidence for diagnosis.
A common Kannada spelling `ಟೊಮೆಟೊ` now maps to the existing tomato commodity.

The secondary model is the pinned AI4Bharat Kannada 120M ONNX export, approximately
493 MB, using the already installed ONNX Runtime 1.31.1 and NumPy. No project-wide
dependency was installed, upgraded or replaced; the voice-only requirements now
explicitly declare ONNX Runtime. No paid API or account is required. Recognition
is local, including this fallback. Existing Edge TTS is unchanged. Model source,
license attribution, pinned revision and offline setup are in KANNADA_ASR_MODEL.md.
No new environment variables are required. This duplicate already has the model.

## Validation

- 323 Python tests passed, including 20 new date-recovery regressions.
- 15 existing widget lifecycle tests passed.
- Full-suite writes used a disposable populated database copy, deleted afterward.
- Six live audio-to-command checks passed: Kannada historical/navigation/tomorrow/
  next-week, plus English and Hindi historical price input. All used the actual
  duplicate backend and existing price/prediction services.
- The original saved Kannada historical clip needed no transcript editing.
- Additional recorded Kannada questions for 16 October 2026 and 7 August 2026
  automatically resolved correctly, proving different days/months are supported.
- An additional 20 October 2025 recording remained unresolved: both recognizers
  damaged the spoken year. It did not become a guessed 2026 lookup. Repeating a
  clearer full date is still necessary for audio whose year neither model reads.
  Thus additional held-out recorded dates passed 2/3; universal accuracy is not
  claimed. Unit tests also cover other years, leap day and conflicting evidence.
- Conflicting day/year/month, missing year/day/crop/market, invalid calendar dates,
  mixed-script secondary text, and low confidence cannot authorize recovery.
- Inputs were synthesized recordings, not physical microphone capture. Human
  accents/noise and microphone acceptance testing remain for the user.
- Frontend/HarvestRoute files were not changed in this fix. Browser page remains
  available at http://127.0.0.1:8766/cropmandi_ai_harvest_route/code.html.

## Isolation

Only duplicate server 8766 was restarted (PID 48708). Original port-8001 processes
26062 and 33906 are unchanged. No original-project files, shared services,
agricultural models, routes, schemas, HarvestRoute UI/calculations or other modules
were modified. Working database SHA256 remains:

`681bedde9da069e26efa302723aee709ca9c18e9f17478ba774643e1e8332db8`

## Complete file manifest for this fix

Modified source/documentation files (all under this voice package):

- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/speech_engine.py`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/intent_parser.py`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/requirements.txt`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/README.md`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/VALIDATION_RESULTS.txt`

Created source/documentation files:

- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/kannada_asr.py`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/tests/test_kannada_date_recovery.py`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/KANNADA_ASR_MODEL.md`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/KANNADA_DATE_FIX_REPORT.md`

Deleted source/documentation files: none.

Created or updated runtime evidence/logs (existing server PID/log updated; other
listed artifacts created in this fix):

- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/indicconformer-kn-padding.json`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/kannada-date-baseline.json`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/kannada-date-fixed.json`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/kannada-date-heldout/2025-10-20.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/kannada-date-heldout/2026-08-07.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/kannada-date-heldout/2026-10-16.mp3`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/kannada-date-heldout-results.json`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/kannada-date-live-validation.json`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/kannada-date-regression-results.txt`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/server-8766.log`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.runtime/server-8766.pid`

Downloaded local model and download metadata (all new, voice package only):

- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/indicconformer-kn/.cache/huggingface/.gitignore`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/indicconformer-kn/.cache/huggingface/CACHEDIR.TAG`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/indicconformer-kn/.cache/huggingface/download/README.md.lock`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/indicconformer-kn/.cache/huggingface/download/README.md.metadata`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/indicconformer-kn/.cache/huggingface/download/kn/model.onnx.lock`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/indicconformer-kn/.cache/huggingface/download/kn/model.onnx.metadata`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/indicconformer-kn/.cache/huggingface/download/kn/vocab.json.lock`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/indicconformer-kn/.cache/huggingface/download/kn/vocab.json.metadata`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/indicconformer-kn/README.md`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/indicconformer-kn/kn/model.onnx`
- `/Users/shwetankjaiswal/Downloads/Final_merger/CropMandi_Enhancements/cropmandi_voice_assistant/.models/indicconformer-kn/kn/vocab.json`
