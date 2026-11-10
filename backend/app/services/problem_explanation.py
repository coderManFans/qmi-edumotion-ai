import re
import uuid

from starlette.concurrency import run_in_threadpool

from app.ai.problem_solver import solve_problem, to_scenes, _local_solution
from app.render.video_renderer import render_explanation_video
from app.schemas.problem import ProblemExplanationResponse


def build_explanation(problem_text: str, source_type: str) -> ProblemExplanationResponse:
    cleaned = re.sub(r"\s+", " ", problem_text).strip()
    solution = _local_solution(cleaned)
    return ProblemExplanationResponse(
        job_id=str(uuid.uuid4()), source_type=source_type, extracted_text=cleaned,
        problem_title=cleaned[:42] + ("…" if len(cleaned) > 42 else ""),
        explanation=solution.explanation, answer=solution.answer,
        verification_status=solution.verification_status, scenes=to_scenes(solution, cleaned),
    )


async def generate_explanation_video(problem_text: str, source_type: str) -> ProblemExplanationResponse:
    cleaned = re.sub(r"\s+", " ", problem_text).strip()
    solution = await solve_problem(cleaned)
    scenes = to_scenes(solution, cleaned)
    job_id = str(uuid.uuid4())
    await run_in_threadpool(render_explanation_video, job_id, scenes)
    return ProblemExplanationResponse(
        job_id=job_id, source_type=source_type, extracted_text=cleaned,
        problem_title=cleaned[:42] + ("…" if len(cleaned) > 42 else ""),
        explanation=solution.explanation, answer=solution.answer,
        verification_status=solution.verification_status, scenes=scenes,
        video_status="completed", video_url=f"/api/v1/problems/videos/{job_id}",
    )
