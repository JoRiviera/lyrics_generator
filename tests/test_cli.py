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
