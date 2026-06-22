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
    return sorted((p for p in root.rglob("*") if is_audio_file(p)), key=lambda p: p.name)


def needs_processing(audio: Path, overwrite: bool) -> bool:
    if overwrite:
        return True
    return not lrc_path_for(audio).exists()
