"""Regressions found by real TTS/STT tests on the separate duplicate server."""
import pytest
from cropmandi_voice_assistant.intent_parser import parse_command


@pytest.mark.parametrize('text,language', [
    ('Open Mundi Price, say hi.', 'en-IN'),
    ('मंदी प्राइस खोलो।', 'hi-IN'),
])
def test_observed_spoken_page_name_variants(text, language):
    parsed = parse_command(text, language, {})
    assert parsed['intent'] == 'navigate'
    assert parsed['entities']['navigation_target'] == 'mandi_price_ai'


def test_hindi_explicit_future_phrase_does_not_need_kal_clarification():
    parsed = parse_command('कोलार में कल होने वाले टमाटर के भाव का अनुमान बताओ।', 'hi-IN', {'client_date':'2026-11-07'})
    assert not parsed['entities']['date_ambiguous']
    assert parsed['intent'] == 'prediction'
    assert parsed['entities']['arrival_date'] == '2026-11-08'


def test_bare_hindi_kal_still_requires_clarification():
    parsed = parse_command('कल टमाटर का भाव बताओ', 'hi-IN', {'client_date':'2026-11-07'})
    assert parsed['entities']['date_ambiguous']


def test_spoken_page_alias_does_not_turn_price_question_into_navigation():
    parsed = parse_command('What is the coffee mundi price at Hassan?', 'en-IN', {})
    assert parsed['intent'] == 'price_lookup'
    assert parsed['entities']['commodity'] == 'coffee'


@pytest.mark.parametrize('text,expected', [
    ('ಹದಿನೈದು ಅಕ್ಟೋಬರ್ ಎರಡು ಸಾವಿರ ಇಪ್ಪತ್ತಾರು ಕೋಲಾರದಲ್ಲಿ ಟೊಮೇಟೊ ಬೆಲೆ ಎಷ್ಟು?', '2026-10-15'),
    ('ಹದಿನೈದು ಅಕ್ಟೋಬರ, ಎರಡುಸಾವಿರ ಇಪ್ಪತ್ತೈದು ಕೋಲಾರದಲ್ಲಿ ಟೊಮೇಟೊ ಬೆಲೆ ಎಷ್ಟು?', '2025-10-15'),
    ('पंद्रह अक्टूबर दो हजार छब्बीस को टमाटर का भाव', '2026-10-15'),
    ('अगले सप्ता का अनुमान बताओ', '2026-11-14'),
])
def test_spoken_calendar_numbers_and_observed_week_variant(text,expected):
    parsed=parse_command(text,'auto',{'client_date':'2026-11-07','commodity':'tomato','market':'Kolar'})
    assert parsed['entities']['arrival_date']==expected


def test_damaged_spoken_year_cannot_become_current_year_or_latest():
    parsed=parse_command('ಹದಿನೈದು ಅಕ್ಟೋಬರ, ಎಡು ಸಾವಿರ ಇಪ್ಪತ್ತಾರು ಟೊಮೇಟೊ ಬೆಲೆ','kn-IN',{'client_date':'2026-11-07'})
    assert parsed['entities']['date_unresolved']
    assert parsed['entities']['arrival_date'] is None


@pytest.mark.parametrize('text',['Predict next month tomato price','अगले महीने टमाटर के भाव का अनुमान','ಮುಂದಿನ ತಿಂಗಳ ಟೊಮೇಟೊ ಅಂದಾಜು'])
def test_unknown_relative_target_does_not_default_to_tomorrow(text):
    parsed=parse_command(text,'auto',{'client_date':'2026-11-07','commodity':'tomato','market':'Kolar'})
    assert parsed['entities']['date_unresolved']
    assert parsed['entities']['arrival_date'] is None


def test_unresolved_spoken_date_cannot_call_price_lookup():
    from unittest.mock import Mock
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from cropmandi_voice_assistant import create_voice_router
    lookup=Mock(return_value={'price':999999})
    app=FastAPI();app.include_router(create_voice_router(price_lookup=lookup))
    data=TestClient(app).post('/api/voice/command',json={'text':'ಹದಿನೈದು ಅಕ್ಟೋಬರ, ಎಡು ಸಾವಿರ ಇಪ್ಪತ್ತಾರು ಟೊಮೇಟೊ ಬೆಲೆ','language':'kn-IN','context':{'commodity':'tomato','market':'Kolar'}}).json()['data']
    assert data['needs_clarification']
    assert 'price_record' not in data
    lookup.assert_not_called()


@pytest.mark.parametrize('text',['ಮಂಡಿ ಪ್ರೈಷ್ತರ್ಯಾರಿ.','ಮಂಡಿ ಪ್ರೈಸ್ ತಿರಿ.'])
def test_observed_short_kannada_navigation_variants(text):
    parsed=parse_command(text,'kn-IN',{})
    assert parsed['intent']=='navigate'
    assert parsed['entities']['navigation_target']=='mandi_price_ai'


def test_invalid_kannada_mark_order_in_tomorrow_does_not_lose_target():
    parsed=parse_command('ಕೋಲಾರದಲ್ಲೀ, ನಾ್ಳಿನ ಟೂಮೆಟು ಬೇಳೆ ಅಂದ ಆಜುಹಿ.','kn-IN',{'client_date':'2026-11-07'})
    assert parsed['intent']=='prediction'
    assert parsed['entities']['commodity']=='tomato'
    assert parsed['entities']['market']=='Kolar'
    assert parsed['entities']['arrival_date']=='2026-11-08'


def test_kannada_normalization_preserves_valid_conjuncts_and_numbers():
    from cropmandi_voice_assistant.intent_parser import normalize_text
    assert normalize_text('ಕನ್ನಡ ೨೦೨೬ ಕ್ವಿಂಟಾಲ್')=='ಕನ್ನಡ ೨೦೨೬ ಕ್ವಿಂಟಾಲ್'
