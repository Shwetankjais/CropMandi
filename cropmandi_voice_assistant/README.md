# CropMandi Voice Assistant — integrated FastAPI version

This package is mounted into the main CropMandi FastAPI application. The main API remains the single service on port **8001**; do not start `cropmandi_voice_assistant.main:app` when using the integrated project.

## What is integrated

- Browser speech input and spoken replies in Hindi (`hi-IN`), English (`en-IN`) and Kannada (`kn-IN`).
- A floating widget added to the existing frontend pages.
- `POST /api/voice/command` and `GET /api/voice/health` registered on `apps.api.main:app`.
- Price lookup connected to the existing CropMandi market-centre records and series-based price history.
- Navigation to the existing dashboard sections, settings page and home page.

Speech recognition records audio in the browser and transcribes it locally with `faster-whisper` through the FastAPI endpoint. It does not use the browser Web Speech recognition service. No `PyAudio` package is required. Use Chrome or Edge on `localhost` or HTTPS and allow microphone permission.

## Run the combined project

From the project root in Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env`. If PostgreSQL/Docker is not running, configure a local SQLite database as documented in the project root README:

```dotenv
DATABASE_URL=sqlite:///./data/cropmandi.db
```

Start the existing FastAPI application from the project root:

```powershell
python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8001
```

Then open the API docs at `http://127.0.0.1:8001/docs` and check `GET /api/voice/health`.

In a second PowerShell terminal, serve the frontend directory so the static navigation URLs resolve:

```powershell
Set-Location frontend
python -m http.server 5500
```

Open `http://127.0.0.1:5500/` and navigate to the dashboard. The voice assistant button appears in the page corner. The widget calls the same FastAPI service on port 8001.

## API quick test

```powershell
$body = @{
  text = "What was the coffee price at Chikkamagaluru on 7 August 2026?"
  language = "en-IN"
  client_date = "2026-10-27"
  context = @{ crop = "coffee"; variety = "Arabica Parchment"; market = "Chikkamagaluru" }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8001/api/voice/command `
  -ContentType "application/json" -Body $body
```

Change the date, location and variety to records actually available in the project's data. The assistant does not invent a value when no matching record exists. For some unverified local market-centre workbooks, multiple matching entries are summarized by their median and identified as a summary in the response metadata. Prices are spoken using the source unit when supplied; the assistant does not assume every commodity is priced per quintal.

## Supported price data

The current CropMandi API has data paths for **Coffee, Pepper and Rice**. Coffee local market-centre data can be marked unverified/experimental. Pepper local workbook values may not supply a unit; in that case the reply clearly says the unit is unspecified. Rice market prices come from the API's DB-backed observations. Other crop names may be recognized by the parser but will not return a price unless a supported data source exists.

## Files

- `main.py`: standalone app retained for isolated development; not needed for the integrated run command.
- `routes.py`: multilingual command endpoint and response formatting.
- `intent_parser.py`: rule-based command parsing and language aliases.
- `project_adapter.py`: adapter connecting commands to the existing CropMandi price data.
- `adapters.py`: CSV adapter retained for standalone use and tests.
- `static/`: original widget files; active integrated copies are in `frontend/js` and `frontend/styles`.
- `tests/`: parser, route and adapter tests.

## Tests

Run all tests from the project root:

```powershell
python -m pytest -q
```

Or only voice-assistant tests:

```powershell
python -m pytest cropmandi_voice_assistant/tests -q
```

## Privacy and deployment notes

The browser asks for microphone permission only after the user presses **Speak**. Recorded input is sent to the project’s own FastAPI server and transcribed locally after the model is cached. For spoken answers, text is sent to the Edge neural TTS service; use text-only mode or change the TTS implementation if you do not want reply text sent to that service. For deployment, use HTTPS and restrict CORS origins to trusted frontend domains. Update the fixed `endpoint` in each page's `window.CropMandiVoiceConfig` if the API is hosted at a different origin. The integrated widget uses the current project's relative static URLs and is intended to be served with `frontend/` as the web root.


## Fixing multilingual voice input/output

The current widget deliberately does **not** depend on `SpeechRecognition` for input, because Chromium-family browsers may use a remote recognition service that can fail with a `network` error. It records a short clip in the browser and posts it to `POST /api/voice/transcribe`. The FastAPI server uses `faster-whisper` on the local CPU.

### Install

From the project root (inside the activated virtual environment):

```powershell
python -m pip install -r requirements.txt
```

The first transcription needs internet once to download the Whisper `base` model into the local cache. After that, transcription runs locally. The root requirements pin `av==18.1.0` because the installed `faster-whisper==1.2.1` code path in this project is incompatible with PyAV 19 (`av.open(..., metadata_errors="ignore")` raises `TypeError`). Keep this pin when updating dependencies. Change `CROPMANDI_WHISPER_MODEL` in `.env` to `small` for better accuracy if your computer has enough RAM and you can afford a larger model download. `tiny` is smaller/faster but may be less accurate for Kannada and Hindi. Restart Uvicorn after changing the setting.

### Speech output

`POST /api/voice/speak` returns an MP3 using these Edge neural voices: `en-IN-NeerjaNeural`, `hi-IN-SwaraNeural`, and `kn-IN-SapnaNeural`. Edge TTS requires an internet connection. If the service cannot be reached, the frontend tries a locally installed browser voice. If Windows has no Hindi or Kannada voice installed and Edge TTS is unreachable, the answer remains visible as text.

### Endpoints

- `GET /api/voice/health` — service health and supported language list.
- `POST /api/voice/transcribe` — multipart fields `audio` and `language` (`en-IN`, `hi-IN`, or `kn-IN`); returns a transcript.
- `POST /api/voice/command` — existing intent/price/navigation handler.
- `POST /api/voice/speak` — JSON body `{"text":"...", "language":"kn-IN"}`; returns `audio/mpeg`.

### Test it

Open `/docs` on the FastAPI server. You can test `/api/voice/health` and `/api/voice/command` without microphone access. Test `/api/voice/transcribe` using a short recording in the selected language, and `/api/voice/speak` with Hindi/Kannada text. The browser microphone is available only on localhost or a secure HTTPS origin, and site microphone permission must be allowed.
