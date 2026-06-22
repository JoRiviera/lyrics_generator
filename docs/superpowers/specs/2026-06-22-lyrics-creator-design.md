# lyrics_creator — Design Spec

**Date:** 2026-06-22
**Status:** Approved design, pending implementation plan

## Goal

Generate synced `.lrc` lyric sidecar files from audio, ready for a Jellyfin music
library. Fully offline. Point the tool at a single audio file *or* a folder; get a
`.lrc` next to each audio file.

## Non-goals (v1)

- Translation of lyrics.
- LLM polish of transcription (dropped — the NPU spike was slow and corrupted lines;
  raw `large-v3-turbo` output is the product).
- Watch-folder daemon / Jellyfin server integration.
- Forced-alignment hybrid using the NPU whisper ("Path B").

## Background / decisions

Two pipelines were evaluated via spike on `15 - Piosenka o CYFERKACH.mp3`:

- **Path A (chosen):** openlrc → faster-whisper → synced `.lrc`. One tool; timestamps
  and text come from a single pass and are inherently consistent. Spike: 67s with the
  `small` model on 2 CPU cores, good Polish output with minor errors.
- **Path B (rejected for v1):** NPU `whisper-v3-turbo-FLM` (22s, better text) for words
  + a separate forced-aligner for timestamps. Rejected because the NPU whisper endpoint
  returns **no timestamps** (`keys: ['model','text']` only), so it cannot feed openlrc.
  A standalone aligner can reach the same end result but adds a second fragile engine:
  text and timing from two systems can disagree, NPU hallucination tails must be
  stripped, and alignment on singing (melisma, instrumental gaps) is the weak spot.
  Same destination, bumpier road — not worth it for a one-time batch.

Transcription model upgraded from the spike's `small` to **`large-v3-turbo`** for best
offline text + timestamp quality in a single pass.

## Architecture

Single-stage pipeline per file:

```
audio file
  → openlrc.LRCer(transcription=TranscriptionConfig(
        whisper_model='large-v3-turbo',
        device='cpu',
        compute_type='int8'))
    .run(path, skip_trans=True, clear_temp=True)   # src_lang optional
  → synced .lrc, written beside the audio file
```

### Components

1. **Transcriber wrapper** — owns the `LRCer` instance (built once, reused across files
   so the whisper model loads only once per run). Exposes `transcribe(audio_path) -> lrc_path`.
   Responsibilities:
   - Run openlrc with the fixed CPU/int8/`large-v3-turbo` config.
   - `skip_trans=True`, `clear_temp=True`.
   - Optional forced source language (`src_lang`), else openlrc auto-detects.
   - Ensure the resulting `.lrc` ends up **beside the source audio file** with the same
     basename (openlrc writes to cwd; the wrapper moves/places it correctly).

2. **Batch driver / CLI** — input resolution + iteration + isolation.
   - Accepts one positional arg: a file **or** a directory.
     - File → process that single file.
     - Directory → recurse, collect audio files.
   - Audio extensions: `.mp3 .flac .m4a .ogg .opus .wav` (case-insensitive).
   - **Idempotent skip:** if a sibling `<basename>.lrc` already exists, skip (logged).
   - Sequential processing (2 cores; parallel whisper gives no benefit).
   - **Per-file error isolation:** an exception on one file is logged and the batch
     continues; the run reports a summary (done / skipped / failed).
   - Flags:
     - `--lang <code>` force source language (default: auto-detect).
     - `--overwrite` regenerate even if a `.lrc` exists.

### Data flow

```
CLI arg ──► resolve to list[audio_path]
             │
             ▼  (for each, sequential)
        sibling .lrc exists & not --overwrite? ──yes──► skip (log)
             │ no
             ▼
        Transcriber.transcribe(path) ──► .lrc beside audio
             │ on error
             ▼
        log + continue
             │
             ▼
        summary: N done, M skipped, K failed
```

## Output contract (Jellyfin)

- `track.flac` → `track.lrc`, identical basename, same directory.
- Synced format: `[mm:ss.xx]line` lines (openlrc default). Jellyfin reads it as a
  sidecar automatically — no tagging, no server API calls.

## Error handling

- Lemonade/NPU not involved in v1 → no network dependency.
- Missing/corrupt audio → caught per-file, logged, batch continues.
- Whisper hallucination/looping on instrumental sections is a known model limitation;
  openlrc's VAD mitigates but does not eliminate it. Accepted for v1; surfaced in docs.

## Testing strategy

- **Unit:** CLI input resolution (file vs dir vs missing), audio-extension filtering,
  skip-existing logic, sibling-path computation, summary accounting. These are pure /
  filesystem logic — testable without running whisper (mock the transcriber).
- **Integration (manual / opt-in):** run against `15 - Piosenka o CYFERKACH.mp3` with
  `large-v3-turbo`, eyeball the `.lrc` for text quality and timestamp sanity. Slow
  (model download + CPU decode), so not in the default fast test loop.

## Environment notes

- Python 3.12 venv via `uv` at `.venv/` (Python 3.14 brew lacks faster-whisper wheels;
  no torch needed for the transcribe-only path).
- ffmpeg present (linuxbrew).
- First `large-v3-turbo` run downloads the model (~1.5GB) to the HF cache.

## Deferred (future, not v1)

- Translation / bilingual `.lrc`.
- Watch-folder daemon or cron auto-processing.
- Path B (NPU text + forced alignment) as a per-track fallback for poor transcriptions.
