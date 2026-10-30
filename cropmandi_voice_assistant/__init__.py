"""CropMandi multilingual voice assistant package for FastAPI."""
from .adapters import make_csv_price_lookup
from .intent_parser import parse_command, detect_language
from .routes import create_voice_router

__all__ = ["create_voice_router", "make_csv_price_lookup", "parse_command", "detect_language"]
__version__ = "2.0.0"
