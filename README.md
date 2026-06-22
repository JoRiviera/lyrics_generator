# lyrics_creator

Generate synced `.lrc` lyric files from audio, fully offline, for a Jellyfin
music library. Uses [openlrc](https://github.com/zh-plus/openlrc) +
faster-whisper (`large-v3-turbo`, CPU).

## Setup

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python openlrc pytest
```

Requires `ffmpeg` on PATH.

## Usage

```bash
# one file
.venv/bin/python -m lyrics_creator "song.flac"

# a whole library (recurses, writes track.lrc beside each track)
.venv/bin/python -m lyrics_creator /path/to/music

# force language, regenerate existing
.venv/bin/python -m lyrics_creator /path/to/music --lang pl --overwrite
```

Each `track.<ext>` gets a sibling `track.lrc`. Already-done files are skipped
unless `--overwrite`. Drop the folder into Jellyfin; it reads `.lrc` sidecars
automatically. First run downloads the `large-v3-turbo` model (~1.5GB).

## Known limitations

- CPU decode (~minutes per track on low core counts); run as an overnight batch.
  Integration test on a ~2-min Polish song took ~3.5 min (219s) on 2 CPU cores.
- Whisper can hallucinate/loop over long instrumental sections; openlrc's VAD
  mitigates but does not fully prevent it.
- Occasional word-level errors persist even with `large-v3-turbo`: in the
  integration test `Czwórka` was transcribed as `Twórka` (visually similar
  digit names). Quality is noticeably better than `small` — e.g. `podwójnym`
  and `siódemka` were correct — but proofreading is still recommended for
  release lyrics.

## Tests

```bash
.venv/bin/python -m pytest
```
