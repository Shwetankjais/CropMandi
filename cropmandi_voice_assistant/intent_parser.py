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

from .date_words import normalize_spoken_date, unresolved_spoken_year, has_month

SUPPORTED_LANGUAGES = {"en-IN": "en", "hi-IN": "hi", "kn-IN": "kn"}

CROPS: dict[str, tuple[str, ...]] = {
    "coffee": ("coffee", "कॉफी", "कोफी", "कोफ़ी", "ಕಾಫಿ", "ಕಾಪಿ", "kaafi", "kafi", "kaapi"),
    "pepper": ("pepper", "black pepper", "काली मिर्च", "ಮೆಣಸು", "ಮೆಣಸಿನ", "ಕರಿಮೆಣಸು"),
    "cardamom": ("cardamom", "elaichi", "इलायची", "ಏಲಕ್ಕಿ"),
    "rice": ("rice", "चावल", "ಅಕ್ಕಿ"),
    "paddy": ("paddy", "धान", "ಭತ್ತ", "bhatta", "dhan"),
    "tomato": ("tomato", "tomatoes", "टमाटर", "ಟೊಮೇಟೊ", "ಟೊಮೆಟೊ", "ಟೊಮಾಟೊ", "ಟೊಮೇಟು", "ಟೊಮೆಟು", "ಟೂಮೆಟು", "tamatar"),
    "potato": ("potato", "potatoes", "आलू", "ಆಲೂಗಡ್ಡೆ", "aloo"),
    "maize": ("maize", "corn", "मक्का", "ಮೆಕ್ಕೆಜೋಳ", "ಜೋಳ", "makka"),
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
    "price", "rate", "modal price", "market price", "mandi bhav", "bhaav", "bhav", "bahav", "bele", "बहाव",
    "कीमत", "दाम", "भाव", "मंडी", "दर", "ಬೆಲೆ", "ದರ", "ಬಿಲೆ", "ಮಾರುಕಟ್ಟೆ", "ಮಂಡಿ",
)
WEATHER_WORDS = ("weather", "rain", "मौसम", "बारिश", "ಹವಾಮಾನ", "ಮಳೆ")
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
    # ASR can emit an invalid Kannada vowel-sign + virama sequence.
    # Remove only that impossible mark ordering; never repair numeric values.
    value = re.sub(r"([\u0cbe-\u0ccc])\u0ccd", r"\1", value)
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

    month_mentioned = has_month(text)
    text = normalize_spoken_date(text)
    if has_month(text) and unresolved_spoken_year(text):
        return "UNRESOLVED_DATE", False
    # Normalize native numerals and month names without translating crop names.
    text = "".join(str(unicodedata.digit(c)) if c.isdigit() else c for c in text)
    month_names = {
        "जनवरी": "january", "फ़रवरी": "february", "फरवरी": "february", "मार्च": "march",
        "अप्रैल": "april", "मई": "may", "जून": "june", "जुलाई": "july", "अगस्त": "august",
        "सितंबर": "september", "सितम्बर": "september", "अक्टूबर": "october", "नवंबर": "november", "दिसंबर": "december",
        "ಜನವರಿ": "january", "ಫೆಬ್ರವರಿ": "february", "ಮಾರ್ಚ್": "march", "ಏಪ್ರಿಲ್": "april",
        "ಮೇ": "may", "ಜೂನ್": "june", "ಜುಲೈ": "july", "ಆಗಸ್ಟ್": "august", "ಸೆಪ್ಟೆಂಬರ್": "september",
        "ಅಕ್ಟೋಬರ್": "october", "ಅಕ್ಟೋಬರ": "october", "ನವೆಂಬರ್": "november", "ಡಿಸೆಂಬರ್": "december",
    }
    for native, english in month_names.items():
        text = text.replace(native, english)
    if any(w in text for w in ("next week", "अगले हफ्ते", "अगले सप्ताह", "अगले सप्ता", "ಮುಂದಿನ ವಾರ")):
        return (base_date + timedelta(days=7)).isoformat(), False
    # ISO date: YYYY-MM-DD or YYYY/MM/DD.
    match = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", text)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat(), False
        except ValueError:
            return "INVALID_DATE", False

    # Local numeric date: DD-MM-YYYY or DD/MM/YYYY.
    match = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b", text)
    if match:
        try:
            return date(int(match.group(3)), int(match.group(2)), int(match.group(1))).isoformat(), False
        except ValueError:
            return "INVALID_DATE", False

    # Day + English month name, with optional year.
    months = {name.lower(): number for number, name in enumerate(calendar.month_name) if name}
    months.update({name.lower(): number for number, name in enumerate(calendar.month_abbr) if name})
    month_pattern = "|".join(sorted(months, key=len, reverse=True))
    match = re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_pattern})(?:\s*,?\s*(20\d{{2}}))?\b", text)
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
            return candidate.isoformat(), False
        except ValueError:
            return "INVALID_DATE", False

    if month_mentioned or has_month(text):
        return "UNRESOLVED_DATE", False

    today_words = ("today", "आज", "ಇಂದು", "ಇವತ್ತು", "ಇವತ್ತಿನ", "ivattu", "aaj")
    yesterday_words = ("yesterday", "ninne", "day before today", "कल था", "बीता कल", "पिछले दिन", "ನಿನ್ನೆ", "ಹಿನ್ನೆ")
    tomorrow_words = ("tomorrow", "naale", "कल होगा", "कल होने वाले", "कल होने वाला", "आने वाला कल", "ನಾಳೆ", "ನಾಳಿನ")
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


PAGE_ALIASES = {
    "dashboard": ("dashboard", "डैशबोर्ड", "ಡ್ಯಾಶ್‌ಬೋರ್ಡ್"),
    "my_crops": ("my crops", "my crop", "मेरी फसल", "मेरी फसलें", "ನನ್ನ ಬೆಳೆ", "nanna bele"),
    "harvest_route": ("harvest route", "harvestroute", "harvest root", "हार्वेस्ट रूट", "ಹಾರ್ವೆಸ್ಟ್ ರೂಟ್"),
    "mandi_price_ai": ("mandi price ai", "mandi price", "mundi price", "मंडी प्राइस", "मंदी प्राइस", "ಮಂಡಿ ಪ್ರೈಸ್", "ಮಂಡಿ ಪ್ರೈಸ್ ತಿರಿ", "ಮಂಡಿ ಪ್ರೈಷ್ತರ್ಯಾರಿ"),
    "analytics": ("analytics", "analysis page", "एनालिटिक्स", "ವಿಶ್ಲೇಷಣೆ", "ಅನಾಲಿಟಿಕ್ಸ್"),
    "settings": ("settings", "setting", "सेटिंग", "ಸೆಟ್ಟಿಂಗ್"),
    "cold_storage": STORAGE_WORDS,
    "weather": ("weather", "मौसम", "ಹವಾಮಾನ"),
    "payments": ("payments", "payment", "भुगतान", "ಪಾವತಿ"),
    "home": ("home", "मुख्य पृष्ठ", "ಮುಖಪುಟ"),
    "calendar": ("farm calendar", "calendar", "कैलेंडर", "ಕ್ಯಾಲೆಂಡರ್"),
    "alerts": ("alert center", "alerts", "अलर्ट", "ಎಚ್ಚರಿಕೆ"),
}
MARKETS.update({
    "Kolar": ("kolar", "कोलार", "ಕೋಲಾರ"),
    "Davanagere": ("davanagere", "davangere", "दावणगेरे", "ದಾವಣಗೆರೆ"),
    "Shivamogga": ("shimoga", "shivamogga", "शिवमोग्गा", "ಶಿವಮೊಗ್ಗ"),
    "Haveri": ("haveri", "हावेरी", "ಹಾವೇರಿ"),
    "Raichur": ("raichur", "रायचूर", "ರಾಯಚೂರು"),
    "Mandya": ("mandya", "मंड्या", "ಮಂಡ್ಯ"),
    "Bangalore": ("bangalore", "bengaluru", "बेंगलुरु", "ಬೆಂಗಳೂರು"),
})
SERIES_ALIASES.update({
    "HYBRID/LOCAL": ("hybrid/local", "hybrid local"),
    "Hybrid": ("hybrid", "हाइब्रिड", "ಹೈಬ್ರಿಡ್"),
    "Local": ("local", "देसी", "ಸ್ಥಳೀಯ"),
    "Sona Masuri": ("sona masuri", "sona masoori", "सोना मसूरी", "ಸೋನ ಮಸೂರಿ"),
    "Jyoti": ("jyoti", "jyothi", "ज्योति", "ಜ್ಯೋತಿ"),
})


def parse_command(text: str, language: str | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
    raw_text = str(text or "").strip()
    query = normalize_text(raw_text)
    context = context or {}
    lang = detect_language(raw_text, language)
    explicit_crop = _find_alias(query, CROPS)
    prior_crop = context.get("commodity") or context.get("crop")
    commodity = explicit_crop or prior_crop
    if commodity:
        commodity = _find_alias(normalize_text(str(commodity)), CROPS) or str(commodity).lower()
    changed_crop = explicit_crop and prior_crop and explicit_crop != prior_crop
    spoken_series = _find_alias(query, SERIES_ALIASES)
    explicit_market = _find_alias(query, {k:v for k,v in MARKETS.items() if k not in SERIES_ALIASES or k == "Sirsi"})
    market = explicit_market or context.get("market") or context.get("location") or context.get("district")
    if not market and context.get("origin"):
        market = _find_alias(normalize_text(str(context["origin"])), MARKETS)
    # Series names are not geographic markets. Legacy series-only requests remain supported.
    if not market and spoken_series and commodity in ("coffee", "pepper"):
        market = spoken_series
    variety = spoken_series or (None if changed_crop else context.get("variety") or context.get("series"))
    arrival_date, ambiguous = _parse_date(query, context.get("client_date"))
    date_unresolved = arrival_date == "UNRESOLVED_DATE"
    invalid_date = arrival_date == "INVALID_DATE"
    if invalid_date or date_unresolved:
        arrival_date = None
    invalid_date = invalid_date or bool(re.search(r"\d{1,4}[./-]\d{1,2}[./-]\d{1,4}|\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)", query)) and not arrival_date and not ambiguous
    navigation_target = _find_alias(query, PAGE_ALIASES)
    navigate_word = any(w in query for w in ("open", "go to", "show me the page", "take me", "navigate", "खोल", "जाओ", "ತೆರೆ", "ಹೋಗು", "ಗೆ ಹೋಗ", "ನೋಡಿ"))
    navigate_word = navigate_word or (query.startswith("show ") and navigation_target not in (None, "my_crops"))
    back = any(w in query for w in ("go back", "previous page", "back page", "पिछले पेज", "वापस", "ಹಿಂದಿನ ಪುಟ", "ಹಿಂದಕ್ಕೆ"))
    comparison = any(w in query for w in ("compare", "comparison", "difference", "तुलना", "अंतर", "ಹೋಲಿಸ", "ವ್ಯತ್ಯಾಸ"))
    forecast = any(w in query for w in ("predict", "prediction", "forecast", "अंदाज", "अनुमान", "ಅಂದಾಜ", "ಮುನ್ಸೂಚನೆ"))
    try:
        future = arrival_date and arrival_date > str(context.get("client_date") or date.today().isoformat())[:10]
    except (TypeError, ValueError):
        future = False
    comparison_dates = []
    if comparison:
        for part in re.split(r"\s+(?:and|versus|vs\.?|और|ಹಾಗೂ|ಮತ್ತು)\s+", query):
            parsed_date, _ = _parse_date(part, context.get("client_date"))
            if parsed_date and parsed_date not in ("INVALID_DATE", "UNRESOLVED_DATE"):
                comparison_dates.append(parsed_date)
    if back:
        intent, navigation_target = "navigate", "back"
    elif navigation_target and (navigate_word or query.rstrip(".!? ") in PAGE_ALIASES[navigation_target]):
        intent = "navigate"
    elif any(w in query for w in ("weather", "rain", "मौसम", "बारिश", "ಹವಾಮಾನ", "ಮಳೆ")):
        intent = "weather"
    elif comparison:
        intent = "compare_prices"
    elif forecast or future:
        intent = "prediction"
    elif any(w in query for w in ("transport", "distance", "net return", "net realization", "net profit", "route cost", "किराया", "दूरी", "लाभ", "ಸಾರಿಗೆ", "ದೂರ", "ನಿವ್ವಳ")):
        intent = "harvest_route"
    elif any(w in query for w in ("best mandi", "best price", "highest price", "which mandi", "सबसे अच्छा", "कौन सी मंडी", "ಯಾವ ಮಂಡಿ", "ಉತ್ತಮ ಬೆಲೆ")):
        intent = "market_rankings"
    elif any(w in query for w in STORAGE_WORDS):
        intent = "cold_storage"
    elif any(w in query for w in RECOMMEND_WORDS):
        intent = "recommendation"
    elif any(w in query for w in ("my crops", "मेरी फसल", "ನನ್ನ ಬೆಳೆ")):
        intent = "my_crops"
    elif any(_contains(query,w) for w in PRICE_WORDS) or explicit_crop or arrival_date or ambiguous or (spoken_series and context.get("last_intent")):
        intent = context.get("pending_intent") or "price_lookup"
    elif (explicit_market or spoken_series) and context.get("last_intent"):
        intent = context.get("pending_intent") or context["last_intent"]
    else:
        intent = "help"
    date_unresolved = date_unresolved or (intent == "prediction" and not arrival_date and any(w in query for w in ("next ", "अगले", "ಮುಂದಿನ")))
    if not arrival_date and not ambiguous and not date_unresolved and context.get("pending_intent") == intent:
        arrival_date = context.get("target_date")
    if intent == "prediction" and not arrival_date and not date_unresolved and context.get("forecast_date"):
        arrival_date, ambiguous = _parse_date(str(context["forecast_date"]), context.get("client_date"))
        if arrival_date == "INVALID_DATE":
            invalid_date = True; arrival_date = None
    quantity = context.get("quantity")
    quantity_unit = context.get("quantity_unit")
    q = re.search(r"(\d+(?:\.\d+)?)\s*(kg|kilograms?|quintals?|qtl|किलो|क्विंटल|ಕೆಜಿ|ಕಿಲೋ|ಕ್ವಿಂಟಾಲ್)", query)
    if q:
        quantity = float(q[1]); quantity_unit = "kg" if q[2] in ("kg", "kilogram", "kilograms", "किलो", "ಕೆಜಿ", "ಕಿಲೋ") else "quintal"
    if q and intent == "help" and context.get("pending_intent"):
        intent = context["pending_intent"]
    origin = context.get("origin")
    if explicit_market and (intent == "harvest_route" or context.get("pending_intent") == "harvest_route"):
        if not origin or any(w in query for w in ("from ", "से", "ಇಂದ")):
            origin = explicit_market
    grade = None if changed_crop else context.get("grade")
    grades = {"AVERAGE": ("average", "औसत", "ಸರಾಸರಿ"), "NON FAQ": ("non faq",), "FAQ": ("faq",), "GOOD": ("good", "अच्छा", "ಉತ್ತಮ"), "SMALL": ("small", "छोटा", "ಸಣ್ಣ"), "MEDIUM": ("medium", "मध्यम", "ಮಧ್ಯಮ"), "LARGE": ("large", "बड़ा", "ದೊಡ್ಡ")}
    grade = _find_alias(query, grades) or grade
    if not changed_crop:
        for choice in context.get("choices", [])[:10]:
            candidate_variety, separator, candidate_grade = str(choice).rpartition(" / ")
            if separator and _contains(query, candidate_variety):
                variety = candidate_variety
            if separator and _contains(query, str(choice)):
                grade = candidate_grade
    if grade != context.get("grade") and context.get("pending_intent"):
        intent = context["pending_intent"]
    if not spoken_series and any(_contains(query, a) for a in ("common", "सामान्य", "ಸಾಮಾನ್ಯ")):
        variety = "Common"
    return {
        "intent": intent, "language": lang, "text": raw_text,
        "entities": {
            "commodity": commodity, "state": _find_alias(query, STATES) or context.get("state"),
            "district": (_find_alias(query, DISTRICTS) if not explicit_market else None) or (None if explicit_market or changed_crop else context.get("district")),
            "market": market, "arrival_date": arrival_date, "date_ambiguous": ambiguous,
            "invalid_date": invalid_date, "date_unresolved": date_unresolved, "navigation_target": navigation_target,
            "quantity": quantity, "quantity_unit": quantity_unit,
            "variety": variety, "spoken_series": spoken_series,
            "grade": grade, "origin": origin, "forecast_date": context.get("forecast_date"),
            "latitude": context.get("latitude"), "longitude": context.get("longitude"),
            "vehicle_mode": context.get("vehicle_mode", "auto"), "vehicle_id": context.get("vehicle_id"),
            "ownership": context.get("ownership", "hired"),
            "explicit_market": bool(explicit_market), "comparison_dates": comparison_dates if len(comparison_dates) == 2 else [], "page": context.get("page"),
            "client_date": context.get("client_date") or date.today().isoformat(),
        }, "confidence": 0.84 if intent != "help" else 0.4,
    }
