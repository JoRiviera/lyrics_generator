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
