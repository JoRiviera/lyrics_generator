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
