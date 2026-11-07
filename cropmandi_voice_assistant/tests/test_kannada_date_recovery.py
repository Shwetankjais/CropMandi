"""Slot agreement must never turn a conflicting date into a price query."""
import pytest
from cropmandi_voice_assistant.kannada_asr import recover_date, date_slots

PRIMARY = 'ಹದಿನೈದು ಅಕ್ಟೋಬರ, ಎಡುಸಾವಿ್ರ ಇಪ್ಪತ್ತಾरು, ಕೋ್ಲಾ ರದ್ಳಿ ಟೊಮೆಟ್ವೂ ಬೆ ಯಷ್ಚು.'
SECONDARY = 'ಅಕ್ಟೋಬರ್ ಎರಡು ಸಾವಿರ ಇಪ್ಪತ್ತಾರು ಕೋಲಾರದಲ್ಲಿ ಟೊಮೆಟೊ ಬೆಲೆ ಎಷ್ಟು'


def test_actual_independent_transcripts_recover_date_without_manual_edits():
    result = recover_date(PRIMARY, SECONDARY, .689)
    assert result['text'] == '2026-10-15 ಕೋಲಾರದಲ್ಲಿ ಟೊಮೆಟೊ ಬೆಲೆ ಎಷ್ಟು'
    assert result['date_evidence']['whisper']['year'] is None
    assert result['date_evidence']['indicconformer']['day'] is None


@pytest.mark.parametrize('day,month,year,expected', [
    ('ಇಪ್ಪತ್ತು','ಅಕ್ಟೋಬರ್','ಇಪ್ಪತ್ತೈದು','2025-10-20'),
    ('ಹದಿನಾರು','ಅಕ್ಟೋಬರ್','ಇಪ್ಪತ್ತಾರು','2026-10-16'),
    ('ಏಳು','ಆಗಸ್ಟ್','ಇಪ್ಪತ್ತಾರು','2026-08-07'),
    ('೨೯','ಫೆಬ್ರವರಿ','ಇಪ್ಪತ್ತನಾಲ್ಕು','2024-02-29'),
])
def test_recovery_uses_observed_slots_for_different_dates(day,month,year,expected):
    result = recover_date(f'{day} {month} ಅಸ್ಪಷ್ಟ', f'{month} ಎರಡು ಸಾವಿರ {year} ಕೋಲಾರದಲ್ಲಿ ಟೊಮೆಟೊ ಬೆಲೆ', .75)
    assert result['text'].startswith(expected)


@pytest.mark.parametrize('primary,secondary,confidence', [
    (PRIMARY, SECONDARY, .59),
    ('ಅಕ್ಟೋಬರ್ ಅಸ್ಪಷ್ಟ', SECONDARY, .9),
    (PRIMARY, 'ಹದಿನಾರು ' + SECONDARY, .9),
    ('ಹದಿನೈದು ಅಕ್ಟೋಬರ್ 2025', SECONDARY, .9),
    (PRIMARY, SECONDARY.replace('ಅಕ್ಟೋಬರ್','ನವೆಂಬರ್'), .9),
    (PRIMARY, SECONDARY.replace('ಎರಡು ಸಾವಿರ ಇಪ್ಪತ್ತಾರು','ಅಸ್ಪಷ್ಟ'), .9),
    (PRIMARY, SECONDARY.replace('ಟೊಮೆಟೊ','ಅಸ್ಪಷ್ಟ'), .9),
    (PRIMARY, SECONDARY.replace('ಕೋಲಾರದಲ್ಲಿ','ಅಸ್ಪಷ್ಟ'), .9),
    ('ಹದಿನೈದು ಅಕ್ಟೋಬರ್ ಹಾಸನ ಟೊಮೇಟೊ', SECONDARY, .9),
    ('ಹದಿನೈದು ಅಕ್ಟೋಬರ್ ಕೋಲಾರ ಆಲೂಗಡ್ಡೆ', SECONDARY, .9),
    ('ಮೂವತ್ತೊಂದು ಫೆಬ್ರವರಿ ಅಸ್ಪಷ್ಟ', SECONDARY.replace('ಅಕ್ಟೋಬರ್','ಫೆಬ್ರವರಿ'), .9),
    (PRIMARY, SECONDARY + ' अक्टूबर', .9),
    (PRIMARY, SECONDARY + ' ನವೆಂಬರ್', .9),
])
def test_uncertain_missing_invalid_or_conflicting_evidence_requires_review(primary,secondary,confidence):
    assert recover_date(primary,secondary,confidence) is None


def test_slots_do_not_default_a_missing_year():
    assert date_slots('ಹದಿನೈದು ಅಕ್ಟೋಬರ್')['year'] is None


def test_month_name_inside_commodity_is_not_a_second_date():
    result = recover_date('ಹದಿನೈದು ಅಕ್ಟೋಬರ್ ಟೊಮೇಟೊ', SECONDARY.replace('ಟೊಮೆಟೊ', 'ಟೊಮೇಟೊ'), .8)
    assert result['text'].startswith('2026-10-15')
