# Local Kannada speech model attribution and setup

The optional date recovery decoder uses AI4Bharat IndicConformer Kannada 120M
(original model: https://huggingface.co/ai4bharat/indicconformer_stt_kn_hybrid_ctc_rnnt_large,
MIT license). The ONNX export is by Sulabh Katiyar, published under CC BY 4.0:
https://huggingface.co/sulabhkatiyar/indicconformer-120m-onnx
License: https://creativecommons.org/licenses/by/4.0/
Pinned revision: `16f1697d0631c9bb88e371fca24577efe0aa8617`.
Our code supplies NumPy preprocessing and guarded calendar-slot agreement;
we do not execute downloaded Python or change the model weights.

Only `kn/model.onnx` (493,060,285 bytes) and `kn/vocab.json` are needed, under
`CROPMANDI_VOICE_MODEL_DIR/indicconformer-kn/` (default: this package's `.models`).
They are already installed in this duplicate. To prepare another installation,
use `huggingface_hub.hf_hub_download` for those two filenames with the repository
and pinned revision above, setting `local_dir` to that directory. Install this
package's requirements. No new environment variables are required.

Recognition runs locally on CPU; no audio or transcript is uploaded by this
model, and there are no paid API requirements. Download requires internet once.
Missing files retain the existing clarification path. Keep this attribution
with redistributed copies. Model files are excluded from source control.
