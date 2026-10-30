"""Standalone FastAPI application for the CropMandi voice assistant.

Run from the CropMandi project root with:
    python -m uvicorn cropmandi_voice_assistant.main:app --reload --host 127.0.0.1 --port 8001
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import create_voice_router, make_csv_price_lookup

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(os.getenv("CROPMANDI_PROJECT_ROOT", Path.cwd())).resolve()

_default_origins = [
    "http://127.0.0.1:5000",
    "http://localhost:5000",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]
_allowed_origins = [
    origin.strip()
    for origin in os.getenv("CROPMANDI_ALLOWED_ORIGINS", ",".join(_default_origins)).split(",")
    if origin.strip()
]

app = FastAPI(
    title="CropMandi Multilingual Voice Assistant",
    description="Voice command and crop-price lookup API for English, Hindi, and Kannada.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

price_lookup = make_csv_price_lookup(project_root=PROJECT_ROOT)
app.include_router(create_voice_router(price_lookup=price_lookup))
app.mount("/voice-static", StaticFiles(directory=str(PACKAGE_DIR / "static")), name="voice-static")


@app.get("/", tags=["service"])
def root() -> dict[str, str]:
    return {
        "service": "CropMandi Voice Assistant API",
        "docs": "/docs",
        "health": "/api/voice/health",
    }
