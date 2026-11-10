import asyncio
import tempfile
from pathlib import Path

from app.ai.problem_solver import solve_problem, to_scenes
from app.celery_app import celery_app
from app.render.video_renderer import render_explanation_video
from app.schemas.problem import ProblemExplanationResponse
from app.services.tts import synthesize_scene_audio_sync


@celery_app.task(bind=True, name="app.tasks.generate_problem_video", max_retries=0)
def generate_problem_video_task(self, job_id: str, problem_text: str, source_type: str) -> dict:
    self.update_state(state="PROGRESS", meta={"progress": 5, "stage": "正在分析题目并生成解题步骤"})
    solution = asyncio.run(solve_problem(problem_text))
    scenes = to_scenes(solution, problem_text)

    self.update_state(state="PROGRESS", meta={"progress": 25, "stage": "解题完成，正在合成中文语音"})
    with tempfile.TemporaryDirectory(prefix=f"edumotion-tts-{job_id[:8]}-") as temp_dir:
        audio_path, durations = synthesize_scene_audio_sync(scenes, Path(temp_dir))
        self.update_state(state="PROGRESS", meta={"progress": 60, "stage": "中文配音完成，正在绘制动画画面"})
        render_explanation_video(
            job_id, scenes, audio_path=audio_path, scene_durations=durations
        )

    self.update_state(state="PROGRESS", meta={"progress": 95, "stage": "视频已合成，正在保存任务结果"})
    response = ProblemExplanationResponse(
        job_id=job_id,
        source_type=source_type,
        extracted_text=problem_text,
        problem_title=problem_text[:42] + ("…" if len(problem_text) > 42 else ""),
        explanation=solution.explanation,
        answer=solution.answer,
        verification_status=solution.verification_status,
        scenes=scenes,
        video_status="completed",
        video_url=f"/api/v1/problems/videos/{job_id}",
    )
    return response.model_dump(mode="json")
