---
language:
  - as
  - bn
  - gu
  - hi
  - kn
  - ml
  - mr
  - or
  - pa
  - ta
  - te
  - ur
tags:
  - automatic-speech-recognition
  - onnx
  - indian-languages
  - ctc
  - conformer
license: cc-by-4.0
---

# IndicConformer 120M — Per-Language ONNX Models for Indian Language ASR

CTC-only ONNX exports of [AI4Bharat](https://ai4bharat.iitm.ac.in/)'s **IndicConformer hybrid CTC/RNN-T large** models (~120M parameters each). One model per language for 12 Indian languages, optimized for batch inference with ONNX Runtime (GPU via CUDA/ROCm, or CPU).

## Languages

| Code | Language   | Source Model |
|------|------------|-------------|
| `as` | Assamese   | [ai4bharat/indicconformer_stt_as_hybrid_ctc_rnnt_large](https://huggingface.co/ai4bharat/indicconformer_stt_as_hybrid_ctc_rnnt_large) |
| `bn` | Bengali    | [ai4bharat/indicconformer_stt_bn_hybrid_ctc_rnnt_large](https://huggingface.co/ai4bharat/indicconformer_stt_bn_hybrid_ctc_rnnt_large) |
| `gu` | Gujarati   | [ai4bharat/indicconformer_stt_gu_hybrid_ctc_rnnt_large](https://huggingface.co/ai4bharat/indicconformer_stt_gu_hybrid_ctc_rnnt_large) |
| `hi` | Hindi      | [ai4bharat/indicconformer_stt_hi_hybrid_ctc_rnnt_large](https://huggingface.co/ai4bharat/indicconformer_stt_hi_hybrid_ctc_rnnt_large) |
| `kn` | Kannada    | [ai4bharat/indicconformer_stt_kn_hybrid_ctc_rnnt_large](https://huggingface.co/ai4bharat/indicconformer_stt_kn_hybrid_ctc_rnnt_large) |
| `ml` | Malayalam  | [ai4bharat/indicconformer_stt_ml_hybrid_ctc_rnnt_large](https://huggingface.co/ai4bharat/indicconformer_stt_ml_hybrid_ctc_rnnt_large) |
| `mr` | Marathi    | [ai4bharat/indicconformer_stt_mr_hybrid_ctc_rnnt_large](https://huggingface.co/ai4bharat/indicconformer_stt_mr_hybrid_ctc_rnnt_large) |
| `or` | Odia       | [ai4bharat/indicconformer_stt_or_hybrid_ctc_rnnt_large](https://huggingface.co/ai4bharat/indicconformer_stt_or_hybrid_ctc_rnnt_large) |
| `pa` | Punjabi    | [ai4bharat/indicconformer_stt_pa_hybrid_ctc_rnnt_large](https://huggingface.co/ai4bharat/indicconformer_stt_pa_hybrid_ctc_rnnt_large) |
| `ta` | Tamil      | [ai4bharat/indicconformer_stt_ta_hybrid_ctc_rnnt_large](https://huggingface.co/ai4bharat/indicconformer_stt_ta_hybrid_ctc_rnnt_large) |
| `te` | Telugu     | [ai4bharat/indicconformer_stt_te_hybrid_ctc_rnnt_large](https://huggingface.co/ai4bharat/indicconformer_stt_te_hybrid_ctc_rnnt_large) |
| `ur` | Urdu       | [ai4bharat/indicconformer_stt_ur_hybrid_ctc_rnnt_large](https://huggingface.co/ai4bharat/indicconformer_stt_ur_hybrid_ctc_rnnt_large) |

## Repo Structure

```
{lang}/model.onnx    # ONNX model (~470 MB each)
{lang}/vocab.json    # BPE vocabulary (JSON list of token strings)
```

## Model Details

| Property | Value |
|----------|-------|
| **Architecture** | IndicConformer (Conformer encoder + CTC head) |
| **Parameters** | ~120M per language |
| **Input: `audio_signal`** | `float32 [B, 80, T_mel]` — log-mel spectrogram |
| **Input: `length`** | `int64 [B]` — number of valid mel frames per utterance |
| **Output** | CTC logits `float32 [B, T_out, V+1]` where V = vocab size |
| **Blank token** | ID = `len(vocab)` (last index in output dim) |
| **Subsampling** | ~4x (mel frames to output frames) |
| **ONNX file size** | ~470 MB per language |

## Mel Spectrogram Preprocessing

These models require NeMo-compatible preprocessing. The full pipeline:

1. **Preemphasis** — coefficient 0.97
2. **STFT** — n_fft=512, hop_length=160, win_length=400
3. **Mel filterbank** — 80 bins, Slaney normalization, fmin=0, fmax=8000
4. **Power** — power=2.0 (power spectrogram)
5. **Log** — `log(x + 2^-24)`
6. **Per-feature normalization** — zero mean, unit variance per mel bin (unbiased std, ddof=1)

```python
import numpy as np
import librosa

def nemo_mel_spectrogram(audio: np.ndarray, sr: int = 16000) -> np.ndarray:
    """NeMo-compatible log-mel spectrogram. Returns float32 [80, T_frames]."""
    # 1. Preemphasis
    audio = np.concatenate([audio[:1], audio[1:] - 0.97 * audio[:-1]])

    # 2. Mel power spectrogram
    mel = librosa.feature.melspectrogram(
        y=audio, sr=sr, n_fft=512, hop_length=160, win_length=400,
        n_mels=80, fmin=0, fmax=sr / 2, norm="slaney", power=2.0,
    )

    # 3. Log
    log_mel = np.log(mel + 2**-24).astype(np.float32)

    # 4. Per-feature normalization
    mean = log_mel.mean(axis=1, keepdims=True)
    std  = log_mel.std(axis=1, ddof=1, keepdims=True) + 1e-5
    log_mel = (log_mel - mean) / std

    return log_mel.astype(np.float32)
```

## Quick Start

```python
import json, numpy as np, librosa, onnxruntime as ort
from huggingface_hub import hf_hub_download

REPO = "sulabhkatiyar/indicconformer-120m-onnx"
LANG = "hi"  # Change to any supported language code

# 1. Download model and vocabulary
model_path = hf_hub_download(REPO, f"{LANG}/model.onnx")
vocab_path = hf_hub_download(REPO, f"{LANG}/vocab.json")

# 2. Load ONNX session (auto-selects best available provider)
providers = ["CUDAExecutionProvider", "ROCMExecutionProvider", "CPUExecutionProvider"]
session = ort.InferenceSession(model_path, providers=providers)

# 3. Load vocabulary
with open(vocab_path, "r", encoding="utf-8") as f:
    vocab = json.load(f)
blank_id = len(vocab)

# 4. Load and preprocess audio
audio, sr = librosa.load("audio.wav", sr=16000)

# Preemphasis
audio_pe = np.concatenate([audio[:1], audio[1:] - 0.97 * audio[:-1]])

# Mel spectrogram
mel = librosa.feature.melspectrogram(
    y=audio_pe, sr=16000, n_fft=512, hop_length=160, win_length=400,
    n_mels=80, fmin=0, fmax=8000, norm="slaney", power=2.0,
)
log_mel = np.log(mel + 2**-24).astype(np.float32)
mean = log_mel.mean(axis=1, keepdims=True)
std  = log_mel.std(axis=1, ddof=1, keepdims=True) + 1e-5
log_mel = (log_mel - mean) / std

# Batch dimensions: [1, 80, T]
mel_batch  = log_mel[np.newaxis, :, :].astype(np.float32)
mel_length = np.array([mel_batch.shape[2]], dtype=np.int64)

# 5. Run inference
logits = session.run(None, {"audio_signal": mel_batch, "length": mel_length})[0]

# 6. CTC greedy decode
log_probs = logits - logits.max(axis=-1, keepdims=True)
log_probs = log_probs - np.log(np.exp(log_probs).sum(axis=-1, keepdims=True))
ids = np.argmax(log_probs[0], axis=-1)

# Collapse consecutive duplicates, remove blanks
prev, tokens = -1, []
for t in ids:
    if t != prev:
        if t != blank_id and t < len(vocab):
            tokens.append(vocab[t])
    prev = t

transcript = "".join(tokens).replace("\u2581", " ").strip()
print(transcript)
```

## Batch Inference

For throughput, pad mel spectrograms to the same length within a batch and set the `length` input to each utterance's actual frame count. The model handles variable-length inputs natively — invalid frames beyond the given length are ignored.

```python
# Assuming mels is a list of [80, T_i] arrays
mel_lengths = np.array([m.shape[1] for m in mels], dtype=np.int64)
max_len = int(mel_lengths.max())
mel_batch = np.zeros((len(mels), 80, max_len), dtype=np.float32)
for i, m in enumerate(mels):
    mel_batch[i, :, :m.shape[1]] = m

logits = session.run(None, {"audio_signal": mel_batch, "length": mel_lengths})[0]
# Decode each utterance using its actual output length (~T_mel / 4)
```

## Export Process

These ONNX models were exported from AI4Bharat's NeMo `.nemo` checkpoints:

1. Load the hybrid CTC/RNN-T model: `EncDecHybridRNNTCTCBPEModel.restore_from(nemo_path)`
2. Switch to CTC decoder: `model.cur_decoder = "ctc"`
3. Export: `model.export("model.onnx")`
4. Extract vocabulary: `list(model.ctc_decoder.vocabulary)` saved as `vocab.json`

Exported using [AI4Bharat's NeMo fork](https://github.com/AI4Bharat/NeMo) (branch `nemo-v2`).

## Credits

- **AI4Bharat** for training and releasing the original IndicConformer models
- Original model repos: `ai4bharat/indicconformer_stt_{lang}_hybrid_ctc_rnnt_large` on [HuggingFace](https://huggingface.co/ai4bharat)
