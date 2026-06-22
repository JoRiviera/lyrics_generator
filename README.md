# lyrics_creator

Generate **synced `.lrc` lyric files** from audio, fully offline, for a Jellyfin
music library. Point it at one song or a whole folder; it writes a timestamped
`track.lrc` next to each `track.<ext>`, ready for Jellyfin to pick up as a
sidecar.

Built on [openlrc](https://github.com/zh-plus/openlrc) + faster-whisper
(`large-v3-turbo`, CPU). No cloud, no API keys, no network calls at runtime
(only the one-time model download).

---

## Table of contents

- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Install](#install)
- [Quick start](#quick-start)
- [CLI reference](#cli-reference)
- [Examples](#examples)
- [Output format](#output-format)
- [Using the lyrics in Jellyfin](#using-the-lyrics-in-jellyfin)
- [Performance & batching](#performance--batching)
- [Known limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)
- [Project layout](#project-layout)
- [Tests](#tests)

---

## How it works

```
audio file ──► faster-whisper (large-v3-turbo, CPU/int8, transcribe-only)
            ──► synced .lrc written beside the audio file
```

One pass. The transcribed words and their timestamps come from the same model,
so they stay consistent. No translation, no LLM post-processing — the raw
`large-v3-turbo` transcript *is* the output.

---

## Requirements

- **Python 3.12** (the project pins to 3.12; 3.14 currently lacks faster-whisper
  wheels).
- **ffmpeg** on your `PATH` (audio decoding).
- **[uv](https://github.com/astral-sh/uv)** for environment setup (or plain
  `pip` into a 3.12 venv).
- ~1.5 GB free disk for the `large-v3-turbo` model (downloaded once, on first
  run).

---

## Install

```bash
# from the project root
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python openlrc pytest
```

That's it — no `pip install -e .` required; run it as a module (below). Confirm
ffmpeg is present:

```bash
ffmpeg -version | head -1
```

---

## Quick start

```bash
# transcribe one song
.venv/bin/python -m lyrics_creator "song.flac"

# transcribe an entire library (recurses subfolders)
.venv/bin/python -m lyrics_creator /path/to/music
```

Each run prints per-file progress and a final summary line:

```
done: song.flac -> song.lrc
summary: 1 done, 0 skipped, 0 failed
```

---

## CLI reference

```
usage: lyrics-creator [-h] [--lang LANG] [--overwrite] path

Generate synced .lrc lyrics from audio (offline).

positional arguments:
  path         audio file or folder

options:
  -h, --help   show this help message and exit
  --lang LANG  force source language code (default: auto-detect)
  --overwrite  regenerate even if a .lrc already exists
```

Invoke either way:

```bash
.venv/bin/python -m lyrics_creator <path> [options]
# or, if installed as a script (pip install -e .):
lyrics-creator <path> [options]
```

### `path` (required)

A **file** or a **folder**:

- **File** → that single audio file is processed (if its extension is
  supported; otherwise nothing happens).
- **Folder** → searched **recursively**; every supported audio file is
  processed, in a deterministic order (by filename, then full path).

### Supported audio extensions

Case-insensitive: `.mp3`, `.flac`, `.m4a`, `.ogg`, `.opus`, `.wav`.
Anything else is ignored.

### `--lang LANG`

Force the source language instead of auto-detecting it. Use a Whisper language
code, e.g. `pl` (Polish), `en` (English), `fr`, `de`, `es`, `ja`. Forcing the
language is faster and more reliable than auto-detect when you already know it
(especially for short tracks).

Default: auto-detect.

### `--overwrite`

Regenerate the `.lrc` even if one already exists beside the audio. Without it,
files that already have a sibling `.lrc` are **skipped** — so re-running over a
growing library only processes new tracks (idempotent, safe to re-run).

### Behavior summary

| Situation                                   | Without `--overwrite` | With `--overwrite` |
|---------------------------------------------|-----------------------|--------------------|
| Audio has no `.lrc` yet                      | transcribe            | transcribe         |
| Audio already has a sibling `.lrc`           | **skip**              | regenerate         |
| File extension not supported                 | ignore                | ignore             |
| A file errors mid-batch                      | log + continue        | log + continue     |

### Exit codes

| Code | Meaning                                              |
|------|------------------------------------------------------|
| `0`  | All processed files succeeded (or all skipped).      |
| `1`  | At least one file failed (the rest still ran).       |
| `2`  | Bad invocation — `path` does not exist, or bad args. |

A single bad/corrupt file never aborts a batch: it's logged, counted as
`failed`, and the run moves on. Check the summary line and the exit code.

---

## Examples

**One file, auto-detected language:**

```bash
.venv/bin/python -m lyrics_creator "15 - Piosenka o CYFERKACH.mp3"
```

**One file, forcing Polish (faster, more reliable than auto-detect):**

```bash
.venv/bin/python -m lyrics_creator "15 - Piosenka o CYFERKACH.mp3" --lang pl
```

**A whole library, recursively:**

```bash
.venv/bin/python -m lyrics_creator ~/Music
```

Writes `~/Music/Artist/Album/track.lrc` next to each track, descending into all
subfolders.

**Re-run after adding new albums (only new tracks get processed):**

```bash
.venv/bin/python -m lyrics_creator ~/Music
# existing .lrc files are skipped; only new audio is transcribed
```

**Force-regenerate everything (e.g. after a model upgrade):**

```bash
.venv/bin/python -m lyrics_creator ~/Music --lang pl --overwrite
```

**Overnight batch on a large library, logging to a file:**

```bash
nohup .venv/bin/python -m lyrics_creator ~/Music --lang pl \
  > lyrics.log 2>&1 &
tail -f lyrics.log
```

**Use the exit code in a script:**

```bash
if .venv/bin/python -m lyrics_creator ~/Music; then
  echo "all good"
else
  echo "some files failed — grep the log for 'failed:'"
fi
```

---

## Output format

A standard synced `.lrc`: one `[mm:ss.xx]` timestamp per line, in time order.
Real output from the sample song:

```lrc
[00:05.33] 0, 1, 2, 3, 4.
[00:08.21] Oto pierwsze są cyferki 5, 6, 7, 8.
[00:13.13] Następują potem i wcale nie są gorsze.
[00:19.15] A na końcu jest cyferka 9.
...
```

Blank-timestamp lines mark instrumental gaps. The file is named after the audio
(`song.flac` → `song.lrc`) and written in the **same folder**.

---

## Using the lyrics in Jellyfin

1. Keep the `.lrc` next to its audio file, same basename (this tool does that
   automatically).
2. Trigger a library scan in Jellyfin (or wait for the scheduled one).
3. Play the track — Jellyfin reads the `.lrc` sidecar and shows synced lyrics
   that scroll with playback. No tagging or extra config needed.

---

## Performance & batching

- Transcription runs on **CPU**. Speed scales with core count. On a 2-core
  machine a ~2-minute song takes ~3.5 minutes; on more cores it's faster.
- The **first run** downloads `large-v3-turbo` (~1.5 GB) into the Hugging Face
  cache; subsequent runs reuse it.
- For a big library, run it as an **overnight batch** (see the `nohup` example).
  Because it skips already-done files, you can stop and resume freely.

---

## Known limitations

- **CPU-bound.** No GPU acceleration here; budget minutes per track on low core
  counts.
- **Instrumental sections.** Whisper can occasionally hallucinate or loop over
  long instrumental passages. openlrc's voice-activity detection mitigates this
  but doesn't fully eliminate it.
- **Occasional word errors.** Even `large-v3-turbo` mis-hears the odd word —
  in the sample run `Czwórka` came out as `Twórka` (similar-sounding Polish
  digit names). Quality is clearly better than the smaller models (`podwójnym`,
  `siódemka` were correct), but **proofread** if you need release-grade lyrics.
- **No translation / no polishing.** Output is the raw transcript in the song's
  own language. (An LLM polish step was evaluated and deliberately dropped —
  too slow and it corrupted lines.)

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `path does not exist` (exit 2) | Check the path; quote names with spaces. |
| Nothing happens for a file | Unsupported extension — see the supported list. |
| `summary: 0 done, N skipped` | `.lrc` files already exist; add `--overwrite` to redo. |
| First run hangs for a while | Downloading the ~1.5 GB model — let it finish. |
| `ffmpeg not found` / decode errors | Install ffmpeg and ensure it's on `PATH`. |
| Wrong language detected on short tracks | Pass `--lang <code>` explicitly. |
| One file failed but others worked (exit 1) | Grep the log for `failed:`; the file may be corrupt. |

---

## Project layout

```
lyrics_creator/
  __init__.py
  __main__.py       # `python -m lyrics_creator` entry point
  discovery.py      # find audio files, compute .lrc paths, skip logic
  transcriber.py    # openlrc/faster-whisper wrapper (model loaded once)
  cli.py            # argparse, batch loop, error isolation, summary, exit code
tests/              # 21 unit tests (no model load — fast)
docs/superpowers/   # design spec + implementation plan
```

---

## Tests

```bash
.venv/bin/python -m pytest
```

21 fast unit tests (discovery, transcriber wrapper, CLI orchestration). They use
mocks for the transcriber, so they do **not** download or run the whisper model.
The real end-to-end run is a manual check — point the CLI at an actual audio
file (see [Examples](#examples)).
