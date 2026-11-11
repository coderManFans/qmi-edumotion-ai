from pathlib import Path
import sys
from types import SimpleNamespace

from app.schemas.problem import ExplanationScene
from app.services.tts import synthesize_scene_audio


def test_disabled_tts_returns_silent_video_configuration(monkeypatch, tmp_path: Path):
    from app.core import config

    monkeypatch.setattr(config.settings, "tts_provider", "none")
    scenes = [
        ExplanationScene(
            id="scene-1", title="计算", narration="十二减四等于八。",
            visual="answer", visual_text="12 - 4 = 8",
        )
    ]

    import asyncio
    audio_path, durations = asyncio.run(synthesize_scene_audio(scenes, tmp_path))
    assert audio_path is None
    assert durations is None


def test_tts_provider_rejects_unknown_provider(monkeypatch, tmp_path: Path):
    from app.core import config
    import asyncio
    import pytest

    monkeypatch.setattr(config.settings, "tts_provider", "unknown")
    scene = ExplanationScene(
        id="scene-1", title="计算", narration="计算结果。",
        visual="step", visual_text="1 + 1 = 2",
    )
    with pytest.raises(RuntimeError, match="不支持的 TTS_PROVIDER"):
        asyncio.run(synthesize_scene_audio([scene], tmp_path))


def test_edge_tts_adapter_saves_audio_and_uses_ffprobe_duration(monkeypatch, tmp_path: Path):
    import asyncio
    from app.core import config
    from app.services import tts

    calls = []
    monkeypatch.setattr(config.settings, "tts_provider", "edge")
    monkeypatch.setattr(config.settings, "tts_voice", "zh-CN-XiaoxiaoNeural")
    monkeypatch.setattr(config.settings, "tts_rate", "+0%")

    class FakeCommunicate:
        def __init__(self, text, voice, rate):
            calls.append((text, voice, rate))

        async def save(self, path):
            Path(path).write_bytes(b"fake-mp3-segment")

    monkeypatch.setitem(sys.modules, "edge_tts", SimpleNamespace(Communicate=FakeCommunicate))

    def fake_run(command, **kwargs):
        if command[0] == "ffprobe":
            return SimpleNamespace(returncode=0, stdout="1.25\n", stderr="")
        if command[0] == "ffmpeg":
            Path(command[-1]).write_bytes(b"fake-merged-mp3")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(f"Unexpected subprocess: {command}")

    monkeypatch.setattr(tts.subprocess, "run", fake_run)
    scene = ExplanationScene(
        id="scene-1",
        title="计算",
        narration="十二减四等于八。",
        visual="answer",
        visual_text="12 - 4 = 8",
    )

    audio_path, durations = asyncio.run(tts.synthesize_scene_audio([scene], tmp_path))

    assert audio_path is not None and audio_path.read_bytes() == b"fake-merged-mp3"
    assert durations == [1.25]
    assert calls == [("十二减四等于八。", "zh-CN-XiaoxiaoNeural", "+0%")]
    assert (tmp_path / "audio_concat.txt").read_text(encoding="utf-8") == "file 'scene_000.mp3'\n"
