"""Normalize spoken calendar numbers; never guess a damaged year or price."""
from __future__ import annotations
import re

KANNADA_NUMBERS = {
    'ಒಂದು':1,'ಎರಡು':2,'ಮೂರು':3,'ನಾಲ್ಕು':4,'ಐದು':5,'ಆರು':6,'ಏಳು':7,'ಎಂಟು':8,'ಒಂಬತ್ತು':9,'ಹತ್ತು':10,
    'ಹನ್ನೊಂದು':11,'ಹನ್ನೆರಡು':12,'ಹದಿಮೂರು':13,'ಹದಿನಾಲ್ಕು':14,'ಹದಿನೈದು':15,'ಹದಿನಾರು':16,'ಹದಿನೇಳು':17,'ಹದಿನೆಂಟು':18,'ಹತ್ತೊಂಬತ್ತು':19,
    'ಇಪ್ಪತ್ತು':20,'ಇಪ್ಪತ್ತೊಂದು':21,'ಇಪ್ಪತ್ತೆರಡು':22,'ಇಪ್ಪತ್ತಮೂರು':23,'ಇಪ್ಪತ್ತನಾಲ್ಕು':24,'ಇಪ್ಪತ್ತೈದು':25,'ಇಪ್ಪತ್ತಾರು':26,'ಇಪ್ಪತ್ತೇಳು':27,'ಇಪ್ಪತ್ತೆಂಟು':28,'ಇಪ್ಪತ್ತೊಂಬತ್ತು':29,'ಮೂವತ್ತು':30,'ಮೂವತ್ತೊಂದು':31,
}
HINDI_NUMBERS = {'एक':1,'दो':2,'तीन':3,'चार':4,'पाँच':5,'पांच':5,'छह':6,'सात':7,'आठ':8,'नौ':9,'दस':10,'ग्यारह':11,'बारह':12,'तेरह':13,'चौदह':14,'पंद्रह':15,'पन्द्रह':15,'सोलह':16,'सत्रह':17,'अठारह':18,'उन्नीस':19,'बीस':20,'इक्कीस':21,'बाईस':22,'तेईस':23,'चौबीस':24,'पच्चीस':25,'छब्बीस':26,'सत्ताईस':27,'अट्ठाईस':28,'उनतीस':29,'तीस':30,'इकतीस':31}
MONTH_WORDS = ('january','february','march','april','june','july','august','september','october','november','december',
    'जनवरी','फरवरी','फ़रवरी','मार्च','अप्रैल','मई','जून','जुलाई','अगस्त','सितंबर','सितम्बर','अक्टूबर','नवंबर','दिसंबर',
    'ಜನವರಿ','ಫೆಬ್ರವರಿ','ಮಾರ್ಚ್','ಏಪ್ರಿಲ್','ಮೇ','ಜೂನ್','ಜುಲೈ','ಆಗಸ್ಟ್','ಸೆಪ್ಟೆಂಬರ್','ಅಕ್ಟೋಬರ','ನವೆಂಬರ','ಡಿಸೆಂಬರ')


def has_month(text):
    return any(word in text for word in MONTH_WORDS) or bool(re.search(r'\b(?:on|in) may\b',text))


def normalize_spoken_date(text):
    if not has_month(text):
        return text
    for numbers,prefix in ((KANNADA_NUMBERS,r'ಎರಡು\s*ಸಾವಿರ(?:ದ)?\s*'),(HINDI_NUMBERS,r'दो\s*ह(?:ज़|ज|ज़)ार\s*')):
        words='|'.join(re.escape(k) for k in sorted(numbers,key=len,reverse=True))
        text=re.sub(prefix+'('+words+')',lambda m:str(2000+numbers[m[1]]),text)
    # A remaining spoken year marker means its year was not decoded reliably.
    # Keep it for the parser to request clarification rather than default a year.
    if unresolved_spoken_year(text):
        return text
    for numbers in (KANNADA_NUMBERS,HINDI_NUMBERS):
        pattern='|'.join(re.escape(k) for k in sorted(numbers,key=len,reverse=True))
        text=re.sub(pattern,lambda m:str(numbers[m[0]]),text)
    return text


def unresolved_spoken_year(text):
    return bool(re.search(r'ಸಾವ[ಿ್]*ರ|ह(?:ज़|ज|ज़)ार',text))
