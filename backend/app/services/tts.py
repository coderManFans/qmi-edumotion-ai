import asyncio
import subprocess
from pathlib import Path

from app.core.config import settings
from app.schemas.problem import ExplanationScene


def _ffprobe_bin() -> str:
    configured = Path(settings.ffmpeg_bin)
    if configured.is_absolute() or configured.parent != Path("."):
        return str(configured.with_name("ffprobe"))
    return "ffprobe"


def _audio_duration(path: Path) -> float:
    result = subprocess.run(
        [
            _ffprobe_bin(), "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if result.returncode:
        raise RuntimeError(f"无法读取语音时长：{result.stderr[-500:]}")
    try:
        duration = float(result.stdout.strip())
    except ValueError as exc:
        raise RuntimeError("TTS 返回的音频文件没有有效时长。") from exc
    if not 0 < duration < float("inf"):
        raise RuntimeError("TTS 返回的音频文件时长无效。")
    return max(duration, 0.2)


async def synthesize_scene_audio(
    scenes: list[ExplanationScene], work_dir: Path
) -> tuple[Path | None, list[float] | None]:
    provider = settings.tts_provider.strip().lower()
    if provider in {"", "none", "disabled"}:
        return None, None
    if provider != "edge":
        raise RuntimeError(f"不支持的 TTS_PROVIDER：{settings.tts_provider}")

    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError("未安装 edge-tts，请重新安装 backend/requirements.txt。") from exc

    work_dir.mkdir(parents=True, exist_ok=True)
    segment_paths: list[Path] = []
    durations: list[float] = []
    for index, scene in enumerate(scenes):
        narration = (scene.narration or scene.title).strip()
        if not narration:
            narration = "请看屏幕中的解题步骤。"
        segment = work_dir / f"scene_{index:03d}.mp3"
        communicate = edge_tts.Communicate(
            narration, voice=settings.tts_voice, rate=settings.tts_rate
        )
        try:
            await asyncio.wait_for(
                communicate.save(str(segment)), timeout=settings.tts_timeout_seconds
            )
        except asyncio.TimeoutError as exc:
            raise RuntimeError(
                f"第 {index + 1} 个镜头的 Edge TTS 请求超时（{settings.tts_timeout_seconds:g} 秒）。"
            ) from exc
        if not segment.is_file() or segment.stat().st_size == 0:
            raise RuntimeError(f"第 {index + 1} 个镜头的 TTS 没有生成音频。")
        segment_paths.append(segment)
        durations.append(_audio_duration(segment))

    concat_file = work_dir / "audio_concat.txt"
    concat_file.write_text(
        "".join(f"file '{path.name}'\n" for path in segment_paths),
        encoding="utf-8",
    )
    output = work_dir / "narration.mp3"
    merged = subprocess.run(
        [
            settings.ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-c:a", "libmp3lame", "-q:a", "3", str(output),
        ],
        cwd=work_dir, capture_output=True, text=True, timeout=180, check=False,
    )
    if merged.returncode:
        raise RuntimeError(f"语音分段合并失败：{merged.stderr[-1000:]}")
    return output, durations


def synthesize_scene_audio_sync(
    scenes: list[ExplanationScene], work_dir: Path
) -> tuple[Path | None, list[float] | None]:
    return asyncio.run(synthesize_scene_audio(scenes, work_dir))
