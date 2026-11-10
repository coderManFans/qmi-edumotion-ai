from pathlib import Path

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
