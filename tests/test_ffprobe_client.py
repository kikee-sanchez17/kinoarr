import json
import subprocess
from pathlib import Path

import pytest

from app.clients import ffprobe
from app.clients.ffprobe import FfprobeClient, FfprobeError
from app.models import SubtitleStream

VIDEO = Path("/downloads/My Movie (1968)/My Movie.mkv")

# Shape recorded from a real ffprobe run.
FFPROBE_OUTPUT = {
    "streams": [
        {
            "index": 2,
            "codec_name": "subrip",
            "disposition": {"forced": 0, "hearing_impaired": 1},
            "tags": {"language": "eng", "title": "English SDH"},
        },
        {"index": 3, "codec_name": "hdmv_pgs_subtitle", "disposition": {"forced": 0, "hearing_impaired": 0}},
    ]
}


def fake_run(monkeypatch, *, stdout="", stderr="", returncode=0, raises=None) -> list[list[str]]:
    calls: list[list[str]] = []

    def run(command, **kwargs):
        calls.append(command)
        if raises:
            raise raises
        return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(ffprobe.subprocess, "run", run)
    return calls


def test_subtitle_streams_parses_ffprobe_json(monkeypatch):
    fake_run(monkeypatch, stdout=json.dumps(FFPROBE_OUTPUT))

    streams = FfprobeClient().subtitle_streams(VIDEO)

    assert streams == [
        SubtitleStream(
            index=2, codec="subrip", language="eng", title="English SDH", forced=False, hearing_impaired=True
        ),
        SubtitleStream(
            index=3, codec="hdmv_pgs_subtitle", language=None, title=None, forced=False, hearing_impaired=False
        ),
    ]


def test_subtitle_streams_passes_path_as_a_single_argument(monkeypatch):
    calls = fake_run(monkeypatch, stdout='{"streams": []}')

    FfprobeClient().subtitle_streams(VIDEO)

    [command] = calls
    assert command[0] == "ffprobe"
    assert command[-1] == str(VIDEO)
    assert ["-select_streams", "s"] == command[command.index("-select_streams") :][:2]


def test_no_subtitle_streams(monkeypatch):
    fake_run(monkeypatch, stdout="{}")

    assert FfprobeClient().subtitle_streams(VIDEO) == []


@pytest.mark.parametrize(
    ("run_kwargs", "expected_message"),
    [
        ({"raises": FileNotFoundError()}, "ffprobe not found"),
        ({"raises": subprocess.TimeoutExpired("ffprobe", 60)}, "timed out on My Movie.mkv"),
        ({"returncode": 1, "stderr": "Invalid data found when processing input\nmore"}, "Invalid data found"),
        ({"returncode": 1}, "exit code 1"),
        ({"stdout": "not json"}, "Unexpected ffprobe output"),
        ({"stdout": '{"streams": [{"codec_name": "subrip"}]}'}, "Unexpected ffprobe output"),
    ],
)
def test_failures_raise_ffprobe_error(monkeypatch, run_kwargs, expected_message):
    fake_run(monkeypatch, **run_kwargs)

    with pytest.raises(FfprobeError, match=expected_message):
        FfprobeClient().subtitle_streams(VIDEO)
