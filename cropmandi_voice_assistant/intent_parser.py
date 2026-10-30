"""Lightweight multilingual intent parsing for CropMandi Voice Assistant v1.

This module intentionally has no NLP/model dependency. It supports a useful set
of structured commands in English, Hindi, and Kannada and can be extended with
more aliases as the product grows.
"""
from __future__ import annotations

import calendar
import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any

SUPPORTED_LANGUAGES = {"en-IN": "en", "hi-IN": "hi", "kn-IN": "kn"}

CROPS: dict[str, tuple[str, ...]] = {
    "coffee": ("coffee", "कॉफी", "ಕಾಫಿ"),
    "pepper": ("pepper", "black pepper", "काली मिर्च", "ಮೆಣಸು", "ಕರಿಮೆಣಸು"),
    "cardamom": ("cardamom", "elaichi", "इलायची", "ಏಲಕ್ಕಿ"),
    "rice": ("rice", "paddy", "चावल", "धान", "ಅಕ್ಕಿ", "ಭತ್ತ"),
    "wheat": ("wheat", "गेहूं", "ಗೋಧಿ"),
    "cotton": ("cotton", "कपास", "ಹತ್ತಿ"),
    "sugarcane": ("sugarcane", "गन्ना", "ಕಬ್ಬು"),
}

STATES: dict[str, tuple[str, ...]] = {
    "Karnataka": ("karnataka", "कर्नाटक", "ಕರ್ನಾಟಕ"),
    "Rajasthan": ("rajasthan", "राजस्थान", "ರಾಜಸ್ಥಾನ"),
    "Tamil Nadu": ("tamil nadu", "तमिलनाडु", "ತಮಿಳುನಾಡು"),
    "Kerala": ("kerala", "केरल", "ಕೇರಳ"),
    "Andhra Pradesh": ("andhra pradesh", "आंध्र प्रदेश", "ಆಂಧ್ರ ಪ್ರದೇಶ"),
    "Madhya Pradesh": ("madhya pradesh", "मध्य प्रदेश", "ಮಧ್ಯಪ್ರದೇಶ"),
}

DISTRICTS: dict[str, tuple[str, ...]] = {
    "Chikkamagaluru": ("chikkamagaluru", "chikmagalur", "ಚಿಕ್ಕಮಗಳೂರು", "चिक्कमगलूरु"),
    "Mysuru": ("mysuru", "mysore", "ಮೈಸೂರು", "मैसूरु", "मैसूर"),
    "Hassan": ("hassan", "ಹಾಸನ", "हासन"),
    "Sakleshpur": ("sakleshpur", "ಸಕಲೇಶಪುರ", "सकलेशपुर"),
    "Kodagu": ("kodagu", "coorg", "ಕೊಡಗು", "कोडगु"),
    "Bengaluru": ("bengaluru", "bangalore", "ಬೆಂಗಳೂರು", "बेंगलुरु"),
}

MARKETS: dict[str, tuple[str, ...]] = {
    # Local market-centre locations supported by the current CropMandi dashboard.
    "Chikkamagaluru APMC": (
        "chikkamagaluru apmc", "chikmagalur apmc", "chikkamagaluru mandi",
        "chikmagalur mandi", "chikkamagaluru", "chikmagalur", "chikmagaluru",
        "ಚಿಕ್ಕಮಗಳೂರು ಎಪಿಎಂಸಿ", "ಚಿಕ್ಕಮಗಳೂರು ಮಂಡಿ", "ಚಿಕ್ಕಮಗಳೂರು",
        "चिक्कमगलूरु मंडी", "चिक्कमगलूरु एपीएमसी", "चिक्कमगलूरु",
    ),
    "Mysore APMC": ("mysore apmc", "mysuru apmc", "mysore mandi", "mysuru mandi", "mysuru", "mysore", "ಮೈಸೂರು ಎಪಿಎಂಸಿ", "ಮೈಸೂರು ಮಂಡಿ", "मैसूरु", "मैसूर"),
    "Hassan": ("hassan apmc", "hassan mandi", "hassan", "ಹಾಸನ ಎಪಿಎಂಸಿ", "ಹಾಸನ ಮಂಡಿ", "ಹಾಸನ", "हासन"),
    "Sakleshpur": ("sakleshpur apmc", "sakleshpur mandi", "sakleshpur", "ಸಕಲೇಶಪುರ ಮಂಡಿ", "ಸಕಲೇಶಪುರ", "सकलेशपुर"),
    "Ballupete": ("ballupete", "ballupet"),
    "Balupet": ("balupet", "ಬಲೂಪೆಟ್"),
    "Somwarpet": ("somwarpet", "somwarpete", "somawarpet", "ಸೋಮವಾರಪೇಟೆ", "कोडगु सोमवरपेट"),
    "Kushalnagar": ("kushalnagar", "kushalnagara", "ಕುಶಾಲನಗರ", "कुशलनगर"),
    "Madikeri": ("madikeri", "ಮಡಿಕೇರಿ", "मडिकेरी"),
    "Mudigere": ("mudigere", "ಮೂಡಿಗೆರೆ", "मुदिगेरे"),
    "Mangalore": ("mangalore", "mangaluru", "ಮಂಗಳೂರು", "मंगलूरु"),
    "Mysuru": ("mysuru", "ಮೈಸೂರು", "मैसूरु", "मैसूर"),
    "Gonikoppa": ("gonikoppa", "ಗೋಣಿಕೊಪ್ಪ", "गोनिकोप्पा"),
    "Goa": ("goa", "ಗೋವಾ", "गोवा"),
    "Gendehalli": ("gendehalli", "ಗೆಂಡೆಹಳ್ಳಿ"),
    "Gudugalale": ("gudugalale", "ಗುಡುಗಳಲೆ"),
    "Hanbalu": ("hanbalu", "ಹನಬಾಳು"),
    "Hosathota": ("hosathota", "ಹೊಸತೋಟ"),
    "Idukki": ("idukki", "ഇടുക്കി", "इडुक्की"),
    "Kodlipete": ("kodlipete", "ಕೊಡ್ಲಿಪೇಟೆ"),
    "Shanivarasanthe": ("shanivarasanthe", "ಶನಿವಾರಸಂತೆ"),
    "Suntikoppa": ("suntikoppa", "ಸೋಂಟಿಕೊಪ್ಪ"),
    "Theni": ("theni", "தேனி", "थेनी"),
    "Puttur": ("puttur", "ಪುತ್ತೂರು", "पुत्तूर"),
    "Kadaba": ("kadaba", "ಕಡಬ", "कडबा"),
    "Kalasa": ("kalasa", "ಕಳಸ", "कलसा"),
    "Karkala": ("karkala", "ಕಾರ್ಕಳ", "कार्कला"),
    "Kumbarahalli": ("kumbarahalli", "ಕುಂಭರಹಳ್ಳಿ"),
    "Kuniganahalli": ("kuniganahalli", "ಕುನಿಗನಹಳ್ಳಿ"),
    "Makkandur": ("makkandur", "ಮಕ್ಕಂದೂರು"),
    "Pattadur": ("pattadur", "ಪಟ್ಟದೂರು"),
    "Siddapur": ("siddapur", "ಸಿದ್ದಾಪುರ", "सिद्धापुर"),
    "Sirsi": ("sirsi", "ಸಿರ್ಸಿ", "सिरसी"),
    "Chikmagalur": ("chikmagalur", "ಚಿಕ್ಕಮಗಳೂರು", "चिक्कमगलूरु"),
    # Series names in the API are accepted as selectors when the user names them.
    "Arabica Parchment": ("arabica parchment", "अरबिका पार्चमेंट", "ಅರೇಬಿಕಾ ಪಾರ್ಚ್ಮೆಂಟ್"),
    "Arabica Cherry": ("arabica cherry", "ಅರೇಬಿಕಾ ಚೆರಿ"),
    "Robusta Parchment": ("robusta parchment", "ರೋಬಸ್ಟಾ ಪಾರ್ಚ್ಮೆಂಟ್"),
    "Robusta Cherry": ("robusta cherry", "ರೋಬಸ್ಟಾ ಚೆರಿ"),
    "Cochin Garbled": ("cochin garbled", "ಕೊಚ್ಚಿನ್ ಗಾರ್ಬಲ್ಡ್"),
    "Cochin Ungarbled": ("cochin ungarbled", "ಕೊಚ್ಚಿನ್ ಅನ್‌ಗಾರ್ಬಲ್ಡ್"),
    "Bodinayakanur": ("bodinayakanur", "बोडिनायक्कनूर"),
    "Kumily": ("kumily", "കുമളി", "കുമളി മാർക്കറ്റ്"),
    "Vandanmedu": ("vandanmedu", "വണ്ടൻമേട്"),
}

SERIES_ALIASES: dict[str, tuple[str, ...]] = {
    "Arabica Parchment": ("arabica parchment", "ಅರೇಬಿಕಾ ಪಾರ್ಚ್ಮೆಂಟ್", "अरबिका पार्चमेंट"),
    "Arabica Cherry": ("arabica cherry", "ಅರೇಬಿಕಾ ಚೆರಿ"),
    "Robusta Parchment": ("robusta parchment", "ರೋಬಸ್ಟಾ ಪಾರ್ಚ್ಮೆಂಟ್"),
    "Robusta Cherry": ("robusta cherry", "ರೋಬಸ್ಟಾ ಚೆರಿ"),
    "Cochin Garbled": ("cochin garbled", "ಕೊಚ್ಚಿನ್ ಗಾರ್ಬಲ್ಡ್"),
    "Cochin Ungarbled": ("cochin ungarbled", "ಕೊಚ್ಚಿನ್ ಅನ್‌ಗಾರ್ಬಲ್ಡ್"),
    "Sirsi": ("sirsi", "ಸಿರ್ಸಿ", "सिरसी"),
}


PRICE_WORDS = (
    "price", "rate", "modal price", "market price", "mandi bhav", "bhaav", "bhav",
    "कीमत", "दाम", "भाव", "मंडी", "दर", "ಬೆಲೆ", "ದರ", "ಮಾರುಕಟ್ಟೆ", "ಮಂಡಿ",
)
WEATHER_WORDS = ("weather", "rain", "forecast", "मौसम", "बारिश", "ಹವಾಮಾನ", "ಮಳೆ")
STORAGE_WORDS = (
    "cold storage", "storage nearby", "nearby storage", "storage facility",
    "कोल्ड स्टोरेज", "शीतगृह", "भंडारण", "शीत भंडारण", "ಶೀತಗೃಹ", "ಕೋಲ್ಡ್ ಸ್ಟೋರೇಜ್", "ಸಂಗ್ರಹಣೆ",
)
RECOMMEND_WORDS = (
    "should i sell", "sell or store", "sell now", "recommend", "recommendation", "hold or sell",
    "बेचूं", "बेचना चाहिए", "रखूं", "बेचें या रखें", "ಸಲ್ಲಿಸಬೇಕಾ", "ಮಾರಬೇಕಾ", "ಮಾರಾಟ", "ಸಂಗ್ರಹಿಸಬೇಕಾ",
)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFC", str(value or "")).lower().strip()
    value = re.sub(r"[\u200b\ufeff]", "", value)
    return re.sub(r"\s+", " ", value)


def _contains(text: str, phrase: str) -> bool:
    phrase = normalize_text(phrase)
    # Indic-script phrases and multi-word phrases are safely checked as substrings.
    if any("\u0900" <= ch <= "\u0dff" for ch in phrase) or " " in phrase:
        return phrase in text
    return re.search(r"(?<![\w])" + re.escape(phrase) + r"(?![\w])", text, flags=re.UNICODE) is not None


def detect_language(text: str, requested: str | None = None) -> str:
    if requested in SUPPORTED_LANGUAGES:
        return SUPPORTED_LANGUAGES[requested]
    if any("\u0c80" <= ch <= "\u0cff" for ch in text):
        return "kn"
    if any("\u0900" <= ch <= "\u097f" for ch in text):
        return "hi"
    return "en"


def _find_alias(text: str, groups: dict[str, tuple[str, ...]]) -> str | None:
    hits: list[tuple[int, str]] = []
    for canonical, aliases in groups.items():
        for alias in aliases:
            if _contains(text, alias):
                hits.append((len(normalize_text(alias)), canonical))
    return max(hits, default=(0, None), key=lambda item: item[0])[1]


def _parse_date(text: str, client_date: str | None = None) -> tuple[str | None, bool]:
    """Return (ISO date or None, ambiguous_relative_date)."""
    base_date = date.today()
    if client_date:
        try:
            base_date = date.fromisoformat(str(client_date)[:10])
        except ValueError:
            pass

    # ISO date: YYYY-MM-DD or YYYY/MM/DD.
    match = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", text)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat(), False
        except ValueError:
            return None, False

    # Local numeric date: DD-MM-YYYY or DD/MM/YYYY.
    match = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b", text)
    if match:
        try:
            return date(int(match.group(3)), int(match.group(2)), int(match.group(1))).isoformat(), False
        except ValueError:
            return None, False

    # Day + English month name, with optional year.
    months = {name.lower(): number for number, name in enumerate(calendar.month_name) if name}
    months.update({name.lower(): number for number, name in enumerate(calendar.month_abbr) if name})
    month_pattern = "|".join(sorted(months, key=len, reverse=True))
    match = re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_pattern})(?:\s+(20\d{{2}}))?\b", text)
    if not match:
        match = re.search(rf"\b({month_pattern})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(20\d{{2}}))?\b", text)
        if match:
            month_name, day_text, year_text = match.groups()
            day_value, month_value = int(day_text), months[month_name]
        else:
            day_value = month_value = 0
            year_text = None
    else:
        day_text, month_name, year_text = match.groups()
        day_value, month_value = int(day_text), months[month_name]
    if day_value and month_value:
        year_value = int(year_text) if year_text else base_date.year
        try:
            candidate = date(year_value, month_value, day_value)
            if not year_text and candidate < base_date - timedelta(days=180):
                candidate = date(year_value + 1, month_value, day_value)
            return candidate.isoformat(), False
        except ValueError:
            return None, False

    today_words = ("today", "आज", "ಇಂದು")
    yesterday_words = ("yesterday", "day before today", "कल था", "बीता कल", "पिछले दिन", "ನಿನ್ನೆ", "ಹಿನ್ನೆ")
    tomorrow_words = ("tomorrow", "कल होगा", "आने वाला कल", "ನಾಳೆ", "ನಾಳಿನ")
    if any(_contains(text, word) for word in today_words):
        return base_date.isoformat(), False
    if any(_contains(text, word) for word in yesterday_words):
        return (base_date - timedelta(days=1)).isoformat(), False
    if any(_contains(text, word) for word in tomorrow_words):
        return (base_date + timedelta(days=1)).isoformat(), False

    # Hindi "कल" can mean yesterday or tomorrow without more context. Ask instead of guessing.
    if _contains(text, "कल"):
        return None, True
    return None, False


def parse_command(text: str, language: str | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
    raw_text = str(text or "").strip()
    query = normalize_text(raw_text)
    context = context or {}
    lang = detect_language(raw_text, language)

    commodity = _find_alias(query, CROPS) or context.get("crop") or context.get("commodity")
    if commodity:
        commodity = str(commodity).strip().lower()
        if commodity not in CROPS:
            commodity = _find_alias(normalize_text(commodity), CROPS) or commodity

    state = _find_alias(query, STATES) or context.get("state") or None
    district = _find_alias(query, DISTRICTS) or context.get("district") or None
    market = _find_alias(query, MARKETS) or context.get("market") or context.get("mandi") or district or None
    spoken_series = _find_alias(query, SERIES_ALIASES)
    variety = spoken_series or context.get("variety")
    arrival_date, ambiguous_date = _parse_date(query, context.get("client_date"))

    # Infer market from common phrases like "at Hassan" only when a known market alias appears.
    explicit_price = any(_contains(query, word) for word in PRICE_WORDS)
    crop_in_query = _find_alias(query, CROPS) is not None
    has_mandi_word = any(_contains(query, word) for word in ("mandi", "market", "apmc", "मंडी", "ಮಂಡಿ", "ಮಾರುಕಟ್ಟೆ"))

    intent = "help"
    navigation_target = None

    if any(_contains(query, word) for word in STORAGE_WORDS):
        intent = "cold_storage"
    elif any(_contains(query, word) for word in WEATHER_WORDS):
        intent = "weather"
    elif any(_contains(query, word) for word in RECOMMEND_WORDS):
        intent = "recommendation"
    elif any(_contains(query, word) for word in ("dashboard", "डैशबोर्ड", "ಡ್ಯಾಶ್‌ಬೋರ್ಡ್", "ಮುಖ್ಯಪುಟ", "मुख्य पृष्ठ")):
        intent, navigation_target = "navigate", "dashboard"
    elif any(_contains(query, word) for word in ("payment", "payments", "भुगतान", "पेमेंट", "ಪಾವತಿ", "ಪಾವತಿಗಳು")):
        intent, navigation_target = "navigate", "payments"
    elif any(_contains(query, word) for word in ("setting", "settings", "सेटिंग", "ಸೆಟ್ಟಿಂಗ್")):
        intent, navigation_target = "navigate", "settings"
    elif any(_contains(query, word) for word in ("home", "मुख्य पृष्ठ", "होम", "ಮನೆ", "ಮುಖಪುಟ")):
        intent, navigation_target = "navigate", "home"
    elif explicit_price or (crop_in_query and (has_mandi_word or arrival_date is not None or ambiguous_date)):
        intent = "price_lookup"
    elif any(_contains(query, word) for word in ("help", "what can you do", "मदद", "सहायता", "ಸಹಾಯ")):
        intent = "help"

    return {
        "intent": intent,
        "language": lang,
        "text": raw_text,
        "entities": {
            "commodity": commodity,
            "state": state,
            "district": district,
            "market": market,
            "arrival_date": arrival_date,
            "date_ambiguous": ambiguous_date,
            "navigation_target": navigation_target,
            "quantity": context.get("quantity"),
            "variety": variety,
            "spoken_series": spoken_series,
        },
        "confidence": 0.84 if intent != "help" else 0.55,
    }
