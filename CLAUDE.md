# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **GPT-SoVITS TTS corpus selection tool** for the "王也" (Wang Ye) voice cloning project. It provides a web UI for browsing, comparing, and refining 1000 synthesized voice lines against reference audio.

## Key Files

| File | Description |
|---|---|
| `wangye_corpus_1000.txt` | 1000 lines of target corpus text (line N corresponds to wav/NNNN.wav) |
| `batch_infer.py` | Batch inference script — reads corpus, auto-selects reference audio by style, synthesizes WAVs via GPT-SoVITS API (`localhost:9880`) |
| `batch_infer_single.py` | CLI single-line inference script |
| `server.py` | Lightweight HTTP server serving the web UI + REST API for re-synthesis and deletion |
| `index.html` | Frontend web UI (vanilla JS) |
| `raw/wangyevoice/*.WAV` | 128 reference audio files |
| `raw/wangye.list` | Reference audio metadata: `path|speaker|lang|text` |
| `wav/*.wav` | Synthesized output WAVs (0001.wav - 1000.wav) |
| `batch_inference.log` | Batch inference log file |

## GPT-SoVITS API

The system depends on a running GPT-SoVITS API server:
```
python api_v2.py --port 9880
```

API endpoints used:
- `POST /tts` — synthesize audio (JSON body: text, text_lang, ref_audio_path, prompt_text, prompt_lang, etc.)
- `GET /set_gpt_weights?weights_path=...` — switch GPT model
- `GET /set_sovits_weights?weights_path=...` — switch SoVITS model

Model paths:
- GPT: `GPT_weights_v2/wangye-e10.ckpt`
- SoVITS: `SoVITS_weights_v2/wangye_e8_s1024.pth`

## Reference Audio Styles

`batch_infer.py` categorizes 39 reference audios into 5 styles:
- **lazy** — 慵懒/叹气/日常 (10 refs)
- **serious** — 沉稳/论述/长篇 (10 refs)
- **casual** — 对话/轻松/短句 (10 refs)
- **question** — 疑问/反问 (10 refs)
- **strong** — 严肃/告诫/气势 (9 refs)

Style selection is auto-determined by text characteristics (length, punctuation).

## Common Commands

```bash
# Start GPT-SoVITS API server (required before any inference)
python api_v2.py --port 9880

# Batch synthesize all 1000 lines
python batch_infer.py

# Synthesize a single line
python batch_infer_single.py --id 123 --ref 100.WAV

# Start the web UI server
python server.py
```

Then open `http://localhost:8888` in a browser.

## Data Flow

1. `wangye_corpus_1000.txt` line N (1-indexed) → `wav/NNNN.wav`
2. Each synthesis pairs a corpus line with one reference audio from `raw/wangyevoice/`
3. `batch_infer.py` generates `metadata.csv` alongside the WAVs
4. The web UI reads corpus text, lists generated WAVs, and allows re-synthesis via the GPT-SoVITS API
