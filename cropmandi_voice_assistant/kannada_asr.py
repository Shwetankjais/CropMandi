"""Optional, entirely local Kannada date recovery; no audio leaves this machine.

Uses the pinned IndicConformer ONNX export credited in KANNADA_ASR_MODEL.md.
Missing model/runtime keeps Whisper's existing confirmation behaviour intact.
"""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import re
import threading
import unicodedata

from .date_words import KANNADA_NUMBERS, normalize_spoken_date

_session = None
_vocab = None
_lock = threading.Lock()
MONTHS = ('ಜನವರಿ', 'ಫೆಬ್ರವರಿ', 'ಮಾರ್ಚ್', 'ಏಪ್ರಿಲ್', 'ಮೇ', 'ಜೂನ್',
          'ಜುಲೈ', 'ಆಗಸ್ಟ್', 'ಸೆಪ್ಟೆಂಬರ್', 'ಅಕ್ಟೋಬರ', 'ನವೆಂಬರ', 'ಡಿಸೆಂಬರ')
MONTH_PATTERN = '|'.join(MONTHS)
MONTH_TOKEN = rf'(?<!\S)({MONTH_PATTERN})(?:್)?(?=$|[\s,.?]|ರಂದು|ದಂದು)'
NUMBER_PATTERN = '|'.join(re.escape(w) for w in sorted(KANNADA_NUMBERS, key=len, reverse=True))


def _digits(text):
    return ''.join(str(unicodedata.digit(c)) if c.isdigit() else c for c in text)


def date_slots(text):
    """Read only explicit slots, never fill a missing year from today's date."""
    from .intent_parser import normalize_text
    text = _digits(normalize_text(text))
    months = list(re.finditer(MONTH_TOKEN, text))
    if len(months) != 1:
        return None
    month = months[0]
    prefix = text[:month.start()].rstrip(' ,')
    day = re.search(rf'(?:^|\s)(\d{{1,2}}|{NUMBER_PATTERN})$', prefix)
    day_value = None if not day else KANNADA_NUMBERS.get(day[1], int(day[1]) if day[1].isdigit() else None)
    suffix = normalize_spoken_date(text[month.start():])
    year = re.search(r'(?<!\d)(20\d{2})(?!\d)', suffix)
    return {'day': day_value, 'month': MONTHS.index(month[1]) + 1,
            'year': int(year[1]) if year else None}


def recover_date(primary, secondary, confidence):
    """Fuse independently recognized slots only with matching month/day/year.

    Whisper must provide the day; IndicConformer must provide an explicit year.
    Missing or conflicting evidence never authorizes an automatic lookup.
    """
    from .intent_parser import parse_command
    if confidence < 0.60 or any('\u0900' <= c <= '\u097f' for c in secondary):
        return None
    first, second = date_slots(primary), date_slots(secondary)
    if not first or not second or not first['day'] or not second['year']:
        return None
    if first['month'] != second['month']:
        return None
    if second['day'] and second['day'] != first['day']:
        return None
    if first['year'] and first['year'] != second['year']:
        return None
    try:
        observed = date(second['year'], second['month'], first['day'])
    except ValueError:
        return None
    # Preserve all non-date words from the Kannada recognizer; the parser must
    # independently identify a commodity and an actual market without context.
    normalized = _digits(normalize_spoken_date(secondary))
    month = re.search(MONTH_TOKEN, normalized)
    if not month:
        return None
    year = re.search(r'20\d{2}', normalized[month.end():])
    if not year:
        return None
    end = month.end() + year.end()
    candidate = f'{observed.isoformat()} {normalized[end:].strip(" ,.")}'
    parsed = parse_command(candidate, 'kn-IN', {})
    original = parse_command(primary, 'kn-IN', {})
    entities = parsed['entities']
    if parsed['intent'] != 'price_lookup' or not entities.get('commodity') or not entities.get('market'):
        return None
    if entities.get('arrival_date') != observed.isoformat():
        return None
    for slot in ('commodity', 'market'):
        if original['entities'].get(slot) and original['entities'][slot] != entities[slot]:
            return None
    return {'text': candidate, 'date_evidence': {'whisper': first, 'indicconformer': second},
            'secondary_text': secondary, 'secondary_confidence': round(confidence, 3)}


def transcribe_kannada(path, model_dir):
    """Decode with CPU ONNX Runtime and NeMo-compatible NumPy features."""
    global _session, _vocab
    import numpy as np
    import onnxruntime as ort
    from faster_whisper.audio import decode_audio
    from faster_whisper.feature_extractor import FeatureExtractor
    ort.disable_telemetry_events()
    with _lock:
        if _session is None:
            root = Path(model_dir) / 'indicconformer-kn' / 'kn'
            options = ort.SessionOptions()
            options.intra_op_num_threads = 4
            options.inter_op_num_threads = 1
            try:
                vocabulary = json.loads((root / 'vocab.json').read_text())
                session = ort.InferenceSession(str(root / 'model.onnx'), options, providers=['CPUExecutionProvider'])
            except Exception as exc:
                raise RuntimeError('Optional local Kannada model could not be loaded') from exc
            _vocab, _session = vocabulary, session
        audio = decode_audio(path, sampling_rate=16000)
        if len(audio) < 400:
            return '', 0.0
        emphasized = np.r_[audio[:1], audio[1:] - .97 * audio[:-1]]
        frames = np.lib.stride_tricks.sliding_window_view(np.pad(emphasized, (256, 256)), 512)[::160]
        window = np.pad(np.hanning(401)[:-1], (56, 56))
        power = np.abs(np.fft.rfft(frames * window, axis=-1)) ** 2
        filters = FeatureExtractor.get_mel_filters(16000, 512, 80).astype(np.float32)
        features = np.log(filters @ power.T + 2**-24).astype(np.float32)
        features = (features - features.mean(1, keepdims=True)) / (features.std(1, ddof=1, keepdims=True) + 1e-5)
        logits = _session.run(None, {'audio_signal': features[None].astype(np.float32),
                                    'length': np.array([features.shape[1]], dtype=np.int64)})[0][0]
        ids = logits.argmax(-1)
        tokens, probabilities = [], []
        previous = None
        for frame, token in zip(logits, ids):
            if token != previous and token < len(_vocab):
                tokens.append(_vocab[token])
                probabilities.append(float(1 / np.exp(frame - frame[token]).sum()))
            previous = token
        return ''.join(tokens).replace('▁', ' ').strip(), float(np.mean(probabilities)) if probabilities else 0.0
