import asyncio
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import edge_tts

from app.core.config import celery_app, settings
from app.ai.problem_solver import solve_problem, to_scenes, _local_solution
from app.render.video_renderer import render_explanation_video
from app.schemas.problem import ProblemExplanationResponse


def build_explanation(problem_text: str, source_type: str) -> ProblemExplanationResponse:
    cleaned = re.sub(r"\\s+", " ", problem_text).strip()
    solution = _local_solution(cleaned)
    return ProblemExplanationResponse(
        job_id=str(uuid.uuid4()), source_type=source_type, extracted_text=cleaned,
        problem_title=cleaned[:42] + ("…" if len(cleaned) > 42 else ""),
        explanation=solution.explanation, answer=solution.answer,
        verification_status=solution.verification_status, scenes=to_scenes(solution, cleaned),
    )


async def _synthesize_scene(text: str, target: Path) -> None:
    await edge_tts.Communicate(
        text=text, voice=settings.tts_voice, rate=settings.tts_rate
    ).save(str(target))


async def _create_narration(scenes, workdir: Path) -> tuple[Path, list[float]]:
    if settings.tts_provider.lower() != "edge":
        raise RuntimeError(f"暂不支持 TTS_PROVIDER={settings.tts_provider!r}，当前支持 edge。")
    ffmpeg = shutil.which(settings.ffmpeg_bin)
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg:
        raise RuntimeError(f"未找到 FFmpeg：{settings.ffmpeg_bin}。")
    tracks: list[Path] = []
    durations: list[float] = []
    for index, scene in enumerate(scenes):
        text = (scene.narration or scene.title).strip()
        track = workdir / f"narration_{index:03d}.mp3"
        await _synthesize_scene(text, track)
        tracks.append(track)
        duration = max(2.0, len(text) / 4.0)
        if ffprobe:
            probe = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(track)],
                capture_output=True, text=True, timeout=30, check=False,
            )
            if probe.returncode == 0 and probe.stdout.strip():
                duration = max(1.0, float(probe.stdout.strip()))
        durations.append(duration)
    concat_file = workdir / "narration_concat.txt"
    concat_file.write_text(
        "".join(f"file '{track.as_posix()}'\\n" for track in tracks), encoding="utf-8"
    )
    combined = workdir / "narration.mp3"
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat",
         "-safe", "0", "-i", str(concat_file), "-c:a", "libmp3lame", "-q:a", "4",
         str(combined)],
        capture_output=True, text=True, timeout=180, check=False,
    )
    if result.returncode:
        raise RuntimeError(f"语音片段合并失败：{result.stderr[-1000:]}")
    return combined, durations


@celery_app.task(bind=True, name="app.services.problem_explanation.generate_problem_video_task")
def generate_problem_video_task(self, problem_text: str, source_type: str) -> dict:
    cleaned = re.sub(r"\\s+", " ", problem_text).strip()
    with tempfile.TemporaryDirectory(prefix="edumotion-tts-") as temp_dir:
        workdir = Path(temp_dir)
        self.update_state(state="PROGRESS", meta={"progress": 8, "stage": "正在分析题目"})
        solution = asyncio.run(solve_problem(cleaned))
        scenes = to_scenes(solution, cleaned)

        self.update_state(state="PROGRESS", meta={"progress": 28, "stage": "正在生成中文旁白"})
        audio_path, durations = asyncio.run(_create_narration(scenes, workdir))

        self.update_state(state="PROGRESS", meta={"progress": 55, "stage": "正在绘制动画并合成音画"})
        job_id = self.request.id or str(uuid.uuid4())
        render_explanation_video(job_id, scenes, audio_path=audio_path, scene_durations=durations)
        response = ProblemExplanationResponse(
            job_id=job_id, source_type=source_type, extracted_text=cleaned,
            problem_title=cleaned[:42] + ("…" if len(cleaned) > 42 else ""),
            explanation=solution.explanation, answer=solution.answer,
            verification_status=solution.verification_status, scenes=scenes,
            video_status="completed", video_url=f"/api/v1/problems/videos/{job_id}",
        )
        self.update_state(state="PROGRESS", meta={"progress": 95, "stage": "正在整理视频结果"})
        return response.model_dump(mode="json")


async def generate_explanation_video(problem_text: str, source_type: str) -> ProblemExplanationResponse:
    """Compatibility helper for direct, synchronous video generation."""
    cleaned = re.sub(r"\\s+", " ", problem_text).strip()
    solution = await solve_problem(cleaned)
    scenes = to_scenes(solution, cleaned)
    job_id = str(uuid.uuid4())
    with tempfile.TemporaryDirectory(prefix="edumotion-tts-") as temp_dir:
        audio_path, durations = await _create_narration(scenes, Path(temp_dir))
        await run_renderer(job_id, scenes, audio_path, durations)
    return ProblemExplanationResponse(
        job_id=job_id, source_type=source_type, extracted_text=cleaned,
        problem_title=cleaned[:42] + ("…" if len(cleaned) > 42 else ""),
        explanation=solution.explanation, answer=solution.answer,
        verification_status=solution.verification_status, scenes=scenes,
        video_status="completed", video_url=f"/api/v1/problems/videos/{job_id}",
    )


async def run_renderer(job_id, scenes, audio_path, durations):
    from starlette.concurrency import run_in_threadpool
    await run_in_threadpool(
        render_explanation_video, job_id, scenes, audio_path=audio_path, scene_durations=durations
    )
