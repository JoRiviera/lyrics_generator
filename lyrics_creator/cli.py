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
