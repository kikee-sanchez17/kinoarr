import subprocess
from pathlib import Path

import pytest

from app.clients import alass
from app.clients.alass import AlassClient, AlassError

VIDEO = Path("/downloads/Lady Bird (2017)/Lady.Bird.2017.1080p.BluRay.x264-[YTS.AM].mp4")
SUBTITLE = Path("/downloads/Lady Bird (2017)/Lady.Bird.en.srt.unsynced.part")
OUTPUT = Path("/downloads/Lady Bird (2017)/Lady.Bird.en.srt.part")


def fake_run(monkeypatch, *, stdout="", stderr="", returncode=0, raises=None) -> list[list[str]]:
    calls: list[list[str]] = []

    def run(command, **kwargs):
        calls.append(command)
        if raises:
            raise raises
        return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(alass.subprocess, "run", run)
    return calls


def test_sync_passes_video_subtitle_and_output_as_separate_arguments(monkeypatch):
    calls = fake_run(monkeypatch)

    AlassClient().sync(VIDEO, SUBTITLE, OUTPUT)

    assert calls == [["alass", str(VIDEO), str(SUBTITLE), str(OUTPUT)]]


@pytest.mark.parametrize(
    ("run_kwargs", "expected_message"),
    [
        ({"raises": FileNotFoundError()}, "alass not found"),
        ({"raises": subprocess.TimeoutExpired("alass", 600)}, "timed out on Lady.Bird"),
        # Recorded from a real alass 2.0.0 run with a missing subtitle file.
        (
            {
                "returncode": 1,
                "stdout": "error: reading subtitle file '/x.srt' failed\ncaused by: failed to open file '/x.srt'\n",
            },
            "reading subtitle file '/x.srt' failed",
        ),
        ({"returncode": 1, "stdout": "extracting audio...\n", "stderr": "error: no audio\n"}, "error: no audio"),
        ({"returncode": 2}, "exit code 2"),
    ],
)
def test_failures_raise_alass_error(monkeypatch, run_kwargs, expected_message):
    fake_run(monkeypatch, **run_kwargs)

    with pytest.raises(AlassError, match=expected_message):
        AlassClient().sync(VIDEO, SUBTITLE, OUTPUT)
