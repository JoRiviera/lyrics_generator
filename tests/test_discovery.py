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
