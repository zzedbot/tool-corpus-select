# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **GPT-SoVITS TTS corpus selection tool** for the "王也" (Wang Ye) voice cloning project. It provides a web UI for browsing, comparing, refining, and rating 1000 synthesized voice lines against reference audio.

## Key Files

| File | Description |
|---|---|
| `wangye_corpus_1000.txt` | 1000 lines of target corpus text (line N corresponds to wav/NNNN.wav) |
| `batch_infer.py` | Batch inference script — reads corpus, auto-selects reference audio by style |
| `batch_infer_single.py` | CLI single-line inference script |
| `server.py` | Backend: HTTP server + REST API for re-synthesis, deletion, rating, locking |
| `index.html` | Frontend HTML structure only |
| `raw/refs.txt` | Reference audio config: `style|number|text` (109 refs, 5 styles) |
| `raw/wangyevoice/*.WAV` | 128 reference audio files |
| `static/` | Frontend JS/CSS (see below) |
| `wav/` | Generated WAVs + state files (excluded from git) |

## Frontend Module Structure

| File | Responsibility |
|---|---|
| `static/state.js` | Global state variables (corpusData, refsData, selectedId, checkedIds, etc.) |
| `static/api.js` | Single `api(path, opts)` fetch wrapper |
| `static/utils.js` | `toast()` notifications, `escHtml()` HTML escaping |
| `static/render.js` | List rendering, detail view, ref audio selector, audio controls, selection/locking |
| `static/actions.js` | User actions: regenerate, random regenerate, rating, delete, batch operations |
| `static/zen.js` | Zen mode: queue management, auto-play, countdown, keyboard events, rating |
| `static/main.js` | Event bindings, data loading entry point |
| `static/style.css` | All CSS styles |

Scripts load in order via `<script>` tags, sharing global scope. No build tools needed.

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

Reference audios are configured in `raw/refs.txt` across 5 styles (109 total refs):

| Style | Count | Label | Use Case |
|-------|-------|-------|----------|
| lazy | 20 | 😮‍💨 慵懒/日常 | Casual conversation |
| serious | 39 | 📜 沉稳/长篇 | Long-form content, idioms, poetry |
| casual | 21 | 💬 对话/轻松 | Short sentences, light conversation |
| question | 13 | ❓ 疑问/反问 | Questions |
| strong | 16 | ⚡ 严肃/气势 | Serious announcements |

## State Files (in wav/)

| File | Format | Purpose |
|---|---|---|
| `metadata.csv` | `id\|text` | Which corpus lines have been generated |
| `ref_mapping.txt` | `id\|ref_name\|ref_text` | Which reference audio was used for each synthesis |
| `rating.txt` | `id\|level` | Quality ratings (excellent/good/fair/poor) |
| `lock_status.txt` | one `id` per line | Locked corpus IDs |

## Common Commands

```bash
# Start GPT-SoVITS API server (required before any inference)
python api_v2.py --port 9880

# Batch synthesize all 1000 lines
python batch_infer.py

# Synthesize a single line
python batch_infer_single.py --id 123 --ref 100.WAV

# Start the web UI server
python server.py [--port 8888] [--api-port 9880]
```

Then open `http://localhost:8888` in a browser.

## Data Flow

1. `wangye_corpus_1000.txt` line N (1-indexed) → `wav/NNNN.wav`
2. Each synthesis pairs a corpus line with one reference audio from `raw/wangyevoice/`
3. `batch_infer.py` generates `metadata.csv` alongside the WAVs
4. The web UI reads corpus text, lists generated WAVs, and allows re-synthesis via the GPT-SoVITS API
5. Ratings and lock states are persisted to txt files in `wav/`
