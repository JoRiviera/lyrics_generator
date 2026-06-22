# lyrics_creator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A CLI that turns an audio file or a folder of audio into synced `.lrc` lyric sidecars for Jellyfin, fully offline.

**Architecture:** Single-stage pipeline — openlrc (faster-whisper `large-v3-turbo`, CPU/int8, transcribe-only) produces a synced `.lrc` per file. A thin batch driver resolves a file-or-folder argument, skips already-done files, isolates per-file errors, and prints a summary. Discovery logic is pure/filesystem (unit-tested); the transcriber wraps openlrc (tested with a mock); the real model run is a manual integration check.

**Tech Stack:** Python 3.12 (`.venv` via `uv`), openlrc, faster-whisper, pytest. No torch (transcribe-only path). ffmpeg (linuxbrew, already present).

## Global Constraints

- Python 3.12 venv at `.venv/` (Python 3.14 brew lacks faster-whisper wheels). Run everything via `.venv/bin/python` / `.venv/bin/pytest`.
- Transcription config is fixed: `whisper_model='large-v3-turbo'`, `device='cpu'`, `compute_type='int8'`, `skip_trans=True`, `clear_temp=True`.
- Audio extensions (case-insensitive): `.mp3 .flac .m4a .ogg .opus .wav`.
- Output `.lrc` MUST sit beside its source audio, same basename, same folder.
- Idempotent: skip a file whose sibling `.lrc` already exists unless `--overwrite`.
- No network/LLM/NPU dependency. No translation. No polish.

---

## File Structure

- `pyproject.toml` — package metadata, dependency record, `lyrics-creator` console script.
- `lyrics_creator/__init__.py` — package marker.
- `lyrics_creator/discovery.py` — pure filesystem logic: audio detection, `.lrc` sibling path, file discovery, skip decision.
- `lyrics_creator/transcriber.py` — `Transcriber` class wrapping openlrc `LRCer`; runs once-loaded model across files; places `.lrc` beside source.
- `lyrics_creator/cli.py` — argparse, orchestration (`run`/`process_file`), logging, summary, exit code.
- `lyrics_creator/__main__.py` — `python -m lyrics_creator` entry.
- `tests/test_discovery.py` — unit tests for discovery (pure).
- `tests/test_cli.py` — orchestration tests with an injected fake transcriber.

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `lyrics_creator/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing.
- Produces: importable package `lyrics_creator`; working `.venv/bin/pytest`.

- [ ] **Step 1: Initialize git (repo does not exist yet)**

```bash
cd /var/home/jonathan/perso/lyrics_creator
git init
printf '%s\n' '.venv/' '__pycache__/' '*.pyc' 'preprocessed/' '*.lrc' '!docs/**' > .gitignore
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "lyrics-creator"
version = "0.1.0"
description = "Generate synced .lrc lyrics from audio, offline, for Jellyfin"
requires-python = ">=3.12"
dependencies = ["openlrc"]

[project.scripts]
lyrics-creator = "lyrics_creator.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Create package + test markers**

`lyrics_creator/__init__.py`:
```python
"""Offline synced-lyrics generator (audio -> .lrc) for Jellyfin."""
```

`tests/__init__.py`: (empty file)

- [ ] **Step 4: Write a smoke test**

`tests/test_smoke.py`:
```python
import lyrics_creator


def test_package_imports():
    assert lyrics_creator.__doc__
```

- [ ] **Step 5: Ensure pytest is installed and run the smoke test**

Run:
```bash
.venv/bin/python -m pip install -q pytest
.venv/bin/python -m pytest tests/test_smoke.py -v
```
Expected: PASS (`test_package_imports`).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml lyrics_creator/__init__.py tests/__init__.py tests/test_smoke.py .gitignore docs/
git commit -m "chore: scaffold lyrics_creator package and test harness"
```

---

### Task 2: Discovery module

**Files:**
- Create: `lyrics_creator/discovery.py`
- Test: `tests/test_discovery.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `AUDIO_EXTS: set[str]`
  - `is_audio_file(path: Path) -> bool`
  - `lrc_path_for(audio: Path) -> Path`
  - `find_audio_files(root: Path) -> list[Path]` (file → `[file]` if audio else `[]`; dir → recursive, sorted)
  - `needs_processing(audio: Path, overwrite: bool) -> bool`

- [ ] **Step 1: Write the failing tests**

`tests/test_discovery.py`:
```python
from pathlib import Path

from lyrics_creator.discovery import (
    is_audio_file,
    lrc_path_for,
    find_audio_files,
    needs_processing,
)


def test_is_audio_file_by_extension(tmp_path):
    mp3 = tmp_path / "a.mp3"
    mp3.touch()
    txt = tmp_path / "a.txt"
    txt.touch()
    assert is_audio_file(mp3) is True
    assert is_audio_file(txt) is False


def test_is_audio_file_is_case_insensitive(tmp_path):
    f = tmp_path / "a.FLAC"
    f.touch()
    assert is_audio_file(f) is True


def test_lrc_path_for_replaces_suffix(tmp_path):
    audio = tmp_path / "song.flac"
    assert lrc_path_for(audio) == tmp_path / "song.lrc"


def test_find_audio_files_single_file(tmp_path):
    mp3 = tmp_path / "a.mp3"
    mp3.touch()
    assert find_audio_files(mp3) == [mp3]


def test_find_audio_files_single_non_audio_file(tmp_path):
    txt = tmp_path / "a.txt"
    txt.touch()
    assert find_audio_files(txt) == []


def test_find_audio_files_recurses_and_sorts(tmp_path):
    (tmp_path / "b.mp3").touch()
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.flac").touch()
    (tmp_path / "notes.txt").touch()
    found = find_audio_files(tmp_path)
    assert found == [tmp_path / "sub" / "a.flac", tmp_path / "b.mp3"]


def test_needs_processing_skips_when_lrc_exists(tmp_path):
    audio = tmp_path / "song.mp3"
    audio.touch()
    (tmp_path / "song.lrc").touch()
    assert needs_processing(audio, overwrite=False) is False
    assert needs_processing(audio, overwrite=True) is True


def test_needs_processing_true_when_no_lrc(tmp_path):
    audio = tmp_path / "song.mp3"
    audio.touch()
    assert needs_processing(audio, overwrite=False) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_discovery.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lyrics_creator.discovery'`.

- [ ] **Step 3: Implement `discovery.py`**

`lyrics_creator/discovery.py`:
```python
"""Pure filesystem logic: locate audio files and decide what to process."""
from pathlib import Path

AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".ogg", ".opus", ".wav"}


def is_audio_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in AUDIO_EXTS


def lrc_path_for(audio: Path) -> Path:
    return audio.with_suffix(".lrc")


def find_audio_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if is_audio_file(root) else []
    return sorted(p for p in root.rglob("*") if is_audio_file(p))


def needs_processing(audio: Path, overwrite: bool) -> bool:
    if overwrite:
        return True
    return not lrc_path_for(audio).exists()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_discovery.py -v`
Expected: PASS (all 8 tests).

- [ ] **Step 5: Commit**

```bash
git add lyrics_creator/discovery.py tests/test_discovery.py
git commit -m "feat: audio discovery and skip logic"
```

---

### Task 3: Transcriber wrapper

**Files:**
- Create: `lyrics_creator/transcriber.py`
- Test: `tests/test_transcriber.py`

**Interfaces:**
- Consumes: `discovery.lrc_path_for` (indirectly, via `audio.with_suffix('.lrc')`).
- Produces:
  - `class Transcriber` with `__init__(self, lang: str | None = None, model: str = "large-v3-turbo")` and `transcribe(self, audio: Path) -> Path` (returns the `.lrc` path beside `audio`).

**Notes for the implementer:**
- openlrc's `LRCer.run(path, src_lang=..., skip_trans=True, clear_temp=True)` returns a `list[Path]`; element 0 is the produced `.lrc` (it may be written relative to the current working directory, not beside the source). The wrapper must move it beside the source if it isn't already there. Use `shutil.move` (handles cross-directory).
- The `LRCer` is created once in `__init__` so the whisper model loads a single time and is reused across files.
- The test must NOT load openlrc/the real model. Patch `lyrics_creator.transcriber.LRCer` with a fake before constructing `Transcriber`.

- [ ] **Step 1: Write the failing tests**

`tests/test_transcriber.py`:
```python
import shutil
from pathlib import Path

import lyrics_creator.transcriber as transcriber_mod
from lyrics_creator.transcriber import Transcriber


class FakeLRCer:
    """Stand-in for openlrc.LRCer that writes the .lrc into cwd, like the real one."""

    instances = []

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        self.calls = []
        FakeLRCer.instances.append(self)

    def run(self, path, src_lang=None, skip_trans=False, clear_temp=False):
        self.calls.append(
            {"path": path, "src_lang": src_lang,
             "skip_trans": skip_trans, "clear_temp": clear_temp}
        )
        # Real openlrc writes the .lrc to cwd, not necessarily beside source.
        produced = Path.cwd() / (Path(path).stem + ".lrc")
        produced.write_text("[00:01.00]hello\n", encoding="utf-8")
        return [produced]


def test_transcribe_places_lrc_beside_source(tmp_path, monkeypatch):
    FakeLRCer.instances = []
    monkeypatch.setattr(transcriber_mod, "LRCer", FakeLRCer)
    # Make cwd different from the audio's folder to prove the move happens.
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    music = tmp_path / "music"
    music.mkdir()
    audio = music / "song.mp3"
    audio.touch()

    t = Transcriber(lang="pl")
    out = t.transcribe(audio)

    assert out == music / "song.lrc"
    assert out.exists()
    assert not (work / "song.lrc").exists()


def test_transcribe_passes_fixed_config_and_args(tmp_path, monkeypatch):
    FakeLRCer.instances = []
    monkeypatch.setattr(transcriber_mod, "LRCer", FakeLRCer)
    monkeypatch.chdir(tmp_path)
    audio = tmp_path / "a.flac"
    audio.touch()

    t = Transcriber(lang=None)
    t.transcribe(audio)

    lrcer = FakeLRCer.instances[0]
    call = lrcer.calls[0]
    assert call["skip_trans"] is True
    assert call["clear_temp"] is True
    assert call["src_lang"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_transcriber.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lyrics_creator.transcriber'`.

- [ ] **Step 3: Implement `transcriber.py`**

`lyrics_creator/transcriber.py`:
```python
"""Wrap openlrc to transcribe one audio file into a synced .lrc beside it."""
import shutil
from pathlib import Path

from openlrc import LRCer, TranscriptionConfig


class Transcriber:
    def __init__(self, lang: str | None = None, model: str = "large-v3-turbo"):
        self.lang = lang
        self._lrcer = LRCer(
            transcription=TranscriptionConfig(
                whisper_model=model,
                device="cpu",
                compute_type="int8",
            )
        )

    def transcribe(self, audio: Path) -> Path:
        results = self._lrcer.run(
            str(audio),
            src_lang=self.lang,
            skip_trans=True,
            clear_temp=True,
        )
        produced = Path(results[0])
        target = audio.with_suffix(".lrc")
        if produced.resolve() != target.resolve():
            shutil.move(str(produced), str(target))
        return target
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_transcriber.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add lyrics_creator/transcriber.py tests/test_transcriber.py
git commit -m "feat: openlrc transcriber wrapper writing .lrc beside source"
```

---

### Task 4: CLI orchestration

**Files:**
- Create: `lyrics_creator/cli.py`
- Create: `lyrics_creator/__main__.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `discovery.find_audio_files`, `discovery.needs_processing`; `Transcriber` (lazily imported inside `run`, so tests can inject a fake without loading openlrc).
- Produces:
  - `process_file(transcriber, audio: Path, overwrite: bool) -> str` returning `"done" | "skipped" | "failed"`.
  - `run(root: Path, lang: str | None, overwrite: bool, transcriber=None) -> dict` returning counts `{"done": int, "skipped": int, "failed": int}`.
  - `main(argv: list[str] | None = None) -> int` (exit code: `1` if any file failed, else `0`).

**Notes for the implementer:**
- `run` only constructs a real `Transcriber` when `transcriber is None`. Import `Transcriber` *inside* `run` (not at module top) so importing `cli` for tests does not import openlrc.
- A `transcribe` exception must be caught per file, logged, counted as `"failed"`, and the loop continues.

- [ ] **Step 1: Write the failing tests**

`tests/test_cli.py`:
```python
from pathlib import Path

from lyrics_creator.cli import process_file, run, main


class FakeTranscriber:
    def __init__(self, fail_on=None):
        self.fail_on = fail_on or set()
        self.seen = []

    def transcribe(self, audio: Path) -> Path:
        self.seen.append(audio)
        if audio.name in self.fail_on:
            raise RuntimeError("boom")
        out = audio.with_suffix(".lrc")
        out.write_text("[00:01.00]x\n", encoding="utf-8")
        return out


def test_process_file_skips_existing(tmp_path):
    audio = tmp_path / "a.mp3"
    audio.touch()
    (tmp_path / "a.lrc").touch()
    t = FakeTranscriber()
    assert process_file(t, audio, overwrite=False) == "skipped"
    assert t.seen == []


def test_process_file_done(tmp_path):
    audio = tmp_path / "a.mp3"
    audio.touch()
    t = FakeTranscriber()
    assert process_file(t, audio, overwrite=False) == "done"
    assert (tmp_path / "a.lrc").exists()


def test_process_file_failure_is_isolated(tmp_path):
    audio = tmp_path / "a.mp3"
    audio.touch()
    t = FakeTranscriber(fail_on={"a.mp3"})
    assert process_file(t, audio, overwrite=False) == "failed"


def test_run_over_folder_counts(tmp_path):
    (tmp_path / "good.mp3").touch()
    (tmp_path / "bad.mp3").touch()
    (tmp_path / "already.mp3").touch()
    (tmp_path / "already.lrc").touch()
    t = FakeTranscriber(fail_on={"bad.mp3"})
    counts = run(tmp_path, lang=None, overwrite=False, transcriber=t)
    assert counts == {"done": 1, "skipped": 1, "failed": 1}


def test_run_overwrite_reprocesses(tmp_path):
    (tmp_path / "a.mp3").touch()
    (tmp_path / "a.lrc").touch()
    t = FakeTranscriber()
    counts = run(tmp_path, lang=None, overwrite=True, transcriber=t)
    assert counts == {"done": 1, "skipped": 0, "failed": 0}


def test_main_missing_path_errors(tmp_path, capsys):
    code = None
    try:
        main([str(tmp_path / "nope.mp3")])
    except SystemExit as e:
        code = e.code
    assert code == 2  # argparse error exit


def test_main_returns_nonzero_on_failure(tmp_path, monkeypatch):
    (tmp_path / "bad.mp3").touch()
    import lyrics_creator.cli as cli

    def fake_run(root, lang, overwrite, transcriber=None):
        return {"done": 0, "skipped": 0, "failed": 1}

    monkeypatch.setattr(cli, "run", fake_run)
    assert main([str(tmp_path)]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lyrics_creator.cli'`.

- [ ] **Step 3: Implement `cli.py` and `__main__.py`**

`lyrics_creator/cli.py`:
```python
"""Command-line entry: resolve a file/folder, transcribe each, report a summary."""
import argparse
import logging
from pathlib import Path

from .discovery import find_audio_files, needs_processing

log = logging.getLogger("lyrics_creator")


def process_file(transcriber, audio: Path, overwrite: bool) -> str:
    if not needs_processing(audio, overwrite):
        log.info("skip (exists): %s", audio.name)
        return "skipped"
    try:
        out = transcriber.transcribe(audio)
        log.info("done: %s -> %s", audio.name, out.name)
        return "done"
    except Exception:
        log.exception("failed: %s", audio.name)
        return "failed"


def run(root: Path, lang: str | None, overwrite: bool, transcriber=None) -> dict:
    audio_files = find_audio_files(root)
    if not audio_files:
        log.warning("no audio files found at %s", root)
    if transcriber is None:
        from .transcriber import Transcriber

        transcriber = Transcriber(lang=lang)
    counts = {"done": 0, "skipped": 0, "failed": 0}
    for audio in audio_files:
        counts[process_file(transcriber, audio, overwrite)] += 1
    log.info(
        "summary: %d done, %d skipped, %d failed",
        counts["done"], counts["skipped"], counts["failed"],
    )
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lyrics-creator",
        description="Generate synced .lrc lyrics from audio (offline).",
    )
    parser.add_argument("path", type=Path, help="audio file or folder")
    parser.add_argument(
        "--lang", default=None,
        help="force source language code (default: auto-detect)",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="regenerate even if a .lrc already exists",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not args.path.exists():
        parser.error(f"path does not exist: {args.path}")
    counts = run(args.path, args.lang, args.overwrite)
    return 1 if counts["failed"] else 0
```

`lyrics_creator/__main__.py`:
```python
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/python -m pytest -v`
Expected: PASS (smoke + discovery + transcriber + cli).

- [ ] **Step 6: Commit**

```bash
git add lyrics_creator/cli.py lyrics_creator/__main__.py tests/test_cli.py
git commit -m "feat: CLI orchestration with skip, error isolation, summary"
```

---

### Task 5: Integration check + README

**Files:**
- Create: `README.md`
- Uses: `15 - Piosenka o CYFERKACH.mp3` (sample in repo root)

**Interfaces:**
- Consumes: the full CLI.
- Produces: nothing new in code; a verified real run and usage docs.

**Notes for the implementer:**
- This run downloads `large-v3-turbo` (~1.5GB) on first use and decodes on CPU (2 cores) — expect a few minutes. This is a manual gate, not part of the fast test loop.

- [ ] **Step 1: Real single-file run**

Run:
```bash
.venv/bin/python -m lyrics_creator "15 - Piosenka o CYFERKACH.mp3" --lang pl --overwrite
```
Expected: logs `done: 15 - Piosenka o CYFERKACH.mp3 -> 15 - Piosenka o CYFERKACH.lrc`, then `summary: 1 done, 0 skipped, 0 failed`. Exit code 0.

- [ ] **Step 2: Inspect the output**

Run: `cat "15 - Piosenka o CYFERKACH.lrc"`
Expected: `[mm:ss.xx]`-prefixed Polish lyric lines that scroll in time order. Confirm the `large-v3-turbo` text reads better than the `small`-model spike (e.g. `Trójka` not `Twórka`, `podwójnym` not `pod wojnym`, `siódemka` not `siódem kato`). Note any residual instrumental-section hallucination in the README's "Known limitations".

- [ ] **Step 3: Verify idempotent skip**

Run:
```bash
.venv/bin/python -m lyrics_creator "15 - Piosenka o CYFERKACH.mp3" --lang pl
```
Expected: `skip (exists)` line; `summary: 0 done, 1 skipped, 0 failed`.

- [ ] **Step 4: Write `README.md`**

`README.md`:
```markdown
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
- Whisper can hallucinate/loop over long instrumental sections; openlrc's VAD
  mitigates but does not fully prevent it.

## Tests

```bash
.venv/bin/python -m pytest
```
```

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: usage README and integration-verified pipeline"
```

---

## Self-Review

**Spec coverage:**
- Goal (file or folder → synced `.lrc` sidecar, offline) → Tasks 2–4.
- File-or-folder CLI → Task 2 `find_audio_files`, Task 4 `main`.
- Fixed `large-v3-turbo`/cpu/int8/`skip_trans`/`clear_temp` config → Task 3.
- `.lrc` beside source → Task 3 move logic + Task 3 test.
- Idempotent skip + `--overwrite` → Task 2 `needs_processing`, Task 4 tests.
- Auto-detect lang + `--lang` override → Task 3 (`src_lang`), Task 4 (`--lang`).
- Per-file error isolation + summary → Task 4 `process_file`/`run`.
- Jellyfin sidecar contract → Task 5 integration + README.
- Env (3.12 venv, no torch, ffmpeg, model download) → Global Constraints + Task 5.
- Non-goals (translation/polish/daemon/Path B) → not implemented. ✓

**Placeholder scan:** No TBD/TODO; every code step has complete code; every command has expected output.

**Type consistency:** `transcribe(audio) -> Path` used consistently in Tasks 3–4; `run`/`process_file` return shapes match their tests; `Transcriber(lang=...)` signature consistent across transcriber and cli.
